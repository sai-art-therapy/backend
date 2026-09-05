"""Measure repeatability of the existing YOLO + OpenAI VLM production path."""

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


EVALUATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALUATION_DIR.parent
IMAGE_DIR = REPO_ROOT.parent / "test_image"
GROUND_TRUTH_PATH = EVALUATION_DIR / "ground_truth.json"
RESULTS_DIR = EVALUATION_DIR / "results"
REPEATABILITY_DIR = RESULTS_DIR / "repeatability"

IMAGE_IDS = (
    "htp_test_01",
    "htp_test_02",
    "htp_test_03",
    "htp_test_04",
    "htp_test_05",
    "htp_test_06",
    "htp_test_07",
    "htp_test_08",
    "htp_test_09",
    "htp_test_10",
    "htp_test_13",
)
RUN_COUNT = 3
BOOLEAN_PATHS = {
    "shoes": ("person", "parts", "shoes", "detected"),
    "root": ("tree", "parts", "roots", "detected"),
    "branch": ("tree", "parts", "branch", "detected"),
}
FRUIT_COUNT_PATH = ("tree", "parts", "fruit", "count")
SHOE_LABELS = {"shoes", "sneakers", "male_shoes", "female_shoes"}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_path.replace(path)


def _nested_get(value: Dict[str, Any], path: Iterable[str]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _detection_key(detection: Dict[str, Any]) -> Tuple[Any, ...]:
    bbox = detection.get("bbox") or {}
    return (
        detection.get("label"),
        detection.get("confidence"),
        bbox.get("x1"),
        bbox.get("y1"),
        bbox.get("x2"),
        bbox.get("y2"),
    )


def _compact_detection(detection: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "label": detection.get("label"),
        "confidence": detection.get("confidence"),
        "bbox": detection.get("bbox"),
        "source": detection.get("source"),
        "use_for_analysis": detection.get("use_for_analysis"),
    }


def _run_once(image_id: str, run_dir: Path) -> Path:
    worker_dir = run_dir / "_worker"
    environment = os.environ.copy()
    environment["OPENAI_VLM_FALLBACK_ENABLED"] = "true"
    command = [
        sys.executable,
        str(EVALUATION_DIR / "run_mode.py"),
        "--mode",
        "yolo_gpt",
        "--image-dir",
        str(IMAGE_DIR.resolve()),
        "--ground-truth",
        str(GROUND_TRUTH_PATH.resolve()),
        "--results-dir",
        str(worker_dir.resolve()),
        "--image-id",
        image_id,
    ]
    subprocess.run(command, cwd=REPO_ROOT, env=environment, check=True)
    source_path = worker_dir / "yolo_gpt" / f"{image_id}.json"
    destination_path = run_dir / f"{image_id}.json"
    source_path.replace(destination_path)
    shutil.rmtree(worker_dir)
    return destination_path


def _analyse_run(
    image_id: str,
    run_number: int,
    raw: Dict[str, Any],
    baseline: Dict[str, Any],
    ground_truth: Dict[str, Any],
) -> Dict[str, Any]:
    visual_features = raw.get("visual_features_json") or {}
    yolo_result = raw.get("yolo_result_json") or {}
    metadata = yolo_result.get("vlm_fallback") or {}
    before = baseline.get("yolo_result_json", {}).get("all_detections") or []
    after = yolo_result.get("all_detections") or []
    before_keys = {_detection_key(item): item for item in before}
    after_keys = {_detection_key(item): item for item in after}
    removed = [item for key, item in before_keys.items() if key not in after_keys]
    added = [item for key, item in after_keys.items() if key not in before_keys]

    shoes = _nested_get(visual_features, BOOLEAN_PATHS["shoes"])
    root = _nested_get(visual_features, BOOLEAN_PATHS["root"])
    branch = _nested_get(visual_features, BOOLEAN_PATHS["branch"])
    fruit_count = _nested_get(visual_features, FRUIT_COUNT_PATH)
    truth = ground_truth[image_id]

    baseline_shoes = [item for item in before if item.get("label") in SHOE_LABELS]
    retained_shoes = [
        item for item in baseline_shoes if _detection_key(item) in after_keys
    ]
    removed_shoes = [item for item in removed if item.get("label") in SHOE_LABELS]
    added_branches = [
        item
        for item in added
        if item.get("label") == "branch" and item.get("source") == "openai_vlm"
    ]
    removed_roots = [item for item in removed if item.get("label") in {"root", "roots"}]

    return {
        "image": image_id,
        "run": run_number,
        "shoes": shoes,
        "root": root,
        "branch": branch,
        "fruit_count": fruit_count,
        "shoes_correct": shoes == truth["person"]["shoes"],
        "root_correct": root == truth["tree"]["root"],
        "branch_correct": branch == truth["tree"]["branch"],
        "fruit_count_correct": fruit_count == truth["tree"]["fruit_count"],
        "verified_count": int(metadata.get("verified_count", 0)),
        "added_count": int(metadata.get("added_count", 0)),
        "removed_count": int(metadata.get("removed_count", 0)),
        "vlm_error": metadata.get("error"),
        "baseline_shoe_detections": [_compact_detection(item) for item in baseline_shoes],
        "retained_shoe_detections": [_compact_detection(item) for item in retained_shoes],
        "removed_shoe_detections": [_compact_detection(item) for item in removed_shoes],
        "branch_added_by_vlm": bool(added_branches),
        "added_branch_detections": [_compact_detection(item) for item in added_branches],
        "removed_root_detections": [_compact_detection(item) for item in removed_roots],
        "added_detections": [_compact_detection(item) for item in added],
        "removed_detections": [_compact_detection(item) for item in removed],
    }


def _consistency(records: List[Dict[str, Any]], attribute: str) -> Dict[str, Any]:
    values = [record[attribute] for record in records]
    true_count = sum(value is True for value in values)
    false_count = sum(value is False for value in values)
    dominant_count = max(true_count, false_count)
    rate = round(dominant_count / len(values), 3)
    classification = "deterministic_like" if rate == 1.0 else "moderately_variable"
    return {
        "values": values,
        "all_three_identical": len(set(values)) == 1,
        "true_count": true_count,
        "false_count": false_count,
        "consistency_rate": rate,
        "classification": classification,
    }


def _build_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_image: Dict[str, List[Dict[str, Any]]] = {
        image_id: [record for record in records if record["image"] == image_id]
        for image_id in IMAGE_IDS
    }
    image_attribute_consistency = {
        image_id: {
            attribute: _consistency(image_records, attribute)
            for attribute in BOOLEAN_PATHS
        }
        for image_id, image_records in by_image.items()
    }
    overall_consistency = {}
    for attribute in BOOLEAN_PATHS:
        rates = [
            image_attribute_consistency[image_id][attribute]["consistency_rate"]
            for image_id in IMAGE_IDS
        ]
        overall_consistency[attribute] = {
            "mean_consistency_rate": round(sum(rates) / len(rates), 3),
            "deterministic_like_images": sum(rate == 1.0 for rate in rates),
            "moderately_variable_images": sum(rate < 1.0 for rate in rates),
        }

    action_variability = {}
    for image_id, image_records in by_image.items():
        signatures = [
            {
                "added": [_detection_key(item) for item in record["added_detections"]],
                "removed": [_detection_key(item) for item in record["removed_detections"]],
            }
            for record in image_records
        ]
        action_variability[image_id] = {
            "varies": len({json.dumps(item, sort_keys=True) for item in signatures}) > 1,
            "runs": signatures,
        }

    return {
        "image_ids": list(IMAGE_IDS),
        "run_count": RUN_COUNT,
        "total_image_runs": len(IMAGE_IDS) * RUN_COUNT,
        "records": records,
        "image_attribute_consistency": image_attribute_consistency,
        "overall_consistency": overall_consistency,
        "vlm_action_variability": action_variability,
    }


def _write_csv(path: Path, records: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "image",
        "run",
        "shoes",
        "root",
        "branch",
        "fruit_count",
        "shoes_correct",
        "root_correct",
        "branch_correct",
        "fruit_count_correct",
        "verified_count",
        "added_count",
        "removed_count",
        "branch_added_by_vlm",
        "vlm_error",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: record[key] for key in fieldnames} for record in records)


def main() -> None:
    ground_truth = _read_json(GROUND_TRUTH_PATH)
    baselines = {
        image_id: _read_json(RESULTS_DIR / "yolo_only" / f"{image_id}.json")
        for image_id in IMAGE_IDS
    }
    records = []
    for run_number in range(1, RUN_COUNT + 1):
        run_dir = REPEATABILITY_DIR / f"run_{run_number:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        for image_id in IMAGE_IDS:
            raw_path = _run_once(image_id, run_dir)
            raw = _read_json(raw_path)
            records.append(
                _analyse_run(
                    image_id, run_number, raw, baselines[image_id], ground_truth
                )
            )
            print(f"[repeatability run_{run_number:02d}] {image_id}: saved")

    summary = _build_summary(records)
    _write_csv(RESULTS_DIR / "repeatability_summary.csv", records)
    _write_json(RESULTS_DIR / "repeatability_summary.json", summary)


if __name__ == "__main__":
    main()
