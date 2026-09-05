from datetime import date
import re
from app.models.htp_pdi import HtpPdiInteraction
from app.models.htp_test import HtpTest
from app.services.openai_service import generate_json_answer
from app.services.htp_rag_service import search_htp_knowledge_for_report


def _iter_report_text(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_report_text(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_report_text(item)


def _has_positive_relation_claim(text: str, left: str, right: str, terms: tuple[str, ...]) -> bool:
    for sentence in text.replace("\n", ".").split("."):
        if left not in sentence or right not in sentence:
            continue
        if not any(term in sentence for term in terms):
            continue
        if any(negative in sentence for negative in ("않", "아니", "없", "떨어", "분리")):
            continue
        return True
    return False


def _assert_report_grounding(report_json: dict, visual: dict) -> None:
    """Reject reports containing directly checkable contradictions or invented states."""
    report_text = "\n".join(_iter_report_text(report_json))
    door = visual.get("house", {}).get("parts", {}).get("door", {})
    if "state" not in door:
        unsupported_door_states = (
            "열린 문", "닫힌 문", "문이 열", "문은 열", "문이 닫", "문은 닫",
            "개방된 문", "문이 개방", "open door", "door is open", "closed door",
        )
        for term in unsupported_door_states:
            for match in re.finditer(re.escape(term), report_text.lower()):
                clause = re.split(r"[.!?\n]|지만", report_text[match.start():], maxsplit=1)[0]
                # An explicit unknown statement does not assert an open/closed door.
                if re.search(r"(?:는지|여부|인지).*?(?:알 수 없|확인할 수 없|확인되지 않|정보가 없|정보는 없|정보가 제공되지 않)", clause):
                    continue
                raise ValueError("report invented an unsupported door state")

    relation_names = {
        "house_tree": ("집", "나무"),
        "house_person": ("집", "사람"),
        "tree_person": ("나무", "사람"),
    }
    # Contradictions can also appear in summary, tabs, or recommendations.
    relation_text = report_text
    relationships = visual.get("relationships", {})
    for key, (left, right) in relation_names.items():
        relation = relationships.get(key, {})
        if relation.get("touching") is False and _has_positive_relation_claim(
            relation_text, left, right, ("접촉", "맞닿", "밀착", "붙어")
        ):
            raise ValueError(f"report contradicted {key}.touching=false")
        if relation.get("overlap") is False and _has_positive_relation_claim(
            relation_text, left, right, ("겹쳐", "겹침", "중첩")
        ):
            raise ValueError(f"report contradicted {key}.overlap=false")


def build_pdi_evidence(pdi_interactions: list[HtpPdiInteraction]) -> list[dict]:
    return [
        {
            "question": item.question_text,
            "answer": item.answer_text,
            "target_type": item.target_type,
        }
        for item in pdi_interactions
        if item.answer_text
    ]


def build_rag_summary(retrieved_knowledge: list[dict]) -> dict:
    """report_json에 저장할 RAG 검색 결과 요약."""
    return {
        "collection": "htp_knowledge",
        "retrieved_count": len(retrieved_knowledge),
        "top_chunks": [
            {
                "id": item.get("id"),
                "title": item.get("metadata", {}).get("title"),
                "section": item.get("metadata", {}).get("section"),
                "subsection": item.get("metadata", {}).get("subsection"),
                "distance": item.get("distance"),
            }
            for item in retrieved_knowledge[:5]
        ],
    }


def create_mock_htp_report(
    htp_test: HtpTest,
    pdi_interactions: list[HtpPdiInteraction],
    retrieved_knowledge: list[dict] | None = None,
) -> dict:
    """개발 테스트용 HTP 리포트 생성.

    추후 실제 구현에서는:
    1. visual_features_json + PDI 답변 기반 RAG query 생성
    2. htp_knowledge collection 검색
    3. GPT로 structured report_json 생성
    """
    retrieved_knowledge = retrieved_knowledge or []

    pdi_used = htp_test.pdi_status == "completed"
    analysis_mode = "with_pdi" if pdi_used else "without_pdi"
    confidence_level = "medium" if pdi_used else "low"

    pdi_evidence = build_pdi_evidence(pdi_interactions)

    if pdi_used:
        one_line_summary = "아이의 그림 특징과 추가 답변을 함께 고려하여 조심스럽게 분석했습니다."
        pdi_notice = "PDI 답변이 리포트에 함께 반영되었습니다."
    else:
        one_line_summary = "아이의 추가 답변 없이 그림에서 관찰 가능한 특징을 중심으로 분석했습니다."
        pdi_notice = "PDI를 진행하지 않아 이미지 분석 결과 중심으로 작성되었습니다."

    report_json = {
        "summary": {
            "title": "HTP 그림 분석 결과",
            "one_line_summary": one_line_summary,
            "main_emotion": "조심스러움",
            "risk_level": "관찰 필요",
            "analysis_mode": analysis_mode,
            "pdi_used": pdi_used,
            "confidence_level": confidence_level,
            "disclaimer": "본 리포트는 전문 진단이 아닌 참고용 안내입니다.",
        },
        "pdi": {
            "status": htp_test.pdi_status,
            "interactions_count": len(pdi_evidence),
            "summary": pdi_notice,
        },
        "rag": build_rag_summary(retrieved_knowledge),
        "visualization": {
            "image_path": htp_test.result_image_path,
            "display_bboxes": (
                htp_test.yolo_result_json.get("display_detections", [])
                if htp_test.yolo_result_json
                else []
            ),
        },
        "tabs": {
            "house": {
                "label": "집",
                "status": "보통",
                "observations": [
                    "집이 탐지되었습니다.",
                    "창문이 일부 표현되어 있으며, 문은 뚜렷하게 탐지되지 않았습니다.",
                ],
                "pdi_evidence": [
                    item for item in pdi_evidence if item["target_type"] == "house"
                ],
                "interpretation": (
                    "집은 가족관계와 생활 환경에 대한 인식을 살펴볼 때 참고할 수 있습니다. "
                    "문이 뚜렷하지 않은 점은 아이의 설명과 함께 확인하는 것이 좋습니다."
                ),
                "positive_note": "집의 전체 구조가 표현되어 있어 생활 환경에 대한 기본적인 표현은 확인됩니다.",
                "tags": ["집", "창문", "문미탐지", "가족관계"],
            },
            "tree": {
                "label": "나무",
                "status": "관찰 필요",
                "observations": [
                    "나무가 탐지되었습니다.",
                    "기둥과 수관은 표현되어 있으나 뿌리는 뚜렷하게 탐지되지 않았습니다.",
                ],
                "pdi_evidence": [
                    item for item in pdi_evidence if item["target_type"] == "tree"
                ],
                "interpretation": (
                    "나무는 자기상과 성장감을 참고하는 요소입니다. "
                    "뿌리 표현 부족은 연령과 발달단계를 함께 고려하여 조심스럽게 해석해야 합니다."
                ),
                "positive_note": "기둥과 수관이 표현되어 있어 기본적인 구조화 능력은 확인됩니다.",
                "tags": ["나무", "뿌리미탐지", "자기상"],
            },
            "person": {
                "label": "사람",
                "status": "관찰 필요",
                "observations": [
                    "사람이 비교적 작게 탐지되었습니다.",
                    "손과 발의 세부 표현은 약하게 나타납니다.",
                ],
                "pdi_evidence": [
                    item for item in pdi_evidence if item["target_type"] == "person"
                ],
                "interpretation": (
                    "사람 그림은 자기개념과 대인관계 인식을 참고하는 요소입니다. "
                    "작은 크기와 세부 표현 부족은 단정하지 않고 아이의 답변이나 생활 맥락과 함께 살펴보는 것이 좋습니다."
                ),
                "positive_note": "사람의 기본 구조는 표현되어 있어 자기표현의 기본 틀은 확인됩니다.",
                "tags": ["사람", "작은크기", "손발세부표현부족", "자기표상"],
            },
        },
        "relationship_analysis": {
            "observations": [
                "집, 나무, 사람은 한 화면 안에 함께 배치되어 있습니다.",
                "세 요소가 직접 겹치거나 강하게 밀착된 형태는 뚜렷하지 않습니다.",
            ],
            "interpretation": (
                "요소 간 거리는 가족 환경, 자기상, 대인관계 표상이 어떻게 함께 배치되는지를 "
                "참고하는 보조 정보입니다."
            ),
        },
        "recommendations": [
            {
                "title": "그림 속 이야기를 물어보기",
                "description": "아이에게 그림 속 집, 나무, 사람에 대해 편안하게 이야기할 기회를 주세요.",
            },
            {
                "title": "1~2주간 일상 관찰하기",
                "description": "최근 아이가 자기표현을 어려워하거나 혼자 있으려는 시간이 늘었는지 부드럽게 관찰해보세요.",
            },
            {
                "title": "전문 상담 고려",
                "description": "걱정되는 변화가 지속되면 아동 심리 전문가와 상담해보는 것을 권장합니다.",
            },
        ],
        "safety_notice": (
            "본 리포트는 HTP 그림 검사와 AI 분석을 바탕으로 한 참고용 안내이며, "
            "전문적인 심리 진단을 대체하지 않습니다."
        ),
    }

    return report_json

def generate_htp_report(
    htp_test: HtpTest,
    pdi_interactions: list[HtpPdiInteraction],
    retrieved_knowledge: list[dict],
) -> dict:
    """RAG + GPT 기반 실제 HTP 리포트 생성."""

    pdi_evidence = build_pdi_evidence(pdi_interactions)
    rag_summary = build_rag_summary(retrieved_knowledge)

    rag_context = "\n\n".join(
        item.get("document", "") for item in retrieved_knowledge
    )

    pdi_text = "\n".join(
        f"[{qa['target_type']}] Q: {qa['question']} / A: {qa['answer']}"
        for qa in pdi_evidence
    ) or "PDI 응답 없음"

    visual = htp_test.visual_features_json or {}

    child = htp_test.child
    child_context = {
        "birth_year": child.birth_year if child else None,
        "age_by_year": (
            date.today().year - child.birth_year
            if child
            else None
        ),
        "gender": child.gender if child else None,
    }

    prompt = f"""
당신은 아동 심리 검사 전문가입니다. KHTP 검사 결과를 바탕으로 보호자용 리포트를 작성하세요.

## 아동 정보
{child_context}

## 그림 및 그리기 과정 분석 결과
{visual}

## PDI 응답
{pdi_text}

## HTP 지식 참고자료
{rag_context}

## 작성 규칙

- 반드시 아래 JSON 형식으로만 응답할 것
- 보호자가 이해하기 쉬운 언어로 작성할 것
- 단정적인 진단을 금지하고 가능성·경향성·관찰 수준의 표현을 사용할 것
- detected는 해당 요소의 존재만 뜻하며, 열림/닫힘·방향·표정·접촉 상태를 뜻하지 않음
- 문이 detected=true여도 open/closed 필드가 없으면 문이 열렸거나 닫혔다고 쓰지 말 것
- relationships의 touching/overlap이 false이면 접촉·맞닿음·밀착·겹침이 있다고 쓰지 말 것
- 단일 visual feature만으로 심리 상태나 공간 상태를 사실처럼 단정하지 말 것
- summary와 positive_note에도 같은 근거 규칙을 적용할 것. 신체 부위의 존재나 배치만으로
  자기인식이 잘 형성됨, 환경 인식이 명확함, 심리적으로 안정적임을 결론 내리지 말 것
- PDI 응답이나 생활 맥락이 없으면 main_emotion은 '확인 어려움'으로 작성하고,
  positive_note는 실제로 확인된 그림 표현만 설명할 것
- RAG 자료가 없으면 부위의 존재·부재를 심리적 상징으로 연결하지 말고,
  interpretation에는 관찰의 한계와 아이에게 확인할 내용을 작성할 것

### 관찰 결과와 참고자료 구분

- 그림에 관한 관찰 사실은 반드시 '그림 및 그리기 과정 분석 결과'에 명시적으로 제공된 필드와 값만 사용할 것
- 분석 결과에 제공되지 않은 특징의 존재·부재·형태를 추측하거나 언급하지 말 것
- ground_line 등 특정 특징의 분석 필드가 제공되지 않은 경우 해당 특징의 존재·부재·형태를 언급하거나 해석하지 말 것
- HTP 지식 참고자료는 분석 결과에 명시된 특징의 해석을 보조하는 용도로만 사용할 것
- HTP 지식 참고자료에 등장한다는 이유만으로 해당 특징이 실제 그림에 존재한다고 가정하거나 관찰 사실처럼 작성하지 말 것
- 원본 이미지를 직접 확인한 것처럼 분석 결과에 없는 내용을 만들어내지 말 것

### 그리기 과정 데이터

- drawing_process는 그림 전체의 과정 데이터이므로 house, tree, person 중 특정 요소나 부위의 특징으로 연결하지 말고 summary에 종합적으로 반영할 것
- drawing_process.available=true이면 그리기 시간과 전체 공간 사용을 summary.one_line_summary에 관찰 수준으로 자연스럽게 반영할 것
- drawing_process.available=false이면 그리기 시간, 좌표, 필압 등 그리기 과정에 관한 내용을 언급하지 말 것
- drawing_process.pressure.available=true일 때만 필압을 언급할 것
- drawing_process.pressure.available=true이면 실제 데이터로 확인되는 필압의 측정 여부와 그림 내부의 변화만 summary.one_line_summary에 관찰 수준으로 반영할 것
- 브러시 굵기를 필압으로 해석하지 말 것
- pressure.mean, min, max, stddev는 기기별 차이가 있는 원시 측정값이므로 평균값만으로 강함·중간·약함을 분류하지 말 것
- 검증된 필압 분류값이 별도로 제공되지 않으면 필압은 측정되었다는 사실과 그림 내부에서 나타난 변화만 설명할 것
- 검증된 시간 분류값이 제공되지 않으면 그리기 시간을 적절함·짧음·긺으로 임의 분류하지 말 것
- 그리기 시간은 관찰 사실로만 표현하고 단독으로 심리 상태를 해석하지 말 것
- 필압·좌표·시간만으로 아동의 심리 상태나 태도를 단정하거나 추론하지 말 것
- 전체 과정 데이터를 특정 집·나무·사람 요소에서 발생한 특징으로 단정하지 말 것
- 원시 수치를 나열하기보다 보호자가 이해할 수 있는 관찰 문장으로 설명할 것

### 아동 정보와 발달단계

- 아동 정보의 age_by_year와 gender를 발달단계 해석에 반영할 것
- birth_year만으로 계산된 age_by_year는 정확한 만 나이가 아닌 연도 기준 나이임을 고려할 것
- 제공된 나이와 맞지 않는 발달단계 설명을 적용하지 말 것
- 성별만으로 성격이나 심리 상태를 단정하지 말 것

## 출력 형식
{{
  "summary": {{
    "title": "HTP 그림 분석 결과",
    "one_line_summary": "전체 요약 1문장",
    "main_emotion": "주요 감정 키워드",
    "risk_level": "낮음/관찰 필요/주의",
    "analysis_mode": "with_pdi 또는 without_pdi",
    "pdi_used": true,
    "confidence_level": "low/medium/high",
    "disclaimer": "본 리포트는 전문 진단이 아닌 참고용 안내입니다."
  }},
  "tabs": {{
    "house": {{
      "label": "집",
      "status": "보통/관찰 필요/주의",
      "observations": ["관찰 사항1", "관찰 사항2"],
      "interpretation": "해석",
      "positive_note": "긍정적 관찰",
      "tags": ["태그1", "태그2"]
    }},
    "tree": {{
      "label": "나무",
      "status": "보통/관찰 필요/주의",
      "observations": ["관찰 사항1"],
      "interpretation": "해석",
      "positive_note": "긍정적 관찰",
      "tags": ["태그1"]
    }},
    "person": {{
      "label": "사람",
      "status": "보통/관찰 필요/주의",
      "observations": ["관찰 사항1"],
      "interpretation": "해석",
      "positive_note": "긍정적 관찰",
      "tags": ["태그1"]
    }}
  }},
  "relationship_analysis": {{
    "observations": ["관찰 사항1"],
    "interpretation": "해석"
  }},
  "recommendations": [
    {{"title": "제목", "description": "설명"}}
  ],
  "safety_notice": "본 리포트는 참고용이며 전문 진단을 대체하지 않습니다."
}}
""".strip()

    prompt += """

최종 출력 전 각 문장을 입력과 대조하세요. 위 참고자료보다 다음 근거 규칙이 우선합니다.
- 객체마다 size/position 값이 다르므로 여러 객체가 모두 같은 크기·위치라고 요약하지 마세요.
- summary.one_line_summary는 요소의 존재와 PDI 확인 여부를 중심으로 쓰고 객체 크기를 나열하지 마세요.
- 미측정 필드는 unknown입니다. 정보가 없다는 이유로 부정적 신호가 없다고 결론 내리지 마세요.
- positive_note는 '어떤 부위가 표현되었다' 수준의 관찰만 쓰세요. 인지·신체 인식·자기표상이
  형성되었다거나 능력을 갖추었다는 추론은 쓰지 마세요.
- PDI나 생활 맥락이 없는 경우 아동 개인의 심리·발달 상태를 그림 부위에 연결하지 마세요.
  RAG의 일반 상징은 이 아동에 대한 사실이 아닙니다. 확인할 질문과 해석의 한계를 쓰세요.
- age_by_year가 null이면 미취학/학령기 등 특정 발달단계를 이 아동의 특징에 적용하지 마세요.
- 문 탐지는 열림·닫힘이 아닙니다. touching=false, overlap=false와 모순되는 문장을 쓰지 마세요.
"""
    report_json = generate_json_answer(prompt)
    _assert_report_grounding(report_json, visual)

    report_json["pdi"] = {
        "status": htp_test.pdi_status,
        "interactions_count": len(pdi_evidence),
        "summary": "PDI 답변이 반영되었습니다." if pdi_evidence else "PDI 없이 이미지 분석 중심으로 작성되었습니다.",
    }
    report_json["rag"] = rag_summary
    report_json["visualization"] = {
        "image_path": htp_test.result_image_path,
        "display_bboxes": (
            htp_test.yolo_result_json.get("display_detections", [])
            if htp_test.yolo_result_json
            else []
        ),
    }

    return report_json

def apply_report_to_test(htp_test: HtpTest, report_json: dict) -> None:
    """생성된 report_json을 htp_tests row에 반영."""
    htp_test.test_status = "completed"
    htp_test.summary_text = report_json["summary"]["one_line_summary"]
    htp_test.main_emotion = report_json["summary"]["main_emotion"]
    htp_test.report_text = report_json["summary"]["one_line_summary"]
    htp_test.report_json = report_json
    htp_test.recommendations_json = report_json["recommendations"]
