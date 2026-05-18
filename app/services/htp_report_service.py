from app.models.htp_pdi import HtpPdiInteraction
from app.models.htp_test import HtpTest
from app.services.openai_service import generate_json_answer
from app.services.htp_rag_service import search_htp_knowledge_for_report


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

    prompt = f"""
당신은 아동 심리 검사 전문가입니다. KHTP 검사 결과를 바탕으로 보호자용 리포트를 작성하세요.

## 그림 분석 결과 (YOLO)
{visual}

## PDI 응답
{pdi_text}

## HTP 지식 참고자료
{rag_context}

## 작성 규칙
- 단정적 진단 금지, 가능성/경향성 언어 사용
- 보호자가 이해할 수 있는 언어로 작성
- 반드시 아래 JSON 형식으로만 응답

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

    report_json = generate_json_answer(prompt)

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
    htp_test.report_text = "개발 테스트용 HTP 분석 리포트입니다. 추후 GPT/RAG 결과로 교체 예정입니다."
    htp_test.report_json = report_json
    htp_test.recommendations_json = report_json["recommendations"]