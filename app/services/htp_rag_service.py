from datetime import date
from app.core.config import CHROMA_HTP_COLLECTION
from app.models.htp_pdi import HtpPdiInteraction
from app.models.htp_test import HtpTest
from app.services.chroma_service import search_documents

def build_child_context_query(htp_test: HtpTest) -> str:
    child = htp_test.child

    if child is None:
        return "KHTP 아동 정보 없음. 발달단계를 임의로 추정하지 말 것."

    age_by_year = date.today().year - child.birth_year

    return f"""
KHTP 아동 발달단계 해석.
출생 연도 {child.birth_year}.
연도 기준 나이 {age_by_year}세.
성별 {child.gender}.
해당 연령의 그림 발달단계와 해석 주의사항.
나이와 성별만으로 심리 상태를 단정하지 말 것.
""".strip()

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
지붕 탐지 여부 {safe_get(house, "parts", "roof", "detected")}.
벽 탐지 여부 {safe_get(house, "parts", "wall", "detected")}.
굴뚝 탐지 여부 {safe_get(house, "parts", "chimney", "detected")}.
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
가지 탐지 여부 {safe_get(tree, "parts", "branch", "detected")}.
열매 개수 {safe_get(tree, "parts", "fruit", "count")}.
꽃 개수 {safe_get(tree, "parts", "flower", "count")}.
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
팔 개수 {safe_get(person, "parts", "arms", "count")}.
다리 개수 {safe_get(person, "parts", "legs", "count")}.
신발 탐지 여부 {safe_get(person, "parts", "shoes", "detected")}.
태그 {tags}.
자기개념 자기표상 대인관계 신체상 세부묘사 해석 주의.
""".strip()


def build_feature_query_for_composition(visual_features: dict) -> str:
    # Retrieve structural evidence explicitly; object queries often retrieve only parts.
    observed = {
        name: {key: feature[key] for key in ("relative_size", "position") if key in feature}
        for name in ("house", "tree", "person")
        if (feature := visual_features.get(name, {})).get("detected") is True
    }
    if not any(observed.values()):
        return ""
    return (
        f"KHTP 그림 크기 위치 구성 조합 해석. 실제 객체별 상대 크기와 위치 {observed}. "
        "공간 사용 자기표현 해석 가능성. 관찰된 조합만 해석하고 성격을 확정하지 말 것."
    )


def build_feature_query_for_relationships(visual_features: dict) -> str:
    relationships = visual_features.get("relationships", {})

    return f"""
KHTP 밀착(enclosure) 개념과 심리적 의미. H-T H-P P-T 요소 간 거리와 독립적 성장.
실제 물리적 접촉·겹침 여부와 단순한 가까운 배치를 구분. 밀착 없음도 함께 검토.
관계 정보 {relationships}.
관찰된 관계에 맞는 해석만 참고하고 심리적 성숙이나 가족관계를 확정하지 말 것.
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
PDI 없이도 실제 시각 특징과 HTP 근거를 연결한 가능성 해석.
크기 위치 구성 세부 요소 관계를 함께 고려.
""".strip()

    lines = ["KHTP PDI 질문 답변 기반 해석."]

    for item in answered_items:
        lines.append(
            f"[{item.target_type}] 질문: {item.question_text} / 아이 답변: {item.answer_text}"
        )

    lines.append("시각 특징 기반 HTP 해석을 PDI 답변으로 보완하거나 수정. 답변 요약으로 대체하지 않기.")
    lines.append("단정 금지, 가능성 언어 사용, 보호자 안내 중심.")

    return "\n".join(lines)

def build_drawing_process_query(visual_features: dict) -> str:
    process = visual_features.get("drawing_process", {})

    if not process.get("available"):
        return (
            "KHTP 캔버스 과정 데이터 없음. "
            "필압과 그리기 시간을 추측하거나 해석하지 말 것."
        )

    duration_seconds = safe_get(
        process, "duration", "total_seconds", default=""
    )
    pressure_available = safe_get(
        process, "pressure", "available", default=False
    )
    pressure_mean = safe_get(
        process, "pressure", "mean", default=""
    )
    pressure_stddev = safe_get(
        process, "pressure", "stddev", default=""
    )
    position_x = safe_get(
        process, "spatial", "position", "x", default=""
    )
    position_y = safe_get(
        process, "spatial", "position", "y", default=""
    )

    return f"""
KHTP 그리기 과정 구조적 분석.
전체 소요 시간 {duration_seconds}초.
실측 필압 사용 가능 여부 {pressure_available}.
평균 필압 {pressure_mean}.
필압 표준편차 {pressure_stddev}.
전체 좌표 기반 위치 {position_x} {position_y}.
그림 위치, 필압, 선 강도, 소요 시간 해석.
필압과 시간만으로 심리 상태를 단정하지 말 것.
""".strip()

def build_htp_rag_queries(
    htp_test: HtpTest,
    pdi_interactions: list[HtpPdiInteraction],
) -> list[str]:
    visual_features = htp_test.visual_features_json or {}

    queries = [
        "KHTP 사용 규칙 주의사항 단정 금지 전문 진단 대체 금지 PDI 생활 맥락 함께 고려",
        build_child_context_query(htp_test),
        build_feature_query_for_house(visual_features),
        build_feature_query_for_tree(visual_features),
        build_feature_query_for_person(visual_features),
        build_feature_query_for_composition(visual_features),
        build_feature_query_for_relationships(visual_features),
    ]

    drawing_process = visual_features.get("drawing_process", {})

    if drawing_process.get("available"):
        queries.append(
            build_drawing_process_query(visual_features)
        )

    queries.append(build_pdi_query(pdi_interactions))

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
