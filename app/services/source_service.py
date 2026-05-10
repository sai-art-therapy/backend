import json
from pathlib import Path

SOURCE_PATH = Path("app/data/rag/parenting_chatbot/sources.json")


def load_sources() -> dict:
    """
    sources.json을 읽어서 source_id 기준 dict로 변환한다.
    """
    data = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    return {item["source_id"]: item for item in data}


def get_sources_by_ids(source_ids: list[str]) -> list[dict]:
    """
    parenting_guides.json의 source_ids를 sources.json의 실제 출처 정보와 연결한다.
    """
    source_map = load_sources()

    sources = []
    for source_id in source_ids:
        source = source_map.get(source_id)
        if source:
            sources.append(source)

    return sources


def build_display_sources(source_ids: list[str]) -> str:
    """
    사용자에게 보여줄 출처명 문자열 생성.
    예: CDC, Positive Parenting Tips ...
    """
    sources = get_sources_by_ids(source_ids)

    display_list = []
    for source in sources:
        organization = source.get("organization", "")
        title = source.get("title", "")
        display_list.append(f"{organization}, {title}")

    return " | ".join(display_list)


def build_source_urls(source_ids: list[str]) -> str:
    sources = get_sources_by_ids(source_ids)
    return " | ".join([source.get("source_url", "") for source in sources])


def build_licenses(source_ids: list[str]) -> str:
    sources = get_sources_by_ids(source_ids)
    return " | ".join([source.get("license", "") for source in sources])


def build_usage_decisions(source_ids: list[str]) -> str:
    sources = get_sources_by_ids(source_ids)
    return " | ".join([source.get("usage_decision", "") for source in sources])