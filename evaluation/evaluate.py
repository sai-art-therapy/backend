"""Evaluate production YOLO-only and YOLO+VLM HTP analysis results."""

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


EVALUATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALUATION_DIR.parent
DEFAULT_IMAGE_DIR = REPO_ROOT.parent / "test_image"
DEFAULT_GROUND_TRUTH = EVALUATION_DIR / "ground_truth.json"
DEFAULT_RESULTS_DIR = EVALUATION_DIR / "results"

MODES = ("yolo_only", "yolo_gpt")
ATTRIBUTES: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    ("house", "window_count", "count", ("house", "parts", "window", "count")),
    ("house", "chimney", "boolean", ("house", "parts", "chimney", "detected")),
    ("tree", "fruit_count", "count", ("tree", "parts", "fruit", "count")),
    ("tree", "flower_count", "count", ("tree", "parts", "flower", "count")),
    ("tree", "root", "boolean", ("tree", "parts", "roots", "detected")),
    ("tree", "branch", "boolean", ("tree", "parts", "branch", "detected")),
    ("person", "shoes", "boolean", ("person", "parts", "shoes", "detected")),
    ("person", "hand_count", "count", ("person", "parts", "hands", "count")),
    ("person", "foot_count", "count", ("person", "parts", "feet", "count")),
    ("person", "arm_count", "count", ("person", "parts", "arms", "count")),
    ("person", "leg_count", "count", ("person", "parts", "legs", "count")),
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _nested_get(value: Dict[str, Any], path: Iterable[str]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def normalize_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Project production visual_features_json into the ground-truth shape."""
    visual_features = analysis.get("visual_features_json", {})
    prediction: Dict[str, Dict[str, Any]] = {
        "house": {},
        "tree": {},
        "person": {},
    }
    for category, attribute, _, visual_path in ATTRIBUTES:
        prediction[category][attribute] = _nested_get(visual_features, visual_path)
    return prediction


def _run_mode(
    mode: str,
    image_dir: Path,
    ground_truth_path: Path,
    results_dir: Path,
    image_id: str = None,
) -> None:
    environment = os.environ.copy()
    environment["OPENAI_VLM_FALLBACK_ENABLED"] = (
        "true" if mode == "yolo_gpt" else "false"
    )
    command = [
        sys.executable,
        str(EVALUATION_DIR / "run_mode.py"),
        "--mode",
        mode,
        "--image-dir",
        str(image_dir.resolve()),
        "--ground-truth",
        str(ground_truth_path.resolve()),
        "--results-dir",
        str(results_dir.resolve()),
    ]
    if image_id:
        command.extend(("--image-id", image_id))
    subprocess.run(command, cwd=REPO_ROOT, env=environment, check=True)


def _build_predictions(
    mode: str,
    ground_truth: Dict[str, Any],
    results_dir: Path,
) -> Dict[str, Any]:
    predictions = {}
    for image_id in ground_truth:
        raw_path = results_dir / mode / f"{image_id}.json"
        if not raw_path.is_file():
            raise FileNotFoundError(f"Missing raw result: {raw_path}")
        predictions[image_id] = normalize_analysis(_read_json(raw_path))
    output_path = results_dir / f"predictions_{mode}.json"
    _write_json(output_path, predictions)
    return predictions


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value


def _validate_ground_truth(ground_truth: Dict[str, Any]) -> None:
    for image_id, expected in ground_truth.items():
        for category, attribute, kind, _ in ATTRIBUTES:
            value = expected.get(category, {}).get(attribute)
            if value is None:
                continue
            if kind == "boolean" and type(value) is not bool:
                raise TypeError(f"{image_id}.{category}.{attribute} must be boolean or null")
            if kind == "count" and (type(value) is not int or value < 0):
                raise TypeError(
                    f"{image_id}.{category}.{attribute} must be a non-negative integer or null"
                )


def _comparison_rows(
    ground_truth: Dict[str, Any],
    predictions: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows = []
    for image_id, expected in ground_truth.items():
        for category, attribute, _, _ in ATTRIBUTES:
            truth = expected[category][attribute]
            yolo_only = predictions["yolo_only"][image_id][category][attribute]
            yolo_gpt = predictions["yolo_gpt"][image_id][category][attribute]
            rows.append({
                "image": image_id,
                "category": category,
                "attribute": attribute,
                "ground_truth": _csv_value(truth),
                "yolo_only": _csv_value(yolo_only),
                "yolo_gpt": _csv_value(yolo_gpt),
                "yolo_only_correct": "" if truth is None else yolo_only == truth,
                "yolo_gpt_correct": "" if truth is None else yolo_gpt == truth,
            })
    return rows


def _write_comparison_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "image",
        "category",
        "attribute",
        "ground_truth",
        "yolo_only",
        "yolo_gpt",
        "yolo_only_correct",
        "yolo_gpt_correct",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_ratio(numerator: int, denominator: int) -> Any:
    return round(numerator / denominator, 6) if denominator else None


def _score_mode(
    mode: str,
    ground_truth: Dict[str, Any],
    predictions: Dict[str, Any],
    results_dir: Path,
) -> Dict[str, Any]:
    boolean_metrics = {}
    count_metrics = {}
    all_exact: List[bool] = []
    all_count_exact: List[bool] = []
    all_count_errors: List[int] = []

    for category, attribute, kind, _ in ATTRIBUTES:
        pairs = []
        for image_id, expected in ground_truth.items():
            truth = expected[category][attribute]
            if truth is None:
                continue
            prediction = predictions[image_id][category][attribute]
            if prediction is None:
                raise ValueError(
                    f"Missing prediction for {mode}:{image_id}.{category}.{attribute}"
                )
            pairs.append((truth, prediction))
            all_exact.append(truth == prediction)

        metric_key = f"{category}.{attribute}"
        if kind == "boolean":
            tp = sum(truth is True and prediction is True for truth, prediction in pairs)
            fp = sum(truth is False and prediction is True for truth, prediction in pairs)
            fn = sum(truth is True and prediction is False for truth, prediction in pairs)
            tn = sum(truth is False and prediction is False for truth, prediction in pairs)
            precision = _safe_ratio(tp, tp + fp)
            recall = _safe_ratio(tp, tp + fn)
            f1 = _safe_ratio(2 * tp, 2 * tp + fp + fn)
            boolean_metrics[metric_key] = {
                "evaluated_count": len(pairs),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "accuracy": _safe_ratio(tp + tn, len(pairs)),
            }
        else:
            errors = [abs(truth - prediction) for truth, prediction in pairs]
            exact = [truth == prediction for truth, prediction in pairs]
            all_count_errors.extend(errors)
            all_count_exact.extend(exact)
            count_metrics[metric_key] = {
                "evaluated_count": len(pairs),
                "exact_match_accuracy": _safe_ratio(sum(exact), len(exact)),
                "mae": round(sum(errors) / len(errors), 6) if errors else None,
                "total_absolute_error": sum(errors),
            }

    vlm_images = {}
    for image_id in ground_truth:
        raw = _read_json(results_dir / mode / f"{image_id}.json")
        metadata = raw.get("yolo_result_json", {}).get("vlm_fallback") or {}
        vlm_images[image_id] = {
            "triggered": bool(metadata.get("triggered", False)),
            "verified_count": int(metadata.get("verified_count", 0)),
            "added_count": int(metadata.get("added_count", 0)),
            "removed_count": int(metadata.get("removed_count", 0)),
            "error": metadata.get("error"),
        }

    return {
        "boolean": boolean_metrics,
        "count": count_metrics,
        "count_overall": {
            "evaluated_count": len(all_count_exact),
            "micro_exact_match_accuracy": _safe_ratio(
                sum(all_count_exact), len(all_count_exact)
            ),
            "mae": (
                round(sum(all_count_errors) / len(all_count_errors), 6)
                if all_count_errors
                else None
            ),
        },
        "overall": {
            "evaluated_attribute_count": len(all_exact),
            "exact_match_accuracy": _safe_ratio(sum(all_exact), len(all_exact)),
        },
        "vlm": {
            "called_image_count": sum(item["triggered"] for item in vlm_images.values()),
            "verified_detection_count": sum(
                item["verified_count"] for item in vlm_images.values()
            ),
            "added_detection_count": sum(
                item["added_count"] for item in vlm_images.values()
            ),
            "removed_detection_count": sum(
                item["removed_count"] for item in vlm_images.values()
            ),
            "images": vlm_images,
        },
    }


def _compare(
    ground_truth: Dict[str, Any],
    results_dir: Path,
) -> None:
    predictions = {
        mode: _read_json(results_dir / f"predictions_{mode}.json")
        for mode in MODES
    }
    rows = _comparison_rows(ground_truth, predictions)
    _write_comparison_csv(results_dir / "comparison.csv", rows)
    summary = {
        mode: _score_mode(mode, ground_truth, predictions[mode], results_dir)
        for mode in MODES
    }
    _write_json(results_dir / "summary.json", summary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("all", "yolo_only", "yolo_gpt", "compare"),
        default="all",
    )
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument(
        "--image-id",
        help="Evaluate only one ground-truth image id, for example htp_test_01",
    )
    args = parser.parse_args()

    ground_truth = _read_json(args.ground_truth)
    _validate_ground_truth(ground_truth)
    if args.image_id:
        if args.image_id not in ground_truth:
            parser.error(f"unknown --image-id: {args.image_id}")
        ground_truth = {args.image_id: ground_truth[args.image_id]}

    modes_to_run = MODES if args.mode == "all" else (args.mode,)
    if args.mode != "compare":
        for mode in modes_to_run:
            _run_mode(
                mode,
                args.image_dir,
                args.ground_truth,
                args.results_dir,
                args.image_id,
            )
            _build_predictions(mode, ground_truth, args.results_dir)

    if args.mode in {"all", "compare"}:
        _compare(ground_truth, args.results_dir)


if __name__ == "__main__":
    main()
