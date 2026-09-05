## Known issue: multi-main-object spatial aggregation

### htp_test_01 / flower_count

- Ground truth: 3
- YOLO raw detections: 3
- All 3 flower detections were present in yolo_result_json.
- Final visual_features flower_count: 2

Observed cause:

- `_create_visual_features_from_yolo()` selects one representative tree bbox using `_pick_best_bbox(detections, "tree")`.
- `_count_parts_spatial()` then counts flower detections relative to that single representative tree bbox.
- htp_test_01 has two tree detections.
- One flower appears spatially associated with the non-representative tree and is excluded from the final count.

Classification:

- NOT detector miss
- NOT OpenAI VLM failure
- Likely post-processing / multi-main-object association issue

Important:

- Do NOT modify app/services/yolo_service.py
- Do NOT modify app/services/htp_vlm_fallback_service.py
- Do NOT change thresholds, spatial policy, prompts, or evaluation metrics
- Do NOT attempt to fix this issue yet
- Do NOT run the full 13-image evaluation yet
