import json
from pathlib import Path

from app.services.chroma_service import add_documents, reset_collection
from app.services.source_service import (
    build_display_sources,
    build_source_urls,
    build_licenses,
    build_usage_decisions,
)

GUIDE_PATH = Path("app/data/rag/parenting_chatbot/parenting_guides.json")


def safe_text(value):
    """
    ChromaDB document/metadata에 넣기 위해 값을 안전하게 문자열로 변환한다.
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(map(str, value))
    return str(value)


def build_document(item: dict) -> str:
    """
    parenting_guides.json의 객체 1개를 RAG 검색용 document 텍스트로 변환한다.
    """
    return f"""
[분류]
{safe_text(item.get("category"))} > {safe_text(item.get("subcategory"))}

[아이 상태]
{safe_text(item.get("child_state"))}

[부모 고민]
{safe_text(item.get("parent_concern"))}

[상황]
{safe_text(item.get("situation"))}

[부모 목표]
{safe_text(item.get("parent_goal"))}

[권장 반응]
{safe_text(item.get("recommended_response"))}

[피해야 할 반응]
{safe_text(item.get("avoid_response"))}

[부모 대화 예시]
{safe_text(item.get("parent_script_example"))}

[실천 방법]
{safe_text(item.get("practical_action"))}

[관찰 포인트]
{safe_text(item.get("observation_points"))}

[관찰 기간]
{safe_text(item.get("observation_duration"))}

[경고 신호]
{safe_text(item.get("warning_signs"))}

[전문기관 안내]
{safe_text(item.get("referral_guide"))}

[키워드]
{safe_text(item.get("keywords"))}
""".strip()


def build_metadata(item: dict) -> dict:
    """
    검색 결과 표시, 출처 표시, 필터링에 사용할 metadata를 만든다.
    ChromaDB metadata에는 문자열, 숫자, bool 같은 단순 타입만 넣는 것이 안전하다.
    """
    source_ids = item.get("source_ids", [])

    return {
        "guide_id": safe_text(item.get("id")),
        "category": safe_text(item.get("category")),
        "subcategory": safe_text(item.get("subcategory")),
        "source_ids": safe_text(source_ids),
        "display_sources": build_display_sources(source_ids),
        "source_urls": build_source_urls(source_ids),
        "licenses": build_licenses(source_ids),
        "usage_decisions": build_usage_decisions(source_ids),
        "age_range": safe_text(item.get("age_range")),
        "tone": safe_text(item.get("tone")),
        "referral_needed": bool(item.get("referral_needed", False)),
        "basis_type": safe_text(item.get("basis_type")),
        "evidence_level": safe_text(item.get("evidence_level")),
        "confidence_level": safe_text(item.get("confidence_level")),
        "last_reviewed": safe_text(item.get("last_reviewed")),
    }


def ingest_parenting_guides(reset: bool = True) -> dict:
    """
    parenting_guides.json을 읽어서 ChromaDB에 저장한다.
    """
    data = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))

    ids = []
    documents = []
    metadatas = []

    for item in data:
        ids.append(item["id"])
        documents.append(build_document(item))
        metadatas.append(build_metadata(item))

    if reset:
        reset_collection()

    add_documents(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    return {
        "count": len(ids),
        "message": f"{len(ids)}개 parenting guide를 ChromaDB에 저장했습니다."
    }