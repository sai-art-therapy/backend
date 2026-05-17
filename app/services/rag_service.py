from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import CHROMA_PARENTING_COLLECTION
from app.core.prompts import ANSWER_FORMAT, SYSTEM_PROMPT
from app.services.chroma_service import search_documents
from app.services.openai_service import generate_answer
from app.services.report_service import get_report_context


def format_search_results(results: list[dict]) -> str:
    """
    ChromaDB 검색 결과를 GPT prompt에 넣기 좋은 텍스트로 변환한다.
    parenting RAG 문서만 이 함수에서 다룬다.
    """
    blocks = []

    for idx, item in enumerate(results, start=1):
        metadata = item.get("metadata", {})

        block = f"""
[육아 가이드 {idx}]
guide_id: {metadata.get("guide_id")}
분류: {metadata.get("category")} > {metadata.get("subcategory")}
연령 범위: {metadata.get("age_range")}
근거 수준: {metadata.get("evidence_level")}
출처: {metadata.get("display_sources")}
라이선스: {metadata.get("licenses")}

내용:
{item.get("document", "")}
""".strip()

        blocks.append(block)

    return "\n\n".join(blocks)


def build_sources(results: list[dict]) -> list[dict]:
    """
    프론트엔드에 표시할 출처 정보를 정리한다.
    """
    sources = []

    for item in results:
        metadata = item.get("metadata", {})

        sources.append(
            {
                "guide_id": metadata.get("guide_id", ""),
                "category": metadata.get("category", ""),
                "subcategory": metadata.get("subcategory", ""),
                "display_sources": metadata.get("display_sources", ""),
                "source_urls": metadata.get("source_urls", ""),
                "licenses": metadata.get("licenses", ""),
                "usage_decisions": metadata.get("usage_decisions", ""),
            }
        )

    return sources


def format_chat_history(chat_history: Optional[list[dict]]) -> str:
    """
    같은 채팅방의 최근 대화 내용을 GPT prompt에 넣기 좋은 형태로 변환한다.
    """
    if not chat_history:
        return "이전 대화 없음"

    lines = []

    for message in chat_history:
        role = message.get("role", "")
        content = message.get("content", "")

        if not content:
            continue

        if role == "user":
            speaker = "부모"
        elif role == "assistant":
            speaker = "상담 챗봇"
        else:
            speaker = role or "unknown"

        lines.append(f"- {speaker}: {content}")

    if not lines:
        return "이전 대화 없음"

    return "\n".join(lines)


def answer_with_rag(
    message: str,
    db: Session,
    report_id: str | int | None = None,
    user_id: int | None = None,
    chat_history: Optional[list[dict]] = None,
) -> dict:
    """
    사용자 질문을 받아서 육아 상담 답변을 생성한다.

    사용하는 context:
    1. parenting RAG 검색 결과
    2. HTP 리포트 참고 정보, report_id가 있을 때만
    3. 같은 채팅방의 최근 대화 history
    4. 현재 사용자 질문
    """
    search_results = search_documents(
        query=message,
        top_k=3,
        collection_name=CHROMA_PARENTING_COLLECTION,
    )

    if not search_results:
        return {
            "answer": (
                "질문과 직접 연결되는 육아 가이드 근거를 충분히 찾지 못했어요. "
                "상황을 조금 더 구체적으로 알려주시면 아이에게 어떤 반응을 해볼 수 있을지 더 잘 안내해드릴게요."
            ),
            "sources": [],
            "safety_notice": "본 답변은 전문 심리 진단이나 치료를 대체하지 않습니다.",
        }

    guide_context = format_search_results(search_results)
    report_context = get_report_context(
        report_id=report_id,
        db=db,
        user_id=user_id,
    )
    history_context = format_chat_history(chat_history)

    has_history = bool(chat_history)
    response_length_rule = (
        "이번 질문은 이전 대화가 있는 후속 질문입니다. 이전 답변을 반복하지 말고, 1~2문단으로 짧게 답하세요."
        if has_history
        else "이번 질문은 상담의 첫 질문에 가깝습니다. 그래도 2~4문단 안에서 간결하게 답하세요."
    )

    prompt = f"""
{SYSTEM_PROMPT}

{ANSWER_FORMAT}

[HTP 리포트 참고 정보]
{report_context}

[검색된 육아 가이드]
{guide_context}

[이전 대화]
{history_context}

[현재 부모 질문]
{message}

이번 답변 길이 규칙:
- {response_length_rule}

답변 작성 지침:
- [검색된 육아 가이드]를 주된 근거로 사용하세요.
- [HTP 리포트 참고 정보]는 report_id가 있을 때만 보조 참고로 사용하세요.
- HTP 리포트 내용을 아이의 심리 상태로 단정하지 마세요.
- [이전 대화]가 있으면 같은 말을 반복하지 말고 자연스럽게 이어서 답하세요.
- 부모를 비난하지 말고, 오늘 바로 해볼 수 있는 행동 중심으로 답하세요.
- 같은 내용을 문단과 bullet로 중복해서 반복하지 마세요.
- 행동 가이드는 한 답변에 2~3개까지만 제안하세요.
- safety_notice는 API 응답 필드로 따로 제공됩니다. 따라서 answer 본문 마지막에 "전문 진단이 아닌 참고용 안내입니다" 같은 고정 문구를 매번 붙이지 마세요.
- 다만 HTP 리포트를 언급할 때는 "리포트는 참고용으로만 봐주세요" 정도를 문장 안에 자연스럽게 포함할 수 있습니다.
- 위험 신호가 있거나 문제가 오래 지속될 가능성이 있을 때만 전문가 상담을 자연스럽게 권유하세요.
""".strip()

    answer = generate_answer(prompt)

    return {
        "answer": answer,
        "sources": build_sources(search_results),
        "safety_notice": (
            "본 답변은 전문 심리 진단이나 치료를 대체하지 않으며, "
            "아이의 상태가 지속적으로 걱정되거나 위험 신호가 보이면 전문가 상담을 권장합니다."
        ),
    }