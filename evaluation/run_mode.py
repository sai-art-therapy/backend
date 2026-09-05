"""Run the production HTP analyzer in one isolated evaluation mode."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _resolve_image(image_dir: Path, image_id: str) -> Path:
    matches = [
        image_dir / f"{image_id}{suffix}"
        for suffix in (".jpg", ".jpeg", ".png")
        if (image_dir / f"{image_id}{suffix}").is_file()
    ]
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected exactly one image for {image_id}, found {len(matches)}"
        )
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("yolo_only", "yolo_gpt"), required=True)
    parser.add_argument("--image-dir", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--image-id")
    args = parser.parse_args()

    expected_vlm_enabled = args.mode == "yolo_gpt"
    configured_value = os.environ.get("OPENAI_VLM_FALLBACK_ENABLED", "").lower()
    if configured_value != str(expected_vlm_enabled).lower():
        raise RuntimeError("Evaluation mode was not set before production imports")

    # Import only after the parent process has fixed the mode environment.
    from app.core.config import OPENAI_VLM_FALLBACK_ENABLED
    from app.services.yolo_service import analyze_htp_image_with_yolo

    if OPENAI_VLM_FALLBACK_ENABLED is not expected_vlm_enabled:
        raise RuntimeError("Imported VLM mode does not match the requested evaluation mode")

    ground_truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))
    if args.image_id:
        if args.image_id not in ground_truth:
            raise KeyError(f"Unknown ground-truth image id: {args.image_id}")
        ground_truth = {args.image_id: ground_truth[args.image_id]}
    mode_dir = args.results_dir / args.mode

    for image_id in ground_truth:
        image_path = _resolve_image(args.image_dir, image_id)
        analysis = analyze_htp_image_with_yolo(str(image_path))
        output_path = mode_dir / f"{image_id}.json"
        _write_json(output_path, analysis)
        print(f"[{args.mode}] {image_id}: saved")

        yolo_result = analysis.get("yolo_result_json", {})
        if yolo_result.get("fallback"):
            raise RuntimeError(
                f"Production YOLO mock fallback occurred for {image_id}; "
                f"see {output_path}"
            )


if __name__ == "__main__":
    main()
