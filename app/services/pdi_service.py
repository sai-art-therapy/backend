from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from app.models.htp_pdi import HtpPdiInteraction
from app.models.htp_test import HtpTest


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
   - 유도 질문 금지, 단정적 표현 금지

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
