from app.core.config import CHROMA_HTP_COLLECTION
from app.models.htp_pdi import HtpPdiInteraction
from app.models.htp_test import HtpTest
from app.services.chroma_service import search_documents


def safe_get(data: dict | None, *keys, default=None):
    """중첩 dict에서 안전하게 값 꺼내기."""
    current = data or {}

    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)

    return current if current is not None else default


def build_feature_query_for_house(visual_features: dict) -> str:
    house = visual_features.get("house", {})

    relative_size = safe_get(house, "relative_size", default="")
    position_x = safe_get(house, "position", "x", default="")
    position_y = safe_get(house, "position", "y", default="")
    door_detected = safe_get(house, "parts", "door", "detected", default=None)
    window_count = safe_get(house, "parts", "window", "count", default=None)
    tags = house.get("tags", [])

    return f"""
KHTP 집 그림 해석.
집 크기 {relative_size}.
집 위치 {position_x} {position_y}.
문 탐지 여부 {door_detected}.
창문 개수 {window_count}.
태그 {tags}.
가족관계 생활환경 자기개방 대인접촉 해석 주의.
""".strip()


def build_feature_query_for_tree(visual_features: dict) -> str:
    tree = visual_features.get("tree", {})

    relative_size = safe_get(tree, "relative_size", default="")
    position_x = safe_get(tree, "position", "x", default="")
    position_y = safe_get(tree, "position", "y", default="")
    trunk_detected = safe_get(tree, "parts", "trunk", "detected", default=None)
    crown_detected = safe_get(tree, "parts", "crown", "detected", default=None)
    roots_detected = safe_get(tree, "parts", "roots", "detected", default=None)
    tags = tree.get("tags", [])

    return f"""
KHTP 나무 그림 해석.
나무 크기 {relative_size}.
나무 위치 {position_x} {position_y}.
기둥 탐지 여부 {trunk_detected}.
수관 탐지 여부 {crown_detected}.
뿌리 탐지 여부 {roots_detected}.
태그 {tags}.
자기상 성장감 에너지 안정감 발달단계 해석 주의.
""".strip()


def build_feature_query_for_person(visual_features: dict) -> str:
    person = visual_features.get("person", {})

    relative_size = safe_get(person, "relative_size", default="")
    position_x = safe_get(person, "position", "x", default="")
    position_y = safe_get(person, "position", "y", default="")
    head_detected = safe_get(person, "parts", "head", "detected", default=None)
    face_detected = safe_get(person, "parts", "face", "detected", default=None)
    hand_count = safe_get(person, "parts", "hands", "count", default=None)
    feet_count = safe_get(person, "parts", "feet", "count", default=None)
    tags = person.get("tags", [])

    return f"""
KHTP 사람 그림 해석.
사람 크기 {relative_size}.
사람 위치 {position_x} {position_y}.
머리 탐지 여부 {head_detected}.
얼굴 탐지 여부 {face_detected}.
손 개수 {hand_count}.
발 개수 {feet_count}.
태그 {tags}.
자기개념 자기표상 대인관계 신체상 세부묘사 해석 주의.
""".strip()


def build_feature_query_for_relationships(visual_features: dict) -> str:
    relationships = visual_features.get("relationships", {})

    return f"""
KHTP 집 나무 사람 관계 해석.
요소 간 거리 겹침 밀착 배치 관계.
관계 정보 {relationships}.
가족환경 자기상 대인관계 요소 간 관계 분석.
""".strip()


def build_pdi_query(pdi_interactions: list[HtpPdiInteraction]) -> str:
    answered_items = [
        item
        for item in pdi_interactions
        if item.answer_text
    ]

    if not answered_items:
        return """
KHTP PDI 응답 없음.
그림 특징만으로 단정하지 말 것.
PDI 없이 이미지 기반 관찰 중심 리포트 작성.
해석 한계와 추가 질문 권장.
""".strip()

    lines = ["KHTP PDI 질문 답변 기반 해석."]

    for item in answered_items:
        lines.append(
            f"[{item.target_type}] 질문: {item.question_text} / 아이 답변: {item.answer_text}"
        )

    lines.append("그림 특징과 PDI 응답을 함께 고려한 리포트 작성.")
    lines.append("단정 금지, 가능성 언어 사용, 보호자 안내 중심.")

    return "\n".join(lines)


def build_htp_rag_queries(
    htp_test: HtpTest,
    pdi_interactions: list[HtpPdiInteraction],
) -> list[str]:
    visual_features = htp_test.visual_features_json or {}

    queries = [
        "KHTP 사용 규칙 주의사항 단정 금지 전문 진단 대체 금지 PDI 생활 맥락 함께 고려",
        build_feature_query_for_house(visual_features),
        build_feature_query_for_tree(visual_features),
        build_feature_query_for_person(visual_features),
        build_feature_query_for_relationships(visual_features),
        build_pdi_query(pdi_interactions),
    ]

    return [query for query in queries if query.strip()]


def search_htp_knowledge_for_report(
    htp_test: HtpTest,
    pdi_interactions: list[HtpPdiInteraction],
    top_k_per_query: int = 3,
) -> list[dict]:
    """HTP 리포트 생성을 위한 RAG 검색.

    여러 query를 생성해서 htp_knowledge collection에서 검색하고,
    중복 chunk를 제거해 반환한다.
    """
    queries = build_htp_rag_queries(
        htp_test=htp_test,
        pdi_interactions=pdi_interactions,
    )

    merged_results = {}
    search_logs = []

    for query in queries:
        results = search_documents(
            query=query,
            top_k=top_k_per_query,
            collection_name=CHROMA_HTP_COLLECTION,
        )

        search_logs.append(
            {
                "query": query,
                "result_count": len(results),
            }
        )

        for result in results:
            chunk_id = result["id"]

            if chunk_id not in merged_results:
                merged_results[chunk_id] = result
            else:
                # 같은 chunk가 여러 query에서 검색되면 더 가까운 distance를 유지
                old_distance = merged_results[chunk_id].get("distance", 999)
                new_distance = result.get("distance", 999)

                if new_distance < old_distance:
                    merged_results[chunk_id] = result

    retrieved = list(merged_results.values())
    retrieved.sort(key=lambda item: item.get("distance", 999))

    return [
        {
            "id": item["id"],
            "document": item["document"],
            "metadata": item["metadata"],
            "distance": item["distance"],
        }
        for item in retrieved
    ]