"""Auditable production evaluation; never overwrite an existing run directory.

Each image invokes the production analyzer once. Persist raw detector input, VLM
decisions, HTTP request count, and normalized image x attribute baseline changes.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--image-ids", nargs="+")
    parser.add_argument("--image-dir", type=Path, default=REPO.parent / "test_image")
    parser.add_argument("--baseline", type=Path, default=REPO / "evaluation/results_final_dev_candidate")
    args = parser.parse_args()
    args.results_dir.mkdir(parents=True, exist_ok=False)
    os.environ["OPENAI_VLM_FALLBACK_ENABLED"] = "true"
    from evaluation.evaluate import ATTRIBUTES, normalize_analysis
    from app.services import htp_vlm_fallback_service as vlm, yolo_service as yolo

    gt = json.loads((REPO / "evaluation/ground_truth.json").read_text(encoding="utf-8"))
    image_ids = args.image_ids or list(gt)
    save(args.results_dir / "manifest.json", {
        "image_ids": image_ids,
        "source_sha256": {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest()
                          for name in ("app/services/htp_vlm_fallback_service.py", "app/services/yolo_service.py")},
        "baseline": str(args.baseline),
    })
    raw_dir = args.results_dir / "yolo_gpt"
    raw_dir.mkdir()
    source_dir = args.results_dir / "sources"
    source_dir.mkdir()
    records, predictions = [], {}
    actual_send = vlm.client._client.send
    actual_apply = vlm.apply_vlm_fallback
    actual_merge = vlm._apply_response
    for image_id in image_ids:
        matches = [p for p in args.image_dir.glob(image_id + ".*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        if len(matches) != 1:
            raise ValueError(f"Expected one image: {image_id}")
        # Unique stem preserves old production visualization artifacts too.
        source = source_dir / (args.results_dir.name + "_" + matches[0].name)
        shutil.copy2(matches[0], source)
        audit = {"image": image_id, "responses_http_calls": 0}

        def send(request, **kwargs):
            if request.url.path.endswith("/responses"):
                audit["responses_http_calls"] += 1
            return actual_send(request, **kwargs)

        def capture_apply(*a, **kw):
            audit["raw_detections"] = a[1] if len(a) > 1 else kw["all_detections"]
            return actual_apply(*a, **kw)

        def capture_merge(*a, **kw):
            audit["verification_candidates"] = a[1]
            audit["vlm_payload"] = a[7]
            return actual_merge(*a, **kw)

        with patch.object(vlm.client._client, "send", send), patch.object(yolo, "apply_vlm_fallback", capture_apply), patch.object(vlm, "_apply_response", capture_merge):
            result = yolo.analyze_htp_image_with_yolo(str(source))
        save(raw_dir / (image_id + ".json"), result)
        save(raw_dir / (image_id + ".audit.json"), audit)
        metadata = result["yolo_result_json"].get("vlm_fallback", {})
        predictions[image_id] = normalize_analysis(result)
        print(json.dumps({"image": image_id, "calls": audit["responses_http_calls"], "metadata": metadata,
                          "prediction": predictions[image_id]}, ensure_ascii=False), flush=True)
        if result["yolo_result_json"].get("fallback") or metadata.get("error"):
            raise RuntimeError(f"Production fallback/error for {image_id}; evidence saved")
        if audit["responses_http_calls"] > 1:
            raise RuntimeError("More than one Responses HTTP call per image")
        baseline_path = args.baseline / "yolo_gpt" / (image_id + ".json")
        if image_id not in gt or not baseline_path.exists():
            continue
        baseline = normalize_analysis(json.loads(baseline_path.read_text(encoding="utf-8")))
        for category, attribute, _, _ in ATTRIBUTES:
            truth = gt[image_id][category][attribute]
            before, after = baseline[category][attribute], predictions[image_id][category][attribute]
            status = "unchanged" if before == after else ("unscored" if truth is None else
                     "improved" if after == truth else "degraded" if before == truth else "changed_wrong")
            records.append(dict(image=image_id, category=category, attribute=attribute,
                                ground_truth=truth, baseline=before, final=after, status=status))
    save(args.results_dir / "predictions_yolo_gpt.json", predictions)
    summary = {"baseline_correct": sum(r["baseline"] == r["ground_truth"] for r in records if r["ground_truth"] is not None),
               "final_correct": sum(r["final"] == r["ground_truth"] for r in records if r["ground_truth"] is not None),
               "total": sum(r["ground_truth"] is not None for r in records),
               **{status: [r for r in records if r["status"] == status] for status in ("improved", "degraded", "changed_wrong")}}
    save(args.results_dir / "comparison.json", {"summary": summary, "records": records})
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
