# HTP YOLO / VLM evaluation

This evaluation compares the production HTP pipeline in two isolated modes:

- `yolo_only`: `OPENAI_VLM_FALLBACK_ENABLED=false`
- `yolo_gpt`: `OPENAI_VLM_FALLBACK_ENABLED=true`

Each mode runs in a separate subprocess, so values loaded by `app.core.config` and
cached YOLO models cannot leak between modes. The worker calls the production
`analyze_htp_image_with_yolo()` function directly. Prediction normalization reads only
the returned `visual_features_json`; it does not duplicate detection, alias, or spatial
validation logic.

## Prerequisites

Run commands from the `backend_latest` repository root. Ensure:

- `.venv` contains the project dependencies;
- `.env` contains required application configuration;
- `evaluation\ground_truth.json` is filled in;
- images are present in `..\test_image` as `htp_test_01` through `htp_test_13`
  using `.jpg`, `.jpeg`, or `.png` extensions.

`yolo_gpt` makes real OpenAI API calls when the production fallback is triggered.

## Run both modes and build the report

Windows CMD:

```bat
.venv\Scripts\python.exe evaluation\evaluate.py --mode all
```

## Run modes separately

```bat
.venv\Scripts\python.exe evaluation\evaluate.py --mode yolo_only
.venv\Scripts\python.exe evaluation\evaluate.py --mode yolo_gpt
.venv\Scripts\python.exe evaluation\evaluate.py --mode compare
```

The `compare` command expects both prediction files and all raw mode results to exist.

Optional explicit paths:

```bat
.venv\Scripts\python.exe evaluation\evaluate.py --mode all --image-dir "C:\Users\minji\OneDrive\바탕 화면\SAI\sai_backend\test_image" --ground-truth evaluation\ground_truth.json --results-dir evaluation\results
```

## Outputs

```text
evaluation\results\yolo_only\htp_test_01.json
evaluation\results\yolo_gpt\htp_test_01.json
evaluation\results\predictions_yolo_only.json
evaluation\results\predictions_yolo_gpt.json
evaluation\results\comparison.csv
evaluation\results\summary.json
```

Ground-truth attributes whose value is `null` remain in `comparison.csv` with blank
correctness columns and are excluded from every metric denominator.

The production analyzer also writes its normal annotated images under
`uploads\htp\result`. Because both modes use the same source stems, the later mode may
overwrite those visualization images. Raw JSON evaluation results remain separated by
mode.
