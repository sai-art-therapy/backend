from app.services.chroma_service import search_documents
from app.services.openai_service import generate_answer
from app.services.report_service import get_report_context
from app.core.prompts import SYSTEM_PROMPT, ANSWER_FORMAT


def format_search_results(results: list[dict]) -> str:
    """
    ChromaDB 검색 결과를 GPT prompt에 넣기 좋은 텍스트로 변환한다.
    """
    blocks = []

    for idx, item in enumerate(results, start=1):
        metadata = item["metadata"]

        block = f"""
[검색 결과 {idx}]
guide_id: {metadata.get("guide_id")}
분류: {metadata.get("category")} > {metadata.get("subcategory")}
연령 범위: {metadata.get("age_range")}
근거 수준: {metadata.get("evidence_level")}
출처: {metadata.get("display_sources")}
라이선스: {metadata.get("licenses")}

내용:
{item["document"]}
""".strip()

        blocks.append(block)

    return "\n\n".join(blocks)


def build_sources(results: list[dict]) -> list[dict]:
    """
    프론트엔드에 표시할 출처 정보를 정리한다.
    """
    sources = []

    for item in results:
        metadata = item["metadata"]

        sources.append({
            "guide_id": metadata.get("guide_id", ""),
            "category": metadata.get("category", ""),
            "subcategory": metadata.get("subcategory", ""),
            "display_sources": metadata.get("display_sources", ""),
            "source_urls": metadata.get("source_urls", ""),
            "licenses": metadata.get("licenses", ""),
            "usage_decisions": metadata.get("usage_decisions", ""),
        })

    return sources


def answer_with_rag(message: str, report_id: str | None = None) -> dict:
    """
    사용자 질문을 받아서:
    1. ChromaDB 검색
    2. HTP 리포트 context 조회
    3. GPT prompt 생성
    4. 답변 반환
    """
    search_results = search_documents(query=message, top_k=4)

    if not search_results:
        return {
            "answer": "현재 구축된 육아 가이드 데이터셋 기준으로는 충분한 근거를 찾지 못했습니다. 질문을 조금 더 구체적으로 작성해 주세요.",
            "sources": [],
            "safety_notice": "본 답변은 전문 심리 진단이나 치료를 대체하지 않습니다."
        }

    guide_context = format_search_results(search_results)
    report_context = get_report_context(report_id)

    prompt = f"""
{SYSTEM_PROMPT}

{ANSWER_FORMAT}

[HTP 리포트 참고 정보]
{report_context}

[검색된 육아 가이드]
{guide_context}

[사용자 질문]
{message}

위 자료만 근거로 답변해 주세요.
""".strip()

    answer = generate_answer(prompt)

    return {
        "answer": answer,
        "sources": build_sources(search_results),
        "safety_notice": "본 답변은 전문 심리 진단이나 치료를 대체하지 않으며, 아이의 상태가 지속적으로 걱정되거나 위험 신호가 보이면 전문가 상담을 권장합니다."
    }