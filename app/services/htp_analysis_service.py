from pathlib import Path


def create_mock_yolo_result():
    """개발 테스트용 YOLO mock 결과.

    추후 실제 YOLO fine-tuned model 추론 결과로 교체 예정.
    """
    return {
        "model": "mock-yolo-htp",
        "all_detections": [
            {
                "label": "house_total",
                "display_label": "집",
                "confidence": 0.92,
                "bbox": {"x1": 10, "y1": 20, "x2": 100, "y2": 120},
                "use_for_display": True,
                "use_for_analysis": True,
            },
            {
                "label": "tree_total",
                "display_label": "나무",
                "confidence": 0.88,
                "bbox": {"x1": 140, "y1": 30, "x2": 220, "y2": 180},
                "use_for_display": True,
                "use_for_analysis": True,
            },
            {
                "label": "person_total",
                "display_label": "사람",
                "confidence": 0.85,
                "bbox": {"x1": 240, "y1": 50, "x2": 320, "y2": 220},
                "use_for_display": True,
                "use_for_analysis": True,
            },
            {
                "label": "window",
                "display_label": "창문",
                "confidence": 0.80,
                "bbox": {"x1": 35, "y1": 55, "x2": 55, "y2": 75},
                "use_for_display": False,
                "use_for_analysis": True,
            },
        ],
        "display_detections": [
            {
                "type": "house",
                "label": "집",
                "bbox": {"x1": 10, "y1": 20, "x2": 100, "y2": 120},
            },
            {
                "type": "tree",
                "label": "나무",
                "bbox": {"x1": 140, "y1": 30, "x2": 220, "y2": 180},
            },
            {
                "type": "person",
                "label": "사람",
                "bbox": {"x1": 240, "y1": 50, "x2": 320, "y2": 220},
            },
        ],
    }


def create_mock_visual_features():
    """개발 테스트용 OpenCV visual feature mock 결과.

    추후 YOLO 결과와 OpenCV feature 추출 결과로 교체 예정.
    """
    return {
        "global": {
            "image_width": 1280,
            "image_height": 1280,
            "drawing_area_ratio": 0.42,
            "overall_position": {"x": "center", "y": "middle"},
            "overall_line_density": "medium",
        },
        "house": {
            "detected": True,
            "relative_size": "medium",
            "position": {"x": "left", "y": "middle"},
            "parts": {
                "door": {"detected": False},
                "window": {"count": 1},
                "roof": {"detected": True},
            },
            "tags": ["house_detected", "door_not_detected", "window_present"],
        },
        "tree": {
            "detected": True,
            "relative_size": "medium",
            "position": {"x": "center", "y": "middle"},
            "parts": {
                "trunk": {"detected": True},
                "crown": {"detected": True},
                "roots": {"detected": False},
            },
            "tags": ["tree_detected", "roots_not_detected"],
        },
        "person": {
            "detected": True,
            "relative_size": "small",
            "position": {"x": "right", "y": "middle"},
            "parts": {
                "head": {"detected": True},
                "face": {"detected": True},
                "hands": {"count": 0},
                "feet": {"count": 0},
            },
            "tags": ["person_detected", "small_person", "hands_not_detected"],
        },
        "relationships": {
            "house_tree": {
                "overlap": False,
                "touching": False,
                "distance_level": "near",
            },
            "house_person": {
                "overlap": False,
                "touching": False,
                "distance_level": "far",
            },
            "tree_person": {
                "overlap": False,
                "touching": False,
                "distance_level": "near",
            },
            "enclosure_type": "none",
        },
    }


def get_pdi_choice_payload():
    """이미지 분석 후 프론트에 보여줄 PDI 선택 안내."""
    return {
        "title": "아이에게 몇 가지 질문을 해볼까요?",
        "description": (
            "아이의 답변을 함께 반영하면 그림의 의미를 더 조심스럽고 풍부하게 "
            "해석할 수 있어요. 지금 아이에게 질문하기 어려운 상황이라면 건너뛰어도 됩니다."
        ),
        "options": [
            {
                "value": "start_pdi",
                "label": "질문하고 답변 입력하기",
            },
            {
                "value": "skip_pdi",
                "label": "건너뛰고 리포트 보기",
            },
        ],
    }


def analyze_htp_image_mock(original_image_path: str):
    """현재 개발 단계의 HTP 이미지 분석 mock 함수.

    실제 구현 시 이 함수 내부가 아래 흐름으로 교체될 예정:
    1. OpenCV 1차 전처리
    2. YOLO 추론
    3. YOLO 결과 후처리
    4. OpenCV 2차 feature 추출
    5. 집/나무/사람 bbox만 표시한 결과 이미지 생성
    """
    result_image_path = str(Path(original_image_path))

    yolo_result_json = create_mock_yolo_result()
    visual_features_json = create_mock_visual_features()

    return {
        "result_image_path": result_image_path,
        "yolo_result_json": yolo_result_json,
        "visual_features_json": visual_features_json,
        "display_detections": yolo_result_json["display_detections"],
    }
