from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.core.config import (
    YOLO_HTP_CONF_THRESHOLD,
    YOLO_HTP_FALLBACK_ENABLED,
    YOLO_HTP_IMAGE_SIZE,
    YOLO_HTP_HOUSE_WEIGHTS_PATH,
    YOLO_HTP_TREE_WEIGHTS_PATH,
    YOLO_HTP_PERSON_WEIGHTS_PATH,
    YOLO_HTP_MODEL_NAME_HOUSE,
    YOLO_HTP_MODEL_NAME_TREE,
    YOLO_HTP_MODEL_NAME_PERSON,
)
from app.services.htp_analysis_service import (
    create_mock_visual_features,
    create_mock_yolo_result,
)

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


# ── 모델 3개 각각 캐싱 ────────────────────────────────────────────────────────
_yolo_models: Dict[str, Any] = {
    "house": None,
    "tree": None,
    "person": None,
}

_WEIGHTS_MAP: Dict[str, str] = {
    "house":  YOLO_HTP_HOUSE_WEIGHTS_PATH,
    "tree":   YOLO_HTP_TREE_WEIGHTS_PATH,
    "person": YOLO_HTP_PERSON_WEIGHTS_PATH,
}

_MODEL_NAME_MAP: Dict[str, str] = {
    "house":  YOLO_HTP_MODEL_NAME_HOUSE,
    "tree":   YOLO_HTP_MODEL_NAME_TREE,
    "person": YOLO_HTP_MODEL_NAME_PERSON,
}
# ─────────────────────────────────────────────────────────────────────────────


# ── Display label map (raw label → 한글 표시명) ───────────────────────────────
DISPLAY_LABEL_MAP = {
    # house 계열
    "house": "집",
    "house_total": "집",
    "집": "집",
    "집전체": "집",
    "집벽": "집벽",
    "wall": "집벽",
    "지붕": "지붕",
    "roof": "지붕",
    "문": "문",
    "door": "문",
    "창문": "창문",
    "window": "창문",
    "굴뚝": "굴뚝",
    "chimney": "굴뚝",

    # tree 계열
    "tree": "나무",
    "tree_total": "나무",
    "나무": "나무",
    "나무전체": "나무",
    "수관": "수관",
    "crown": "수관",
    "줄기": "줄기",
    "나무줄기": "줄기",
    "trunk": "줄기",
    "뿌리": "뿌리",
    "root": "뿌리",
    "branch": "가지",
    "열매": "열매",
    "fruit": "열매",
    "flower": "꽃",
    "bird": "새",

    # person 계열
    "person": "사람",
    "person_total": "사람",
    "사람": "사람",
    "사람전체": "사람",
    "male_person": "사람",
    "female_person": "사람",
    "남자": "사람",
    "여자": "사람",
    "아이": "사람",
    "머리": "머리",
    "head": "머리",
    "얼굴": "얼굴",
    "face": "얼굴",
    "눈": "눈",
    "eye": "눈",
    "코": "코",
    "nose": "코",
    "입": "입",
    "mouth": "입",
    "귀": "귀",
    "ear": "귀",
    "목": "목",
    "neck": "목",
    "몸": "몸통",
    "몸통": "몸통",
    "body": "몸통",
    "upper_body": "몸통",
    "팔": "팔",
    "arm": "팔",
    "손": "손",
    "hand": "손",
    "다리": "다리",
    "leg": "다리",
    "발": "발",
    "foot": "발",
    "feet": "발",
    "male_shoes": "신발",
    "female_shoes": "신발",
    "sneakers": "신발",
    "shoes": "신발",
    "hair": "머리카락",

    # 기타 배경 객체
    "태양": "태양",
    "sun": "태양",
    "moon": "달",
    "구름": "구름",
    "cloud": "구름",
    "꽃": "꽃",
    "잔디": "잔디",
    "grass": "잔디",
    "길": "길",
    "road": "길",
    "연기": "연기",
    "smoke": "연기",
    "연못": "연못",
    "pond": "연못",
    "pocket": "주머니",
}


# ── Normalize map (raw label → house / tree / person 그룹) ───────────────────
NORMALIZED_TYPE_MAP = {
    # house 전체 및 세부요소
    "house": "house",
    "house_total": "house",
    "집": "house",
    "집전체": "house",
    "집벽": "house",
    "wall": "house",
    "지붕": "house",
    "roof": "house",
    "문": "house",
    "door": "house",
    "창문": "house",
    "window": "house",
    "굴뚝": "house",
    "chimney": "house",

    # tree 전체 및 세부요소
    "tree": "tree",
    "tree_total": "tree",
    "나무": "tree",
    "나무전체": "tree",
    "수관": "tree",
    "crown": "tree",
    "줄기": "tree",
    "나무줄기": "tree",
    "trunk": "tree",
    "뿌리": "tree",
    "root": "tree",
    "branch": "tree",
    "열매": "tree",
    "fruit": "tree",
    "flower": "tree",
    "bird": "tree",

    # person 전체 및 세부요소
    "person": "person",
    "person_total": "person",
    "사람": "person",
    "사람전체": "person",
    "male_person": "person",
    "female_person": "person",
    "남자": "person",
    "여자": "person",
    "아이": "person",
    "머리": "person",
    "head": "person",
    "얼굴": "person",
    "face": "person",
    "눈": "person",
    "eye": "person",
    "코": "person",
    "nose": "person",
    "입": "person",
    "mouth": "person",
    "귀": "person",
    "ear": "person",
    "목": "person",
    "neck": "person",
    "몸": "person",
    "몸통": "person",
    "body": "person",
    "upper_body": "person",
    "팔": "person",
    "arm": "person",
    "손": "person",
    "hand": "person",
    "다리": "person",
    "leg": "person",
    "발": "person",
    "foot": "person",
    "feet": "person",
    "male_shoes": "person",
    "female_shoes": "person",
    "sneakers": "person",
    "shoes": "person",
    "hair": "person",
}


# ── 프론트 탭용 주요 객체만 표시 ──────────────────────────────────────────────
DISPLAY_TARGET_LABELS = {
    "house", "house_total", "집", "집전체",
    "tree", "tree_total", "나무", "나무전체",
    "person", "person_total", "사람", "사람전체",
    "male_person", "female_person",
    "남자", "여자", "아이",
}


# ── 대표 bbox 선택 시 main object 우선 ───────────────────────────────────────
# sub-object(shoes, hand 등)가 confidence 높아도 main object bbox가 우선 선택됨
MAIN_OBJECT_LABELS: Dict[str, set] = {
    "house": {
        "house", "house_total", "집", "집전체",
    },
    "tree": {
        "tree", "tree_total", "나무", "나무전체",
    },
    "person": {
        "person", "person_total", "사람", "사람전체",
        "male_person", "female_person", "남자", "여자", "아이",
    },
}
# ─────────────────────────────────────────────────────────────────────────────


def _load_yolo_models() -> Dict[str, Any]:
    """house / tree / person 모델을 각각 한 번만 로드해서 재사용한다."""
    global _yolo_models

    if YOLO is None:
        raise RuntimeError("ultralytics 패키지가 설치되어 있지 않습니다.")

    for key, weights_path_str in _WEIGHTS_MAP.items():
        if _yolo_models[key] is not None:
            continue
        weights_path = Path(weights_path_str)
        if not weights_path.exists():
            raise FileNotFoundError(
                f"YOLO 가중치 파일을 찾을 수 없습니다 [{key}]: {weights_path}"
            )
        _yolo_models[key] = YOLO(str(weights_path))

    return _yolo_models


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
    horizontal_gap = max(bbox_b["x1"] - bbox_a["x2"], bbox_a["x1"] - bbox_b["x2"], 0)
    vertical_gap = max(bbox_b["y1"] - bbox_a["y2"], bbox_a["y1"] - bbox_b["y2"], 0)
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
    """대표 bbox 선택: main object label 우선, 없으면 sub-object fallback.

    sub-object(hand, shoes, fruit 등)가 confidence가 높더라도
    main object bbox가 있으면 반드시 main object를 우선 선택한다.
    이렇게 해야 position / relative_size / relationships 계산이 정확해진다.
    """
    main_labels = MAIN_OBJECT_LABELS.get(target_type, set())

    # 1순위: main object label 후보
    main_candidates = [
        d for d in detections
        if _clean_label(d["label"]) in main_labels
    ]
    if main_candidates:
        return max(main_candidates, key=lambda d: d["confidence"])["bbox"]

    # 2순위: normalize 기준 같은 타입의 sub-object (fallback)
    sub_candidates = [
        d for d in detections
        if _normalize_label(d["label"]) == target_type
    ]
    if sub_candidates:
        return max(sub_candidates, key=lambda d: d["confidence"])["bbox"]

    return None


def _count_parts(
    detections: List[Dict[str, Any]],
    labels: List[str],
) -> int:
    label_set = {_clean_label(label) for label in labels}
    return sum(
        1 for detection in detections
        if _clean_label(detection["label"]) in label_set
    )


def _has_part(
    detections: List[Dict[str, Any]],
    labels: List[str],
) -> bool:
    return _count_parts(detections, labels) > 0


def _is_center_inside(
    part_bbox: Dict[str, int],
    main_bbox: Optional[Dict[str, int]],
) -> bool:
    """part bbox의 center point가 main bbox 안에 있는지 확인.

    완전 containment 대신 center point 방식을 사용해
    bbox가 조금 삐져나가거나 detection noise가 있어도 robust하게 동작한다.
    """
    if main_bbox is None:
        return False
    cx = (part_bbox["x1"] + part_bbox["x2"]) / 2
    cy = (part_bbox["y1"] + part_bbox["y2"]) / 2
    return (
        main_bbox["x1"] <= cx <= main_bbox["x2"]
        and main_bbox["y1"] <= cy <= main_bbox["y2"]
    )


def _count_parts_inside(
    detections: List[Dict[str, Any]],
    labels: List[str],
    main_bbox: Optional[Dict[str, int]],
) -> int:
    """main bbox 내부에 center가 있는 part detection만 카운트."""
    label_set = {_clean_label(label) for label in labels}
    return sum(
        1 for d in detections
        if _clean_label(d["label"]) in label_set
        and _is_center_inside(d["bbox"], main_bbox)
    )


def _has_part_inside(
    detections: List[Dict[str, Any]],
    labels: List[str],
    main_bbox: Optional[Dict[str, int]],
) -> bool:
    """main bbox 내부에 center가 있는 part가 존재하는지 확인."""
    return _count_parts_inside(detections, labels, main_bbox) > 0


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
                "door":    {"detected": _has_part_inside(detections, ["문", "door"], bbox)},
                "window":  {"count": _count_parts_inside(detections, ["창문", "window"], bbox)},
                "roof":    {"detected": _has_part_inside(detections, ["지붕", "roof"], bbox)},
                "chimney": {"detected": _has_part_inside(detections, ["굴뚝", "chimney"], bbox)},
                "wall":    {"detected": _has_part_inside(detections, ["집벽", "wall"], bbox)},
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
                "trunk":  {"detected": _has_part_inside(detections, ["줄기", "나무줄기", "trunk"], bbox)},
                "crown":  {"detected": _has_part_inside(detections, ["수관", "crown"], bbox)},
                "branch": {"detected": _has_part_inside(detections, ["branch"], bbox)},
                "roots":  {"detected": _has_part_inside(detections, ["뿌리", "root"], bbox)},
                "fruit":  {"count": _count_parts_inside(detections, ["열매", "fruit"], bbox)},
                "flower": {"count": _count_parts_inside(detections, ["꽃", "flower"], bbox)},
            }
            if feature["parts"]["trunk"]["detected"]:
                feature["tags"].append("trunk_detected")
            if feature["parts"]["crown"]["detected"]:
                feature["tags"].append("crown_detected")
            if not feature["parts"]["roots"]["detected"]:
                feature["tags"].append("roots_not_detected")
            if feature["parts"]["fruit"]["count"] > 0:
                feature["tags"].append("fruit_present")
            if feature["parts"]["branch"]["detected"]:
                feature["tags"].append("branch_detected")

        elif target_type == "person":
            feature["parts"] = {
                "head":  {"detected": _has_part_inside(detections, ["머리", "head", "얼굴", "face"], bbox)},
                "face":  {"detected": _has_part_inside(detections, ["얼굴", "face", "눈", "eye", "코", "nose", "입", "mouth"], bbox)},
                "hands": {"count": _count_parts_inside(detections, ["손", "hand"], bbox)},
                "feet":  {"count": _count_parts_inside(detections, ["발", "foot", "feet"], bbox)},
                "arms":  {"count": _count_parts_inside(detections, ["팔", "arm"], bbox)},
                "legs":  {"count": _count_parts_inside(detections, ["다리", "leg"], bbox)},
                "shoes": {"detected": _has_part_inside(detections, ["male_shoes", "female_shoes", "sneakers", "shoes"], bbox)},
            }
            if feature["parts"]["head"]["detected"]:
                feature["tags"].append("head_detected")
            if feature["parts"]["face"]["detected"]:
                feature["tags"].append("face_detected")
            if feature["parts"]["hands"]["count"] == 0:
                feature["tags"].append("hands_not_detected")
            if feature["parts"]["feet"]["count"] == 0:
                feature["tags"].append("feet_not_detected")
            if feature["parts"]["shoes"]["detected"]:
                feature["tags"].append("shoes_detected")

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
                "distance_level": _distance_level(house_bbox, tree_bbox, image_width, image_height),
            },
            "house_person": {
                "overlap": _is_overlap(house_bbox, person_bbox),
                "touching": _is_touching(house_bbox, person_bbox),
                "distance_level": _distance_level(house_bbox, person_bbox, image_width, image_height),
            },
            "tree_person": {
                "overlap": _is_overlap(tree_bbox, person_bbox),
                "touching": _is_touching(tree_bbox, person_bbox),
                "distance_level": _distance_level(tree_bbox, person_bbox, image_width, image_height),
            },
            "enclosure_type": "unknown",
        },
    }


def _draw_bboxes_only(image, detections: List[Dict[str, Any]]) -> None:
    for detection in detections:
        bbox = detection["bbox"]
        cv2.rectangle(image, (bbox["x1"], bbox["y1"]), (bbox["x2"], bbox["y2"]), (0, 0, 0), 2)


def _get_korean_font(size: int = 16):
    font_candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for font_path in font_candidates:
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def _get_label_color(label: str) -> tuple:
    label = _clean_label(label)
    fixed_color_map = {
        "house": (220, 20, 60), "house_total": (220, 20, 60), "집": (220, 20, 60), "집전체": (220, 20, 60),
        "tree": (34, 139, 34), "tree_total": (34, 139, 34), "나무": (34, 139, 34), "나무전체": (34, 139, 34),
        "person": (30, 144, 255), "person_total": (30, 144, 255), "사람": (30, 144, 255), "사람전체": (30, 144, 255),
        "male_person": (30, 144, 255), "female_person": (30, 144, 255),
    }
    if label in fixed_color_map:
        return fixed_color_map[label]
    color_palette = [
        (255, 140, 0), (148, 0, 211), (255, 105, 180), (0, 191, 255), (255, 215, 0),
        (139, 69, 19), (0, 128, 128), (128, 0, 0), (72, 61, 139), (46, 139, 87),
        (255, 99, 71), (105, 105, 105), (65, 105, 225), (154, 205, 50), (199, 21, 133),
    ]
    label_hash = sum(ord(char) for char in label)
    return color_palette[label_hash % len(color_palette)]


def _save_single_result_image(
    original_image_path: str,
    detections: List[Dict[str, Any]],
    suffix: str,
) -> str:
    original_path = Path(original_image_path)
    image = cv2.imread(str(original_path))
    if image is None:
        raise ValueError(f"결과 이미지를 생성할 수 없습니다: {original_path}")
    _draw_bboxes_only(image, detections)
    result_dir = Path("uploads") / "htp" / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / f"{original_path.stem}_{suffix}{original_path.suffix}"
    cv2.imwrite(str(result_path), image)
    return str(result_path)


def _save_debug_all_result_image(
    original_image_path: str,
    detections: List[Dict[str, Any]],
) -> str:
    original_path = Path(original_image_path)
    image_bgr = cv2.imread(str(original_path))
    if image_bgr is None:
        raise ValueError(f"디버그 이미지를 생성할 수 없습니다: {original_path}")
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image_rgb)
    draw = ImageDraw.Draw(pil_image)
    font = _get_korean_font(size=15)
    for detection in detections:
        bbox = detection["bbox"]
        raw_label = detection["label"]
        label = detection["display_label"]
        confidence = detection["confidence"]
        color = _get_label_color(raw_label)
        x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
        text = f"{label} {confidence:.2f}"
        draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=2)
        text_bbox = draw.textbbox((x1, y1), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_y = max(y1 - text_height - 6, 0)
        draw.rectangle([(x1, text_y), (x1 + text_width + 8, text_y + text_height + 6)], fill=color, outline=color)
        draw.text((x1 + 4, text_y + 3), text, fill=(255, 255, 255), font=font)
    result_dir = Path("uploads") / "htp" / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / f"{original_path.stem}_yolo_debug_all{original_path.suffix}"
    result_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(result_path), result_bgr)
    return str(result_path)


def _build_result_image_paths(
    original_image_path: str,
    display_detections: List[Dict[str, Any]],
    all_detections: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Optional[str]]:
    grouped = {
        "house":  [d for d in display_detections if d["type"] == "house"],
        "tree":   [d for d in display_detections if d["type"] == "tree"],
        "person": [d for d in display_detections if d["type"] == "person"],
    }
    result_image_paths = {
        "all": _save_single_result_image(original_image_path, display_detections, "yolo_result_all"),
        "house": None,
        "tree": None,
        "person": None,
        "debug_all": None,
    }
    for key in ["house", "tree", "person"]:
        if grouped[key]:
            result_image_paths[key] = _save_single_result_image(
                original_image_path, grouped[key], f"yolo_result_{key}"
            )
    if all_detections:
        result_image_paths["debug_all"] = _save_debug_all_result_image(
            original_image_path, all_detections
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
        "house": None, "tree": None, "person": None, "debug_all": None,
    }
    yolo_result_json["model"] = {
        "house":  YOLO_HTP_MODEL_NAME_HOUSE,
        "tree":   YOLO_HTP_MODEL_NAME_TREE,
        "person": YOLO_HTP_MODEL_NAME_PERSON,
    }
    yolo_result_json["fallback"] = True
    yolo_result_json["fallback_reason"] = error_message
    yolo_result_json["result_image_paths"] = result_image_paths
    return {
        "result_image_path": result_image_paths["all"],
        "result_image_paths": result_image_paths,
        "yolo_result_json": yolo_result_json,
        "visual_features_json": visual_features_json,
        "display_detections": yolo_result_json["display_detections"],
    }


def analyze_htp_image_with_yolo(original_image_path: str) -> Dict[str, Any]:
    """HTP 이미지에 대해 house / tree / person 모델을 각각 추론 후 결과를 병합한다.

    downstream(report / PDI / frontend)은 기존 single-model 결과 구조와 동일하게 수신한다.
    """
    try:
        image_path = Path(original_image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"분석할 이미지 파일을 찾을 수 없습니다: {image_path}")

        models = _load_yolo_models()

        # ── 3개 모델 각각 inference → detections merge ────────────────
        all_detections: List[Dict[str, Any]] = []

        for key, model in models.items():
            results = model.predict(
                source=str(image_path),
                imgsz=YOLO_HTP_IMAGE_SIZE,
                conf=YOLO_HTP_CONF_THRESHOLD,
                verbose=False,
            )
            if not results:
                continue
            detections = _extract_detections_from_result(results[0])
            all_detections.extend(detections)
        # ─────────────────────────────────────────────────────────────

        if not all_detections:
            raise RuntimeError("3개 모델 모두 detection 결과가 없습니다.")

        # 이후 로직은 기존 single-model 흐름과 완전히 동일
        display_detections = _create_display_detections(all_detections)

        result_image_paths = _build_result_image_paths(
            original_image_path=str(image_path),
            display_detections=display_detections,
            all_detections=all_detections,
        )

        yolo_result_json = {
            "model": {
                "house":  YOLO_HTP_MODEL_NAME_HOUSE,
                "tree":   YOLO_HTP_MODEL_NAME_TREE,
                "person": YOLO_HTP_MODEL_NAME_PERSON,
            },
            "weights_path": {
                "house":  YOLO_HTP_HOUSE_WEIGHTS_PATH,
                "tree":   YOLO_HTP_TREE_WEIGHTS_PATH,
                "person": YOLO_HTP_PERSON_WEIGHTS_PATH,
            },
            "confidence_threshold": YOLO_HTP_CONF_THRESHOLD,
            "fallback": False,
            "all_detections": all_detections,
            "display_detections": display_detections,
            "result_image_paths": result_image_paths,
            "all_detection_count": len(all_detections),
            "display_detection_count": len(display_detections),
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