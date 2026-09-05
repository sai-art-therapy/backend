import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from PIL import Image

from app.core.config import (
    OPENAI_VLM_FALLBACK_ENABLED,
    OPENAI_VLM_MODEL,
    OPENAI_VLM_VERIFY_CONF_MAX,
    YOLO_HTP_CONF_THRESHOLD,
)
from app.services.openai_service import client


_PARENT_ALIASES = {
    "house": {"house", "house_total", "집", "집전체"},
    "tree": {"tree", "tree_total", "나무", "나무전체"},
    "person": {
        "person", "person_total", "사람", "사람전체", "male_person",
        "female_person", "남자", "여자", "아이",
    },
}

# Values are canonical labels already understood by yolo_service.py. Aliases are
# used only to decide whether YOLO has already found that canonical element.
_DETAIL_ALIASES = {
    "roof": {"roof", "지붕"},
    "door": {"door", "문"},
    "window": {"window", "창문"},
    "chimney": {"chimney", "굴뚝"},
    "trunk": {"trunk", "줄기", "나무줄기"},
    "crown": {"crown", "수관"},
    "branch": {"branch", "가지"},
    "root": {"root", "뿌리"},
    "fruit": {"fruit", "열매"},
    "flower": {"flower", "꽃"},
    "eye": {"eye", "눈"},
    "nose": {"nose", "코"},
    "mouth": {"mouth", "입"},
    "arm": {"arm", "팔"},
    "hand": {"hand", "손"},
    "leg": {"leg", "다리"},
    "foot": {"foot", "feet", "발"},
    "shoes": {"shoes", "sneakers", "male_shoes", "female_shoes", "신발"},
}

_PARENT_DETAILS = {
    "house": ("roof", "door", "window", "chimney"),
    "tree": ("trunk", "branch", "root", "fruit", "flower"),
    "person": ("eye", "nose", "mouth", "arm", "hand", "leg", "foot", "shoes"),
}

_RECOVERABLE_MAIN_LABELS = ("house", "person")
_DETAIL_PARENT = {
    detail: parent
    for parent, details in _PARENT_DETAILS.items()
    for detail in details
}


def _metadata(**overrides: Any) -> Dict[str, Any]:
    value = {
        "triggered": False,
        "verified_count": 0,
        "removed_count": 0,
        "added_count": 0,
        "error": None,
    }
    value.update(overrides)
    return value


def _missing_labels(
    detections: List[Dict[str, Any]], selected_parent_types: Set[str]
) -> List[str]:
    labels = {str(item.get("label", "")).lower().strip() for item in detections}
    requested: List[str] = []
    for parent in selected_parent_types:
        for canonical in _PARENT_DETAILS[parent]:
            if canonical == "branch":
                continue
            if labels.isdisjoint(_DETAIL_ALIASES[canonical]):
                requested.append(canonical)
    return requested


def _main_recovery_labels(detections: List[Dict[str, Any]]) -> List[str]:
    labels = {str(item.get("label", "")).lower().strip() for item in detections}
    return [
        parent
        for parent in _RECOVERABLE_MAIN_LABELS
        if labels.isdisjoint(_PARENT_ALIASES[parent])
    ]


def _encode_image(image_path: Path) -> Tuple[str, int, int]:
    with Image.open(image_path) as image:
        width, height = image.size
        image.verify()
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}", width, height


def _response_schema() -> Dict[str, Any]:
    bbox_schema = {
        "anyOf": [
            {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
            {"type": "null"},
        ]
    }
    return {
        "type": "object",
        "properties": {
            "verified": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {"type": "integer"},
                        "present": {"type": "boolean"},
                    },
                    "required": ["candidate_id", "present"],
                    "additionalProperties": False,
                },
            },
            "missing": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "present": {"type": "boolean"},
                        "bbox": bbox_schema,
                    },
                    "required": ["label", "present", "bbox"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["verified", "missing"],
        "additionalProperties": False,
    }


def _prompt(
    candidates: List[Dict[str, Any]],
    missing_labels: List[str],
    main_recovery_labels: List[str],
    shoe_recovery_requested: bool,
    width: int,
    height: int,
) -> str:
    candidate_payload = [
        {
            "candidate_id": item["candidate_id"],
            "label": item["detection"]["label"],
            "confidence": item["detection"]["confidence"],
            "bbox": item["detection"]["bbox"],
        }
        for item in candidates
    ]
    return f"""You verify only visible elements in an HTP drawing.
Do not infer psychological meaning.
Do not provide mental-health interpretation.
Only verify visible drawing elements.

The original image is {width}x{height} pixels. Every bbox uses original-image pixel
coordinates [x1, y1, x2, y2], with origin at the top-left. Coordinates must satisfy
0 <= x1 < x2 <= {width} and 0 <= y1 < y2 <= {height}.

For every low-confidence candidate, return its candidate_id and whether that exact
labeled element is visibly present near the supplied bbox. For every requested main
object or missing detail label, return the label and whether it is visibly present. If
present, return its tight pixel bbox; if absent, return null for bbox. Do not add labels
that were not requested.

Requested main-object recovery labels are conservative whole-object checks. Set a main
object present=true only when the complete house or person is clearly and directly
visible, and return a bbox enclosing that whole object. Do not infer a main object from
an isolated part, such as a shoe, hand, window, or line.

The following conservative rules apply only to requested missing labels, not to the
low-confidence candidate verification above:
- Set present=true only when the drawing contains clear, direct visual evidence of the
  missing element itself. Do not infer that an element exists merely because it would
  normally or structurally be expected.
- If the element is ambiguous, or if unrelated lines must be interpreted as that
  element, set present=false.
- For root: set present=true only when clearly root-shaped lines visibly extend from
  the base of the tree. A ground line, the point where the trunk meets the ground, and
  nearby unrelated lines are not roots.
- For shoes: set present=true only when a shoe outline visibly distinct from the foot
  or leg is drawn. Do not infer shoes from the presence or shape of a foot alone.
- For fruit: set present=true only for a clearly drawn fruit-like object located in the
  tree or crown. A single ambiguous dot, decoration, eye-like circle, or unrelated small
  round mark is not fruit. If its identity as fruit is uncertain, set present=false.
{'''- Shoes is also requested as a conditional replacement. Verify each existing shoe
  candidate independently and do not keep a wrong candidate. In the missing result for
  shoes, return present=true with a new tight bbox only if all supplied shoe candidates
  are invalid and a separate, clear shoe outline is directly visible at the person’s
  actual foot area. Otherwise return present=false with bbox=null.''' if shoe_recovery_requested else ''}

Low-confidence candidates:
{json.dumps(candidate_payload, ensure_ascii=False)}

Missing labels to check because their parent object exists:
{json.dumps(missing_labels, ensure_ascii=False)}

Missing main objects to recover:
{json.dumps(main_recovery_labels, ensure_ascii=False)}
"""


def _validate_bbox(value: Any, width: int, height: int) -> Dict[str, int]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("present missing-element result has no four-value bbox")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise ValueError("bbox coordinates must be numbers")
    x1, y1, x2, y2 = (int(round(item)) for item in value)
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("bbox is outside the original-image pixel coordinate system")
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _apply_response(
    original: List[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
    missing_labels: List[str],
    main_recovery_labels: List[str],
    shoe_recovery_requested: bool,
    protected_labels: Set[str],
    payload: Any,
    width: int,
    height: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("VLM response is not a JSON object")
    verified = payload.get("verified")
    missing = payload.get("missing")
    if not isinstance(verified, list) or not isinstance(missing, list):
        raise ValueError("VLM response arrays are missing")

    expected_ids = {item["candidate_id"] for item in candidates}
    decisions: Dict[int, bool] = {}
    for item in verified:
        if not isinstance(item, dict) or type(item.get("candidate_id")) is not int or type(item.get("present")) is not bool:
            raise ValueError("invalid verified item")
        candidate_id = item["candidate_id"]
        if candidate_id not in expected_ids or candidate_id in decisions:
            raise ValueError("unknown or duplicate candidate_id")
        decisions[candidate_id] = item["present"]
    if set(decisions) != expected_ids:
        raise ValueError("not every candidate was verified")

    expected_labels = set(missing_labels) | set(main_recovery_labels)
    proposed_additions: List[Dict[str, Any]] = []
    seen_labels = set()
    for item in missing:
        if not isinstance(item, dict) or type(item.get("present")) is not bool:
            raise ValueError("invalid missing item")
        label = item.get("label")
        if label not in expected_labels or label in seen_labels:
            raise ValueError("unknown or duplicate missing label")
        seen_labels.add(label)
        if item["present"]:
            is_main_recovery = label in main_recovery_labels
            proposed_additions.append({
                "label": label,
                "display_label": label,
                # Compatibility value only.
                # This is NOT a calibrated confidence score from the VLM.
                "confidence": 0.5,
                "source": "openai_vlm",
                "bbox": _validate_bbox(item.get("bbox"), width, height),
                "use_for_display": is_main_recovery,
                "use_for_analysis": True,
            })
        elif item.get("bbox") is not None:
            raise ValueError("absent missing element must have a null bbox")
    if seen_labels != expected_labels:
        raise ValueError("not every missing label was checked")

    rejected_indexes = {
        item["detection_index"]
        for item in candidates
        if not decisions[item["candidate_id"]]
        and str(item["detection"].get("label", "")).lower().strip()
        not in protected_labels
    }
    corrected = [item for index, item in enumerate(original) if index not in rejected_indexes]

    main_additions = [
        item for item in proposed_additions if item["label"] in main_recovery_labels
    ]
    corrected.extend(main_additions)
    detail_additions = [
        item for item in proposed_additions
        if item["label"] not in main_recovery_labels
        and _detail_addition_has_valid_parent(item, corrected)
    ]

    additions = detail_additions
    if shoe_recovery_requested:
        shoe_candidate_ids = {
            item["candidate_id"]
            for item in candidates
            if str(item["detection"].get("label", "")).lower().strip()
            in _DETAIL_ALIASES["shoes"]
        }
        all_shoe_candidates_rejected = bool(shoe_candidate_ids) and all(
            not decisions[candidate_id] for candidate_id in shoe_candidate_ids
        )
        shoe_additions = [
            item for item in detail_additions if item["label"] == "shoes"
        ]
        additions = [
            item for item in detail_additions if item["label"] != "shoes"
        ]
        if (
            all_shoe_candidates_rejected
            and not _has_spatial_shoe_evidence(corrected)
            and shoe_additions
            and _shoe_replacement_passes_spatial(shoe_additions[0], original)
        ):
            additions.extend(shoe_additions)

    corrected.extend(additions)
    return corrected, _metadata(
        triggered=True,
        verified_count=len(candidates),
        removed_count=len(rejected_indexes),
        added_count=len(main_additions) + len(additions),
    )


def _detail_addition_has_valid_parent(
    addition: Dict[str, Any], detections: List[Dict[str, Any]]
) -> bool:
    from app.services.yolo_service import (
        _clean_label,
        _is_center_inside,
        _pick_best_bbox,
    )

    label = addition["label"]
    parent = _DETAIL_PARENT.get(label)
    if parent is None:
        return False
    parent_bbox = _pick_best_bbox(
        detections, parent, allow_subobject_fallback=False
    )
    if parent_bbox is None:
        return False
    if label != "fruit":
        return True

    crown_candidates = [
        detection
        for detection in detections
        if _clean_label(detection.get("label", "")) in _DETAIL_ALIASES["crown"]
    ]
    fruit_parent_bbox = (
        max(crown_candidates, key=lambda item: item["confidence"])["bbox"]
        if crown_candidates
        else parent_bbox
    )
    return _is_center_inside(addition["bbox"], fruit_parent_bbox)


def _has_spatial_shoe_evidence(detections: List[Dict[str, Any]]) -> bool:
    from app.services.yolo_service import _has_shoes_spatial, _pick_best_bbox

    person_bbox = _pick_best_bbox(
        detections, "person", allow_subobject_fallback=False
    )
    return _has_shoes_spatial(detections, person_bbox)


def _shoe_replacement_passes_spatial(
    replacement: Dict[str, Any], detections: List[Dict[str, Any]]
) -> bool:
    from app.services.yolo_service import (
        _is_shoe_spatially_consistent,
        _pick_best_bbox,
    )

    person_bbox = _pick_best_bbox(
        detections, "person", allow_subobject_fallback=False
    )
    return _is_shoe_spatially_consistent(
        replacement["bbox"], person_bbox, "shoes"
    )


def apply_vlm_fallback(
    original_image_path: str,
    all_detections: List[Dict[str, Any]],
    protected_labels: Set[str],
    trigger_a_detection_indexes: Set[int],
    selected_parent_types: Set[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return corrected detections, or the exact original list on every VLM failure."""
    if not OPENAI_VLM_FALLBACK_ENABLED:
        return all_detections, _metadata()

    candidates = []
    for index, detection in enumerate(all_detections):
        try:
            confidence = float(detection["confidence"])
        except (KeyError, TypeError, ValueError):
            continue
        if (
            index in trigger_a_detection_indexes
            and YOLO_HTP_CONF_THRESHOLD <= confidence < OPENAI_VLM_VERIFY_CONF_MAX
        ):
            candidates.append({
                "candidate_id": len(candidates),
                "detection_index": index,
                "detection": detection,
            })

    spatially_relevant_detections = [
        detection
        for index, detection in enumerate(all_detections)
        if index in trigger_a_detection_indexes
    ]
    missing_labels = _missing_labels(
        spatially_relevant_detections, selected_parent_types
    )
    main_recovery_labels = _main_recovery_labels(all_detections)
    spatial_shoe_indexes = {
        index
        for index in trigger_a_detection_indexes
        if str(all_detections[index].get("label", "")).lower().strip()
        in _DETAIL_ALIASES["shoes"]
    }
    shoe_candidate_indexes = {
        item["detection_index"]
        for item in candidates
        if str(item["detection"].get("label", "")).lower().strip()
        in _DETAIL_ALIASES["shoes"]
    }
    shoe_recovery_requested = (
        "person" in selected_parent_types
        and bool(shoe_candidate_indexes)
        and spatial_shoe_indexes == shoe_candidate_indexes
    )
    if shoe_recovery_requested and "shoes" not in missing_labels:
        missing_labels.append("shoes")
    if not candidates and not missing_labels and not main_recovery_labels:
        return all_detections, _metadata()

    try:
        image_url, width, height = _encode_image(Path(original_image_path))
        response = client.with_options(timeout=30.0).responses.create(
            model=OPENAI_VLM_MODEL,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _prompt(
                        candidates,
                        missing_labels,
                        main_recovery_labels,
                        shoe_recovery_requested,
                        width,
                        height,
                    )},
                    {"type": "input_image", "image_url": image_url},
                ],
            }],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "htp_visible_element_verification",
                    "strict": True,
                    "schema": _response_schema(),
                }
            },
        )
        payload = json.loads(response.output_text)
        return _apply_response(
            all_detections,
            candidates,
            missing_labels,
            main_recovery_labels,
            shoe_recovery_requested,
            protected_labels,
            payload,
            width,
            height,
        )
    except Exception as exc:
        return all_detections, _metadata(triggered=True, error=f"{type(exc).__name__}: {exc}")
