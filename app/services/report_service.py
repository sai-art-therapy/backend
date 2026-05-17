from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.htp_test import HtpTest


def _safe_get(data: dict | None, key: str, default: Any = None) -> Any:
    """
    dict에서 안전하게 값을 꺼내기 위한 작은 helper.
    report_json 내부 key가 없거나 None이어도 에러가 나지 않게 한다.
    """
    if not isinstance(data, dict):
        return default

    return data.get(key, default)


def _format_tab_context(tab_name: str, tab_data: dict | None) -> str:
    """
    report_json["tabs"]["house/tree/person"] 구조를 상담용 짧은 문장으로 변환한다.
    """
    if not isinstance(tab_data, dict):
        return f"- {tab_name}: 정보 없음"

    label = tab_data.get("label", tab_name)
    status = tab_data.get("status", "정보 없음")
    tags = tab_data.get("tags", [])
    observations = tab_data.get("observations", [])
    interpretation = tab_data.get("interpretation", "")
    positive_note = tab_data.get("positive_note", "")

    lines = [
        f"- {label}",
        f"  - 상태: {status}",
    ]

    if tags:
        lines.append(f"  - 관련 키워드: {', '.join(map(str, tags))}")

    if observations:
        observation_text = " / ".join(map(str, observations[:3]))
        lines.append(f"  - 관찰 내용: {observation_text}")

    if positive_note:
        lines.append(f"  - 긍정적 참고점: {positive_note}")

    if interpretation:
        lines.append(f"  - 해석 참고: {interpretation}")

    return "\n".join(lines)


def _format_recommendations(recommendations: list | None) -> str:
    """
    report_json["recommendations"]를 상담용 짧은 목록으로 변환한다.
    """
    if not recommendations:
        return "- 리포트 기반 추천 없음"

    lines = []

    for item in recommendations[:3]:
        if not isinstance(item, dict):
            continue

        title = item.get("title", "")
        description = item.get("description", "")

        if title and description:
            lines.append(f"- {title}: {description}")
        elif title:
            lines.append(f"- {title}")
        elif description:
            lines.append(f"- {description}")

    if not lines:
        return "- 리포트 기반 추천 없음"

    return "\n".join(lines)


def build_htp_report_context(report_json: dict | None) -> str:
    """
    HTP report_json 전체를 GPT에 넣지 않고,
    육아 상담 챗봇이 참고할 수 있는 핵심 정보만 짧게 정리한다.

    목적:
    - 컨텍스트 길이 절약
    - HTP 해석을 단정하지 않도록 안전 문구 포함
    - parenting RAG와 역할 분리
    """
    if not isinstance(report_json, dict):
        return "연결된 HTP 리포트가 아직 생성되지 않았습니다."

    summary = _safe_get(report_json, "summary", {})
    tabs = _safe_get(report_json, "tabs", {})
    recommendations = _safe_get(report_json, "recommendations", [])
    relationship_analysis = _safe_get(report_json, "relationship_analysis", {})
    safety_notice = report_json.get(
        "safety_notice",
        "본 리포트는 전문 진단이 아닌 참고용 안내입니다.",
    )

    title = _safe_get(summary, "title", "HTP 그림 분석 결과")
    one_line_summary = _safe_get(summary, "one_line_summary", "")
    main_emotion = _safe_get(summary, "main_emotion", "정보 없음")
    risk_level = _safe_get(summary, "risk_level", "정보 없음")
    confidence_level = _safe_get(summary, "confidence_level", "정보 없음")
    pdi_used = _safe_get(summary, "pdi_used", False)
    disclaimer = _safe_get(summary, "disclaimer", safety_notice)

    house_context = _format_tab_context("집", _safe_get(tabs, "house", {}))
    tree_context = _format_tab_context("나무", _safe_get(tabs, "tree", {}))
    person_context = _format_tab_context("사람", _safe_get(tabs, "person", {}))
    recommendation_context = _format_recommendations(recommendations)

    relationship_observations = _safe_get(relationship_analysis, "observations", [])
    relationship_interpretation = _safe_get(relationship_analysis, "interpretation", "")

    relationship_lines = []

    if relationship_observations:
        relationship_lines.append(
            "- 관찰 내용: " + " / ".join(map(str, relationship_observations[:3]))
        )

    if relationship_interpretation:
        relationship_lines.append(f"- 해석 참고: {relationship_interpretation}")

    if not relationship_lines:
        relationship_lines.append("- 관계 분석 정보 없음")

    pdi_text = "반영됨" if pdi_used else "반영되지 않음"

    return f"""
[HTP 리포트 참고 정보]
- 리포트 제목: {title}
- 한 줄 요약: {one_line_summary or "요약 정보 없음"}
- 주요 정서 키워드: {main_emotion}
- 관찰 수준: {risk_level}
- 신뢰도: {confidence_level}
- PDI 답변 반영 여부: {pdi_text}
- 주의 문구: {disclaimer}

[그림 요소별 참고 정보]
{house_context}

{tree_context}

{person_context}

[요소 간 관계 참고 정보]
{chr(10).join(relationship_lines)}

[리포트 기반 추천]
{recommendation_context}

[안전 안내]
{safety_notice}

주의:
- 위 내용은 아이의 상태를 단정하기 위한 정보가 아니라, 부모 상담 답변에서 조심스럽게 참고하기 위한 보조 정보입니다.
- 답변에서는 "불안하다", "문제가 있다"처럼 단정하지 말고 "그럴 가능성을 조심스럽게 살펴볼 수 있다" 정도로 표현해야 합니다.
""".strip()


def get_report_context(
    report_id: str | int | None,
    db: Optional[Session] = None,
    user_id: Optional[int] = None,
) -> str:
    """
    report_id로 HTP 리포트를 조회하고, 챗봇 상담용 context 문자열을 반환한다.

    - report_id가 없으면 일반 상담방으로 판단한다.
    - db가 없으면 기존 코드 호환을 위해 안내 문구만 반환한다.
    - user_id가 있으면 해당 사용자의 리포트만 조회한다.
    """
    if not report_id:
        return "연결된 HTP 리포트 없음"

    if db is None:
        return "HTP 리포트 조회를 위한 DB 세션이 전달되지 않았습니다."

    try:
        report_id_int = int(report_id)
    except (TypeError, ValueError):
        return "올바르지 않은 HTP 리포트 ID입니다."

    query = db.query(HtpTest).filter(HtpTest.id == report_id_int)

    if user_id is not None:
        query = query.filter(HtpTest.user_id == user_id)

    htp_test = query.first()

    if htp_test is None:
        return "연결된 HTP 리포트를 찾을 수 없습니다."

    if not htp_test.report_json:
        return "연결된 HTP 리포트가 아직 생성되지 않았습니다."

    return build_htp_report_context(htp_test.report_json)