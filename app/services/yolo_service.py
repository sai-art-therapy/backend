from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2

from app.core.config import (
    YOLO_HTP_CONF_THRESHOLD,
    YOLO_HTP_FALLBACK_ENABLED,
    YOLO_HTP_MODEL_NAME,
    YOLO_HTP_WEIGHTS_PATH,
)
from app.services.htp_analysis_service import (
    create_mock_visual_features,
    create_mock_yolo_result,
)

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


_yolo_model = None


DISPLAY_LABEL_MAP = {
    # house 계열
    "house": "집",
    "house_total": "집",
    "집": "집",
    "집전체": "집",
    "집벽": "집벽",
    "지붕": "지붕",
    "문": "문",
    "창문": "창문",
    "굴뚝": "굴뚝",

    # tree 계열
    "tree": "나무",
    "tree_total": "나무",
    "나무": "나무",
    "나무전체": "나무",
    "수관": "수관",
    "줄기": "줄기",
    "나무줄기": "줄기",
    "뿌리": "뿌리",
    "열매": "열매",

    # person 계열
    "person": "사람",
    "person_total": "사람",
    "사람": "사람",
    "사람전체": "사람",
    "남자": "사람",
    "여자": "사람",
    "아이": "사람",
    "머리": "머리",
    "얼굴": "얼굴",
    "눈": "눈",
    "코": "코",
    "입": "입",
    "귀": "귀",
    "목": "목",
    "몸": "몸",
    "몸통": "몸통",
    "팔": "팔",
    "손": "손",
    "다리": "다리",
    "발": "발",
}


NORMALIZED_TYPE_MAP = {
    # house 전체 및 세부요소
    "house": "house",
    "house_total": "house",
    "집": "house",
    "집전체": "house",
    "집벽": "house",
    "지붕": "house",
    "문": "house",
    "창문": "house",
    "굴뚝": "house",

    # tree 전체 및 세부요소
    "tree": "tree",
    "tree_total": "tree",
    "나무": "tree",
    "나무전체": "tree",
    "수관": "tree",
    "줄기": "tree",
    "나무줄기": "tree",
    "뿌리": "tree",
    "열매": "tree",

    # person 전체 및 세부요소
    "person": "person",
    "person_total": "person",
    "사람": "person",
    "사람전체": "person",
    "남자": "person",
    "여자": "person",
    "아이": "person",
    "머리": "person",
    "얼굴": "person",
    "눈": "person",
    "코": "person",
    "입": "person",
    "귀": "person",
    "목": "person",
    "몸": "person",
    "몸통": "person",
    "팔": "person",
    "손": "person",
    "다리": "person",
    "발": "person",
}


# 실제 결과 이미지에 bbox로 표시할 큰 객체만 지정
# 문/창문/지붕/수관/열매 같은 세부 요소는 분석에는 쓰되, 탭 이미지에는 표시하지 않음
DISPLAY_TARGET_LABELS = {
    "house",
    "house_total",
    "집",
    "집전체",

    "tree",
    "tree_total",
    "나무",
    "나무전체",

    "person",
    "person_total",
    "사람",
    "사람전체",
    "남자",
    "여자",
    "아이",
}


def _load_yolo_model():
    """YOLO 모델을 한 번만 로드해서 재사용한다."""
    global _yolo_model

    if _yolo_model is not None:
        return _yolo_model

    if YOLO is None:
        raise RuntimeError("ultralytics 패키지가 설치되어 있지 않습니다.")

    weights_path = Path(YOLO_HTP_WEIGHTS_PATH)

    if not weights_path.exists():
        raise FileNotFoundError(f"YOLO 가중치 파일을 찾을 수 없습니다: {weights_path}")

    _yolo_model = YOLO(str(weights_path))
    return _yolo_model


def _clean_label(raw_label: str) -> str:
    return raw_label.lower().strip()


def _bbox_list_to_dict(bbox: List[float]) -> Dict[str, int]:
    x1, y1, x2, y2 = bbox
    return {
        "x1": int(round(x1)),
        "y1": int(round(y1)),
        "x2": int(round(x2)),
        "y2": int(round(y2)),
    }


def _bbox_area(bbox: Dict[str, int]) -> int:
    width = max(0, bbox["x2"] - bbox["x1"])
    height = max(0, bbox["y2"] - bbox["y1"])
    return width * height


def _get_center(bbox: Dict[str, int]) -> Tuple[float, float]:
    return (
        (bbox["x1"] + bbox["x2"]) / 2,
        (bbox["y1"] + bbox["y2"]) / 2,
    )


def _position_label(value: float, total: int, axis: str) -> str:
    ratio = value / max(total, 1)

    if axis == "x":
        if ratio < 0.33:
            return "left"
        if ratio > 0.66:
            return "right"
        return "center"

    if ratio < 0.33:
        return "top"
    if ratio > 0.66:
        return "bottom"
    return "middle"


def _relative_size_label(area: int, image_area: int) -> str:
    ratio = area / max(image_area, 1)

    if ratio < 0.03:
        return "small"
    if ratio > 0.18:
        return "large"
    return "medium"


def _distance_level(
    bbox_a: Optional[Dict[str, int]],
    bbox_b: Optional[Dict[str, int]],
    image_width: int,
    image_height: int,
) -> str:
    if bbox_a is None or bbox_b is None:
        return "unknown"

    ax, ay = _get_center(bbox_a)
    bx, by = _get_center(bbox_b)

    distance = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    diagonal = max((image_width**2 + image_height**2) ** 0.5, 1)

    ratio = distance / diagonal

    if ratio < 0.18:
        return "near"
    if ratio < 0.38:
        return "middle"
    return "far"


def _is_overlap(
    bbox_a: Optional[Dict[str, int]],
    bbox_b: Optional[Dict[str, int]],
) -> bool:
    if bbox_a is None or bbox_b is None:
        return False

    return not (
        bbox_a["x2"] < bbox_b["x1"]
        or bbox_b["x2"] < bbox_a["x1"]
        or bbox_a["y2"] < bbox_b["y1"]
        or bbox_b["y2"] < bbox_a["y1"]
    )


def _is_touching(
    bbox_a: Optional[Dict[str, int]],
    bbox_b: Optional[Dict[str, int]],
    threshold: int = 10,
) -> bool:
    if bbox_a is None or bbox_b is None:
        return False

    if _is_overlap(bbox_a, bbox_b):
        return True

    horizontal_gap = max(
        bbox_b["x1"] - bbox_a["x2"],
        bbox_a["x1"] - bbox_b["x2"],
        0,
    )
    vertical_gap = max(
        bbox_b["y1"] - bbox_a["y2"],
        bbox_a["y1"] - bbox_b["y2"],
        0,
    )

    return horizontal_gap <= threshold and vertical_gap <= threshold


def _normalize_label(raw_label: str) -> str:
    label = _clean_label(raw_label)
    return NORMALIZED_TYPE_MAP.get(label, label)


def _to_display_label(raw_label: str) -> str:
    label = _clean_label(raw_label)
    return DISPLAY_LABEL_MAP.get(label, raw_label)


def _should_display(raw_label: str) -> bool:
    label = _clean_label(raw_label)
    return label in DISPLAY_TARGET_LABELS


def _extract_detections_from_result(result: Any) -> List[Dict[str, Any]]:
    detections = []

    names = result.names

    if result.boxes is None:
        return detections

    for box in result.boxes:
        cls_id = int(box.cls[0].item())
        confidence = float(box.conf[0].item())
        raw_label = names.get(cls_id, str(cls_id))

        bbox_values = box.xyxy[0].tolist()
        bbox = _bbox_list_to_dict(bbox_values)

        display_label = _to_display_label(raw_label)
        use_for_display = _should_display(raw_label)

        detections.append(
            {
                "label": raw_label,
                "display_label": display_label,
                "confidence": round(confidence, 4),
                "bbox": bbox,
                "use_for_display": use_for_display,
                "use_for_analysis": True,
            }
        )

    return detections


def _create_display_detections(
    all_detections: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    display_detections = []

    for detection in all_detections:
        raw_label = detection["label"]

        if not _should_display(raw_label):
            continue

        normalized_type = _normalize_label(raw_label)

        if normalized_type not in {"house", "tree", "person"}:
            continue

        display_detections.append(
            {
                "type": normalized_type,
                "label": detection["display_label"],
                "confidence": detection["confidence"],
                "bbox": detection["bbox"],
            }
        )

    return display_detections


def _pick_best_bbox(
    detections: List[Dict[str, Any]],
    target_type: str,
) -> Optional[Dict[str, int]]:
    candidates = [
        detection
        for detection in detections
        if _normalize_label(detection["label"]) == target_type
    ]

    if not candidates:
        return None

    best = max(candidates, key=lambda item: item["confidence"])
    return best["bbox"]


def _count_parts(
    detections: List[Dict[str, Any]],
    labels: List[str],
) -> int:
    label_set = {_clean_label(label) for label in labels}

    return sum(
        1
        for detection in detections
        if _clean_label(detection["label"]) in label_set
    )


def _has_part(
    detections: List[Dict[str, Any]],
    labels: List[str],
) -> bool:
    return _count_parts(detections, labels) > 0


def _create_visual_features_from_yolo(
    image_path: str,
    detections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(f"이미지를 읽을 수 없습니다: {image_path}")

    image_height, image_width = image.shape[:2]
    image_area = image_width * image_height

    house_bbox = _pick_best_bbox(detections, "house")
    tree_bbox = _pick_best_bbox(detections, "tree")
    person_bbox = _pick_best_bbox(detections, "person")

    target_bboxes = {
        "house": house_bbox,
        "tree": tree_bbox,
        "person": person_bbox,
    }

    detected_areas = [
        _bbox_area(bbox)
        for bbox in target_bboxes.values()
        if bbox is not None
    ]

    drawing_area_ratio = round(sum(detected_areas) / max(image_area, 1), 4)

    if detected_areas:
        centers = [
            _get_center(bbox)
            for bbox in target_bboxes.values()
            if bbox is not None
        ]
        avg_x = sum(center[0] for center in centers) / len(centers)
        avg_y = sum(center[1] for center in centers) / len(centers)
        overall_position = {
            "x": _position_label(avg_x, image_width, "x"),
            "y": _position_label(avg_y, image_height, "y"),
        }
    else:
        overall_position = {"x": "unknown", "y": "unknown"}

    def object_feature(
        target_type: str,
        bbox: Optional[Dict[str, int]],
    ) -> Dict[str, Any]:
        if bbox is None:
            return {
                "detected": False,
                "relative_size": "unknown",
                "position": {"x": "unknown", "y": "unknown"},
                "parts": {},
                "tags": [f"{target_type}_not_detected"],
            }

        center_x, center_y = _get_center(bbox)

        feature = {
            "detected": True,
            "relative_size": _relative_size_label(_bbox_area(bbox), image_area),
            "position": {
                "x": _position_label(center_x, image_width, "x"),
                "y": _position_label(center_y, image_height, "y"),
            },
            "parts": {},
            "tags": [f"{target_type}_detected"],
        }

        if target_type == "house":
            feature["parts"] = {
                "door": {"detected": _has_part(detections, ["문"])},
                "window": {"count": _count_parts(detections, ["창문"])},
                "roof": {"detected": _has_part(detections, ["지붕"])},
                "chimney": {"detected": _has_part(detections, ["굴뚝"])},
            }

            if feature["parts"]["door"]["detected"]:
                feature["tags"].append("door_detected")
            else:
                feature["tags"].append("door_not_detected")

            if feature["parts"]["window"]["count"] > 0:
                feature["tags"].append("window_present")

            if feature["parts"]["roof"]["detected"]:
                feature["tags"].append("roof_detected")

        elif target_type == "tree":
            feature["parts"] = {
                "trunk": {"detected": _has_part(detections, ["줄기", "나무줄기"])},
                "crown": {"detected": _has_part(detections, ["수관"])},
                "roots": {"detected": _has_part(detections, ["뿌리"])},
                "fruit": {"count": _count_parts(detections, ["열매"])},
            }

            if feature["parts"]["trunk"]["detected"]:
                feature["tags"].append("trunk_detected")
            if feature["parts"]["crown"]["detected"]:
                feature["tags"].append("crown_detected")
            if not feature["parts"]["roots"]["detected"]:
                feature["tags"].append("roots_not_detected")
            if feature["parts"]["fruit"]["count"] > 0:
                feature["tags"].append("fruit_present")

        elif target_type == "person":
            feature["parts"] = {
                "head": {"detected": _has_part(detections, ["머리", "얼굴"])},
                "face": {"detected": _has_part(detections, ["얼굴", "눈", "코", "입"])},
                "hands": {"count": _count_parts(detections, ["손"])},
                "feet": {"count": _count_parts(detections, ["발"])},
                "arms": {"count": _count_parts(detections, ["팔"])},
                "legs": {"count": _count_parts(detections, ["다리"])},
            }

            if feature["parts"]["head"]["detected"]:
                feature["tags"].append("head_detected")
            if feature["parts"]["face"]["detected"]:
                feature["tags"].append("face_detected")
            if feature["parts"]["hands"]["count"] == 0:
                feature["tags"].append("hands_not_detected")
            if feature["parts"]["feet"]["count"] == 0:
                feature["tags"].append("feet_not_detected")

        return feature

    return {
        "global": {
            "image_width": image_width,
            "image_height": image_height,
            "drawing_area_ratio": drawing_area_ratio,
            "overall_position": overall_position,
            "overall_line_density": "unknown",
        },
        "house": object_feature("house", house_bbox),
        "tree": object_feature("tree", tree_bbox),
        "person": object_feature("person", person_bbox),
        "relationships": {
            "house_tree": {
                "overlap": _is_overlap(house_bbox, tree_bbox),
                "touching": _is_touching(house_bbox, tree_bbox),
                "distance_level": _distance_level(
                    house_bbox,
                    tree_bbox,
                    image_width,
                    image_height,
                ),
            },
            "house_person": {
                "overlap": _is_overlap(house_bbox, person_bbox),
                "touching": _is_touching(house_bbox, person_bbox),
                "distance_level": _distance_level(
                    house_bbox,
                    person_bbox,
                    image_width,
                    image_height,
                ),
            },
            "tree_person": {
                "overlap": _is_overlap(tree_bbox, person_bbox),
                "touching": _is_touching(tree_bbox, person_bbox),
                "distance_level": _distance_level(
                    tree_bbox,
                    person_bbox,
                    image_width,
                    image_height,
                ),
            },
            "enclosure_type": "unknown",
        },
    }


def _draw_bboxes_only(
    image,
    detections: List[Dict[str, Any]],
) -> None:
    """텍스트 없이 bbox만 그린다. 한글 label이 ???로 깨지는 문제 방지."""
    for detection in detections:
        bbox = detection["bbox"]

        x1 = bbox["x1"]
        y1 = bbox["y1"]
        x2 = bbox["x2"]
        y2 = bbox["y2"]

        cv2.rectangle(
            image,
            (x1, y1),
            (x2, y2),
            (0, 0, 0),
            2,
        )


def _save_single_result_image(
    original_image_path: str,
    detections: List[Dict[str, Any]],
    suffix: str,
) -> str:
    original_path = Path(original_image_path)
    image = cv2.imread(str(original_path))

    if image is None:
        raise ValueError(
            f"결과 이미지를 생성할 수 없습니다. 이미지를 읽을 수 없습니다: {original_path}"
        )

    _draw_bboxes_only(image, detections)

    result_dir = Path("uploads") / "htp" / "result"
    result_dir.mkdir(parents=True, exist_ok=True)

    result_path = result_dir / f"{original_path.stem}_{suffix}{original_path.suffix}"
    cv2.imwrite(str(result_path), image)

    return str(result_path)


def _build_result_image_paths(
    original_image_path: str,
    display_detections: List[Dict[str, Any]],
) -> Dict[str, Optional[str]]:
    grouped = {
        "house": [d for d in display_detections if d["type"] == "house"],
        "tree": [d for d in display_detections if d["type"] == "tree"],
        "person": [d for d in display_detections if d["type"] == "person"],
    }

    result_image_paths = {
        "all": _save_single_result_image(
            original_image_path=original_image_path,
            detections=display_detections,
            suffix="yolo_result_all",
        ),
        "house": None,
        "tree": None,
        "person": None,
    }

    for key in ["house", "tree", "person"]:
        if grouped[key]:
            result_image_paths[key] = _save_single_result_image(
                original_image_path=original_image_path,
                detections=grouped[key],
                suffix=f"yolo_result_{key}",
            )

    return result_image_paths


def _create_fallback_result(
    original_image_path: str,
    error_message: str,
) -> Dict[str, Any]:
    yolo_result_json = create_mock_yolo_result()
    visual_features_json = create_mock_visual_features()

    result_image_paths = {
        "all": str(Path(original_image_path)),
        "house": None,
        "tree": None,
        "person": None,
    }

    yolo_result_json["model"] = "fallback_mock_yolo"
    yolo_result_json["fallback"] = True
    yolo_result_json["fallback_reason"] = error_message
    yolo_result_json["requested_model_name"] = YOLO_HTP_MODEL_NAME
    yolo_result_json["result_image_paths"] = result_image_paths

    return {
        "result_image_path": result_image_paths["all"],
        "result_image_paths": result_image_paths,
        "yolo_result_json": yolo_result_json,
        "visual_features_json": visual_features_json,
        "display_detections": yolo_result_json["display_detections"],
    }


def analyze_htp_image_with_yolo(original_image_path: str) -> Dict[str, Any]:
    """HTP 이미지에 대해 YOLO 추론을 수행한다.

    반환 구조:
    - result_image_path: 전체 bbox 이미지
    - result_image_paths: all / house / tree / person 탭별 이미지 경로
    - yolo_result_json: DB 저장용 YOLO 결과
    - visual_features_json: 리포트 생성용 정량 feature
    - display_detections: 프론트 표시용 bbox 정보
    """
    try:
        image_path = Path(original_image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"분석할 이미지 파일을 찾을 수 없습니다: {image_path}")

        model = _load_yolo_model()

        results = model.predict(
            source=str(image_path),
            conf=YOLO_HTP_CONF_THRESHOLD,
            verbose=False,
        )

        if not results:
            raise RuntimeError("YOLO 추론 결과가 비어 있습니다.")

        first_result = results[0]
        all_detections = _extract_detections_from_result(first_result)
        display_detections = _create_display_detections(all_detections)

        result_image_paths = _build_result_image_paths(
            original_image_path=str(image_path),
            display_detections=display_detections,
        )

        yolo_result_json = {
            "model": YOLO_HTP_MODEL_NAME,
            "weights_path": YOLO_HTP_WEIGHTS_PATH,
            "confidence_threshold": YOLO_HTP_CONF_THRESHOLD,
            "fallback": False,
            "all_detections": all_detections,
            "display_detections": display_detections,
            "result_image_paths": result_image_paths,
        }

        visual_features_json = _create_visual_features_from_yolo(
            image_path=str(image_path),
            detections=all_detections,
        )

        return {
            "result_image_path": result_image_paths["all"],
            "result_image_paths": result_image_paths,
            "yolo_result_json": yolo_result_json,
            "visual_features_json": visual_features_json,
            "display_detections": display_detections,
        }

    except Exception as exc:
        if YOLO_HTP_FALLBACK_ENABLED:
            return _create_fallback_result(
                original_image_path=original_image_path,
                error_message=str(exc),
            )

        raise