import json
from pathlib import Path

from app.core.config import CHROMA_HTP_COLLECTION
from app.services.chroma_service import add_documents, reset_collection

HTP_KNOWLEDGE_PATH = Path("app/data/rag/htp_report_generation/htp_knowledge.json")
HTP_SOURCES_PATH = Path("app/data/rag/htp_report_generation/sources.json")


def safe_text(value) -> str:
    """
    ChromaDB document/metadata에 넣기 위해 값을 안전하게 문자열로 변환한다.
    """
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def load_htp_sources() -> dict:
    """
    sources.json을 source_id 기준 dict로 변환한다.
    """
    data = json.loads(HTP_SOURCES_PATH.read_text(encoding="utf-8"))
    sources = data.get("sources", [])

    return {
        source["id"]: source
        for source in sources
    }


def build_source_titles(source_ids: list[str], source_map: dict) -> str:
    titles = []

    for source_id in source_ids:
        source = source_map.get(source_id)
        if not source:
            continue

        title = source.get("title", "")
        year = source.get("year", "")
        author = source.get("author", "")

        display = f"{title}"
        if author:
            display += f" / {author}"
        if year:
            display += f" ({year})"

        titles.append(display)

    return " | ".join(titles)


def build_htp_document(chunk: dict, source_map: dict) -> str:
    """
    htp_knowledge.json의 chunk 1개를 RAG 검색용 document 텍스트로 변환한다.
    """
    source_ids = chunk.get("source_ids", [])
    source_titles = build_source_titles(source_ids, source_map)

    return f"""
[ID]
{safe_text(chunk.get("id"))}

[섹션]
{safe_text(chunk.get("section"))} > {safe_text(chunk.get("subsection"))}

[제목]
{safe_text(chunk.get("title"))}

[내용]
{safe_text(chunk.get("content"))}

[태그]
{safe_text(chunk.get("tags"))}

[검사 형식]
{safe_text(chunk.get("test_format"))}

[출처]
{source_titles}
""".strip()


def build_htp_metadata(chunk: dict, source_map: dict) -> dict:
    """
    HTP 검색 결과 표시 및 필터링에 사용할 metadata를 만든다.
    ChromaDB metadata에는 문자열, 숫자, bool 같은 단순 타입만 넣는다.
    """
    source_ids = chunk.get("source_ids", [])

    return {
        "chunk_id": safe_text(chunk.get("id")),
        "section": safe_text(chunk.get("section")),
        "subsection": safe_text(chunk.get("subsection")),
        "title": safe_text(chunk.get("title")),
        "tags": safe_text(chunk.get("tags")),
        "source_ids": safe_text(source_ids),
        "source_titles": build_source_titles(source_ids, source_map),
        "test_format": safe_text(chunk.get("test_format")),
    }


def ingest_htp_knowledge(reset: bool = True) -> dict:
    """
    htp_knowledge.json을 읽어서 ChromaDB htp_knowledge collection에 저장한다.
    """
    data = json.loads(HTP_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    chunks = data.get("chunks", [])
    source_map = load_htp_sources()

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        ids.append(chunk["id"])
        documents.append(build_htp_document(chunk, source_map))
        metadatas.append(build_htp_metadata(chunk, source_map))

    if reset:
        reset_collection(CHROMA_HTP_COLLECTION)

    add_documents(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        collection_name=CHROMA_HTP_COLLECTION,
    )

    return {
        "collection": CHROMA_HTP_COLLECTION,
        "count": len(ids),
        "message": f"{len(ids)}개 HTP 지식 chunk를 ChromaDB에 저장했습니다.",
    }