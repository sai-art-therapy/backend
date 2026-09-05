from datetime import datetime
import re
from typing import List

from sqlalchemy.orm import Session

from app.models.htp_pdi import HtpPdiInteraction
from app.models.htp_test import HtpTest


_PDI_VISIBLE_FEATURES = (
    (("문", "door"), ("house", "parts", "door", "detected"), "boolean"),
    (("창문", "window"), ("house", "parts", "window", "count"), "count"),
    (("지붕", "roof"), ("house", "parts", "roof", "detected"), "boolean"),
    (("굴뚝", "chimney"), ("house", "parts", "chimney", "detected"), "boolean"),
    (("벽", "wall"), ("house", "parts", "wall", "detected"), "boolean"),
    (("줄기", "trunk"), ("tree", "parts", "trunk", "detected"), "boolean"),
    (("수관", "crown"), ("tree", "parts", "crown", "detected"), "boolean"),
    # A crown detection does not measure individual leaves. With no leaves field,
    # absence questions about leaves are unsupported even if branches are absent.
    (("잎", "잎사귀", "나뭇잎", "leaf", "leaves"), ("tree", "parts", "leaves", "detected"), "boolean"),
    (("가지", "branch"), ("tree", "parts", "branch", "detected"), "boolean"),
    (("뿌리", "root"), ("tree", "parts", "roots", "detected"), "boolean"),
    (("열매", "fruit"), ("tree", "parts", "fruit", "count"), "count"),
    (("꽃", "flower"), ("tree", "parts", "flower", "count"), "count"),
    (("머리", "head"), ("person", "parts", "head", "detected"), "boolean"),
    (("얼굴", "face"), ("person", "parts", "face", "detected"), "boolean"),
    (("손", "hand"), ("person", "parts", "hands", "count"), "count"),
    (("발", "foot", "feet"), ("person", "parts", "feet", "count"), "count"),
    (("팔", "arm"), ("person", "parts", "arms", "count"), "count"),
    (("다리", "leg"), ("person", "parts", "legs", "count"), "count"),
    (("신발", "shoe"), ("person", "parts", "shoes", "detected"), "boolean"),
)


def _nested_value(value: dict, path: tuple[str, ...]):
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _filter_grounded_pdi_questions(questions: list[dict], visual: dict) -> list[dict]:
    """Allow missing-element questions only for explicitly absent features."""
    grounded = []
    for question in questions:
        text = str(question.get("question_text", "")).lower()
        # The model sometimes puts an absence question under default_pdi.
        has_absence_premise = any(term in text for term in (
            "없", "그리지 않", "안 그", "빠져", "생략", "missing", "not drawn",
        ))
        if question.get("question_type") != "missing_element" and not has_absence_premise:
            grounded.append(question)
            continue
        matched_values = []
        for aliases, path, kind in _PDI_VISIBLE_FEATURES:
            if not any(_mentions_feature(text, alias) for alias in aliases):
                continue
            value = _nested_value(visual, path)
            absent = value is False if kind == "boolean" else type(value) is int and value == 0
            matched_values.append(absent)
        if not matched_values:
            for label, aliases in (("house", ("집", "house")), ("tree", ("나무", "tree")),
                                   ("person", ("사람", "person"))):
                if any(_mentions_feature(text, alias) for alias in aliases):
                    matched_values.append(_nested_value(visual, (label, "detected")) is False)
        if matched_values and all(matched_values):
            grounded.append(question)
    return grounded


def _mentions_feature(text: str, alias: str) -> bool:
    # Korean particles attach to nouns. Avoid treating 창문 as 문, 신발 as 발,
    # or 발달 as 발; English aliases also need word boundaries.
    if alias.isascii():
        return re.search(r"\b" + re.escape(alias) + r"s?\b", text) is not None
    return re.search(
        r"(?<![가-힣a-z])" + re.escape(alias)
        + r"(?=$|[^가-힣a-z]|은|는|이|가|을|를|에|도|만|과|와|의|처럼|하고|이나|나)",
        text,
    ) is not None


def create_pdi_questions(htp_test: HtpTest, db: Session) -> List[HtpPdiInteraction]:
    """RAG + GPT 기반 PDI 질문 생성."""
    from app.services.openai_service import generate_json_answer
    from app.services.chroma_service import search_documents
    from app.core.config import CHROMA_HTP_COLLECTION
    import json

    # 기존 질문 삭제
    db.query(HtpPdiInteraction).filter(
        HtpPdiInteraction.htp_test_id == htp_test.id
    ).delete()

    visual = htp_test.visual_features_json or {}

    # YOLO 태그 기반 RAG 검색
    yolo_tags = []
    for key in ["house", "tree", "person"]:
        tags = visual.get(key, {}).get("tags", [])
        yolo_tags.extend(tags)

    query = " ".join(yolo_tags) + " PDI 심리신호 해석 질문"

    rag_results = search_documents(
        query=query,
        top_k=8,
        collection_name=CHROMA_HTP_COLLECTION,
    )
    rag_context = "\n\n".join(item.get("document", "") for item in rag_results)

    prompt = f"""
당신은 아동 심리 검사 전문가입니다. KHTP 그림 분석 결과를 바탕으로 PDI 질문을 생성하세요.

## 그림 분석 결과 (YOLO)
{json.dumps(visual, ensure_ascii=False)}

## HTP 지식 참고자료 (PDI 질문 예시 + 심리신호)
{rag_context}

## 질문 생성 규칙
1. 개인화 질문 (그림 분석 결과 보고 필요한 것만):
   - 참고자료의 심리신호와 PDI 질문을 참고해서 이 그림에 맞는 질문만 선택
   - 집/나무/사람 중 탐지되지 않은 요소가 있으면 왜 안 그렸는지
   - 사람이 여러 명이면 누구인지, 왜 여러 명인지
   - 그림의 특이사항이 있을 때만 질문, 없으면 최소화
   - 특이사항이 많은 요소는 질문을 더 많이, 특이사항 없는 요소는 줄이거나 생략
   - 질문은 공통 질문 포함 최대 10개까지만 생성

2. 질문 작성 규칙:
   - 아이에게 직접 물어볼 수 있는 자연스러운 한국어
   - **반드시 존댓말로 작성** (예: "~인가요?", "~해 주실래요?", "~어떤가요?")
   - 유도 질문 금지, 단정적 표현 금지
   - **탐지된 객체의 개수(숫자)를 절대 언급하지 말 것**
     - ❌ 잘못된 예: "열매가 7개 그려져 있는데, 어떤 의미인가요?"
     - ❌ 잘못된 예: "사람이 한 명만 그려져 있는데, 다른 가족은 왜 없나요?"
     - ❌ 잘못된 예: "창문이 두 개 있네요, 어떤 역할인가요?"
     - ✅ 올바른 예: "나무에 열매를 그려주셨네요. 어떤 의미인가요?"
     - ✅ 올바른 예: "사람을 그려주셨네요. 이 사람은 누구인가요?"
     - ✅ 올바른 예: "창문을 그려주셨네요. 어떤 역할을 한다고 생각하나요?"
   - 객체의 존재 여부만 언급하고, 수량·크기·위치 등 수치적 표현은 사용하지 말 것
   - missing_element 질문은 분석 결과가 detected=false 또는 count=0인 요소에만 만들 것
   - detected=true 또는 count>0인 요소를 없거나 그리지 않은 것으로 질문하지 말 것
   - 한 질문에 absent 요소와 present 요소를 섞어 둘 다 없다고 전제하지 말 것

## 출력 형식 (JSON만 응답)
{{
  "questions": [
    {{
      "target_type": "global/house/tree/person",
      "question_type": "drawing_time/missing_element/image_based/default_pdi",
      "question_text": "질문 내용",
      "reason": "이 질문을 하는 이유"
    }}
  ]
}}
""".strip()

    result = generate_json_answer(prompt)
    questions = result.get("questions", [])
    
    # drawing_time 타입 질문 제외 (별도 엔드포인트로 분리)
    questions = [q for q in questions if q.get("question_type") != "drawing_time"]
    questions = _filter_grounded_pdi_questions(questions, visual)

    interactions = []

    for idx, q in enumerate(questions):
        interaction = HtpPdiInteraction(
            htp_test_id=htp_test.id,
            round_no=1,
            sort_order=idx + 1,
            target_type=q.get("target_type", "global"),
            question_type=q.get("question_type", "default_pdi"),
            question_text=q.get("question_text", ""),
            reason=q.get("reason", ""),
        )
        db.add(interaction)
        interactions.append(interaction)

    htp_test.pdi_status = "accepted"
    htp_test.test_status = "waiting_pdi_answers"

    return interactions

def format_pdi_questions(interactions: List[HtpPdiInteraction]) -> list[dict]:
    return [
        {
            "question_id": interaction.id,
            "round_no": interaction.round_no,
            "sort_order": interaction.sort_order,
            "target_type": interaction.target_type,
            "question_type": interaction.question_type,
            "question_text": interaction.question_text,
            "reason": interaction.reason,
        }
        for interaction in sorted(interactions, key=lambda x: (x.round_no, x.sort_order))
    ]


def save_pdi_answers(
    htp_test: HtpTest,
    answers: list,
    db: Session,
) -> dict:
    """PDI 답변 저장.

    현재는 mock 흐름:
    - 답변 저장
    - 추가 질문 없이 바로 PDI 완료 처리

    추후 실제 구현:
    - GPT가 답변을 보고 추가 질문 필요 여부 판단
    - need_followup=True면 followup 질문 생성
    """
    question_ids = [item.question_id for item in answers]

    interactions = (
        db.query(HtpPdiInteraction)
        .filter(
            HtpPdiInteraction.htp_test_id == htp_test.id,
            HtpPdiInteraction.id.in_(question_ids),
        )
        .all()
    )

    interaction_map = {interaction.id: interaction for interaction in interactions}

    missing_ids = [qid for qid in question_ids if qid not in interaction_map]
    if missing_ids:
        return {
            "ok": False,
            "missing_ids": missing_ids,
        }

    now = datetime.utcnow()

    for answer in answers:
        interaction = interaction_map[answer.question_id]
        interaction.answer_text = answer.answer_text
        interaction.answered_at = now

    all_interactions = (
        db.query(HtpPdiInteraction)
        .filter(HtpPdiInteraction.htp_test_id == htp_test.id)
        .order_by(HtpPdiInteraction.round_no, HtpPdiInteraction.sort_order)
        .all()
    )

    answered_count = sum(1 for item in all_interactions if item.answer_text)

    htp_test.pdi_status = "completed"
    htp_test.test_status = "ready_to_generate_report"
    htp_test.pdi_summary_json = {
        "status": "completed",
        "answered_count": answered_count,
        "summary": "PDI 답변이 저장되었습니다. 추후 GPT 요약 결과로 교체 예정입니다.",
    }

    return {
        "ok": True,
        "saved_count": len(answers),
        "answered_count": answered_count,
        "need_followup": False,
        "followup_questions": [],
    }


def skip_pdi(htp_test: HtpTest) -> None:
    htp_test.pdi_status = "skipped"
    htp_test.test_status = "ready_to_generate_report"
    htp_test.pdi_summary_json = {
        "status": "skipped",
        "answered_count": 0,
        "summary": "이번 리포트는 아이의 추가 답변 없이 이미지 분석 결과를 중심으로 작성됩니다.",
    }
