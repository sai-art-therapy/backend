# Branch Error Audit

This audit uses only saved results from `evaluation/results/`, `evaluation/results_after_shoes_fix/`, the ground truth, and the current production source. No inference or OpenAI request was run. Coordinates are original-image pixels. VLM decision reasons are not stored and are not inferred.

## Branch Error Map

### Ground-truth positive

| Image | GT | Raw branch detections | YOLO-only final | GPT final | VLM action | GPT correct |
|---|---:|---|---:|---:|---|---:|
| `htp_test_05` | true | `0.8404 [771,570,1009,772]` | true | true | retained; confidence above Trigger A | yes |
| `htp_test_12` | true | `0.7270 [759,618,925,710]` | true | true | retained; confidence above Trigger A | yes |

### Ground-truth negative

| Image | GT | Raw branch detections | Analysis | YOLO-only | GPT | VLM action | GPT correct |
|---|---:|---|---|---:|---:|---|---:|
| `htp_test_01` | false | `0.6536 [420,225,482,264]` | true | true | true | retained; above Trigger A | no |
| `htp_test_02` | false | none | — | false | false | no branch added | yes |
| `htp_test_03` | false | `0.4493 [1186,374,1345,475]`; `0.3372 [1186,391,1303,474]` | both true | true | true | both Trigger A candidates verified/retained | no |
| `htp_test_04` | false | `0.6825 [193,710,277,805]` | true | true | true | retained; above Trigger A | no |
| `htp_test_06` | false | `0.3371 [705,637,816,693]` | true | true | true | Trigger A candidate verified/retained | no |
| `htp_test_07` | false | `0.7784 [814,632,928,699]`; `0.3405 [162,601,292,736]` | true; true | true | true | first retained above Trigger A; second is spatially irrelevant | no |
| `htp_test_08` | false | none | — | false | true | Trigger B added `branch 0.5 [767,410,1047,819]` | no |
| `htp_test_09` | false | `0.7399 [172,689,258,779]` | true | true | true | retained; above Trigger A | no |
| `htp_test_10` | false | `0.7989 [830,689,956,770]` | true | true | true | retained; above Trigger A | no |
| `htp_test_11` | false | `0.8578 [852,766,969,835]`; `0.4482 [73,865,123,938]`; `0.2610 [107,857,164,923]` | all true | true | true | first retained above Trigger A; latter two spatially irrelevant | no |
| `htp_test_13` | false | none | — | false | true | Trigger B added `branch 0.5 [827,661,935,777]` | no |

All listed raw detections have `use_for_analysis=true`; the final value additionally depends on the representative-tree spatial check. Raw count means every raw `branch` detection, including detections that fail that association check.

## YOLO False Positives

YOLO-only has eight negative images with final `branch=true`: `01`, `03`, `04`, `06`, `07`, `09`, `10`, and `11`.

The production branch policy is exactly:

```text
branch -> ["adjacent_any", "overlap"]
```

The fallback chain uses OR semantics. `adjacent_any` expands the selected tree bbox by 20% on every side and tests overlap; `overlap` tests direct bbox intersection. Every branch that actually causes the eight false positives passes **both** policies, not merely the more permissive `adjacent_any` fallback.

| Image | Branch conf/bbox causing final true | Selected tree | Crown | Trunk | Root(s) | True policy paths |
|---|---|---|---|---|---|---|
| `01` | `0.6536 [420,225,482,264]` | `[389,146,515,334]` | `[390,146,515,266]` | `[422,262,462,303]` | none | adjacent_any + overlap |
| `03` | `0.4493 [1186,374,1345,475]`; `0.3372 [1186,391,1303,474]` | `[890,23,1626,1204]` | `[892,12,1625,504]` | `[1124,476,1335,1197]` | none | both paths for both boxes |
| `04` | `0.6825 [193,710,277,805]` | `[63,396,405,980]` | `[63,397,405,801]` | `[189,796,250,951]` | `0.3928 [183,937,257,979]`; `0.3414 [182,933,317,980]` | adjacent_any + overlap |
| `06` | `0.3371 [705,637,816,693]` | `[582,348,968,869]` | `[582,349,967,687]` | `[692,672,818,858]` | `0.4598 [687,826,826,867]` | adjacent_any + overlap |
| `07` | `0.7784 [814,632,928,699]` | `[679,342,1064,884]` | `[680,344,1064,695]` | `[816,692,936,872]` | `0.5424 [803,843,952,881]` | adjacent_any + overlap |
| `09` | `0.7399 [172,689,258,779]` | `[35,403,399,938]` | `[36,403,398,764]` | `[184,757,246,935]` | none | adjacent_any + overlap |
| `10` | `0.7989 [830,689,956,770]` | `[677,379,1068,948]` | `[680,381,1068,760]` | `[830,763,947,905]` | `0.6916 [808,890,1047,950]` | adjacent_any + overlap |
| `11` | `0.8578 [852,766,969,835]` | `[736,526,1065,990]` | `[737,527,1065,837]` | `[854,831,962,978]` | `0.4818 [849,946,963,989]` | adjacent_any + overlap |

The outlying raw branches in `07` and `11` fail both policy paths and do not affect the final feature. This shows that the existing policy does reject branches associated with a different region, but cannot determine whether a tree-internal detection is semantically a real branch.

## True vs False Branch Signals

| Type/image | Confidence | Branch area / tree area | Relative center `(x,y)` | Crown coverage of branch | Trunk coverage of branch |
|---|---:|---:|---|---:|---:|
| true `05` | 0.8404 | 0.2324 | `(0.575,0.486)` | 1.0000 | 0.0169 |
| true `12` | 0.7270 | 0.0479 | `(0.521,0.525)` | 0.9239 | 0.1147 |
| false `01` | 0.6536 | 0.1021 | `(0.492,0.524)` | 1.0000 | 0.0331 |
| false `03-a` | 0.4493 | 0.0185 | `(0.510,0.340)` | 1.0000 | 0.0000 |
| false `03-b` | 0.3372 | 0.0112 | `(0.482,0.347)` | 1.0000 | 0.0000 |
| false `04` | 0.6825 | 0.0400 | `(0.503,0.619)` | 0.9579 | 0.0643 |
| false `06` | 0.3371 | 0.0309 | `(0.462,0.608)` | 0.8929 | 0.3750 |
| false `07` | 0.7784 | 0.0366 | `(0.499,0.597)` | 0.9403 | 0.1026 |
| false `09` | 0.7399 | 0.0397 | `(0.495,0.619)` | 0.8333 | 0.1762 |
| false `10` | 0.7989 | 0.0459 | `(0.552,0.616)` | 0.8765 | 0.0802 |
| false `11` | 0.8578 | 0.0529 | `(0.530,0.592)` | 1.0000 | 0.0535 |

Findings:

- **Confidence is not separating.** True confidence is `0.7270`–`0.8404`; false detections extend from `0.3371` to `0.8578` and overlap the entire true range.
- **Size is not separating.** True `12` has area ratio `0.0479`, inside the false cluster `0.0309`–`0.0529`. True `05` is unusually large, but this does not form a rule for both positives.
- **Crown overlap is not separating.** Both classes are predominantly inside the crown; false values span `0.8333`–`1.0`, while true values are `0.9239` and `1.0`.
- **Trunk overlap is not separating.** True values `0.0169` and `0.1147` lie within the false range `0.0`–`0.3750`.
- **Relative y is the only suggestive bbox-level signal, but weakly supported.** Both positives center at y ratios `0.486` and `0.525`. Six FP boxes center lower at `0.592`–`0.619`, but false `01` is `0.524` and false `03` is higher at `0.340`–`0.347`. A vertical-band gate could reject six of eight FP images while retaining the two observed positives, but two positives are insufficient to establish generalization.
- **Connectivity is not represented.** Bboxes do not encode whether lines truly split from the trunk. A branch-specific support signal would need visual/line connectivity information rather than only overlap rectangles.

Conclusion: no sufficiently reliable single confidence, size, crown-overlap, or trunk-overlap threshold is demonstrated by these 13 images. Relative position is a candidate signal, not yet a safe rule.

## VLM-Induced False Positives

### `htp_test_08`

- YOLO raw branch count: `0`.
- Branch is absent from the spatially relevant labels, so `_missing_labels()` requests canonical `branch` because a tree parent exists.
- VLM returns `branch 0.5 [767,410,1047,819]`, `source=openai_vlm`.
- The addition passes both `adjacent_any` and direct `overlap` against tree `[750,404,1052,951]`.
- Its bbox covers most of the crown region `[752,405,1048,822]`, which is evidence of a crown-level localization rather than a tight branch localization.
- Prior repeatability: branch addition `no/no/yes`; this is a **stochastic VLM Trigger B failure**. The current full run produced `yes` again.

### `htp_test_13`

- YOLO raw branch count: `0`.
- The same parent-present/detail-missing rule requests `branch`.
- VLM returns `branch 0.5 [827,661,935,777]`, `source=openai_vlm`.
- It passes both `adjacent_any` and direct `overlap` against tree `[699,379,1069,885]`.
- The bbox overlaps the trunk/crown boundary region: crown ends near y=`703`, trunk spans `[822,658,935,850]`.
- Prior repeatability: branch added `yes/yes/yes`; this is a **deterministic-like VLM Trigger B failure**.

The code-level reason for both requests is only that a selected tree exists and no spatially relevant branch label exists. The VLM response does not store a textual decision reason.

## Root Cause Classification

Classification is assigned to the ten GPT false-positive images/actions without double-counting:

| Classification | Count | Images | Basis |
|---|---:|---|---|
| detector false positive | 6 | `01`, `04`, `07`, `09`, `10`, `11` | YOLO branch directly overlaps the selected tree/crown and is above the Trigger A range |
| combination: detector FP + VLM verification retention | 2 | `03`, `06` | low-confidence YOLO FP entered Trigger A but VLM returned present |
| VLM Trigger B false addition | 2 | `08`, `13` | no raw branch; VLM added a new branch bbox |
| spatial policy too permissive, primary | 0 | — | every causal raw box directly overlaps the tree; `adjacent_any` alone does not create these outcomes |
| representative-tree association | 0 | — | causal branches are associated with the selected tree, not excluded alternative trees |
| uncertain | 0 | — | action provenance is observable, although the visual semantic confusion reason is not stored |

Spatial policy is a contributing limitation for all ten outcomes because it tests association only and has no branch semantics/connectivity gate. It is not counted as the primary cause of the eight YOLO FPs because direct overlap—not only expansion—passes, and the two true branches have overlapping geometry.

## Fix Candidates

### A. Strengthen the existing branch spatial policy with a relative-position band

- **Target:** Six lower-position YOLO FP images (`04`, `06`, `07`, `09`, `10`, `11`).
- **True-positive preservation evidence:** the two observed true branches center at relative y `0.486` and `0.525`, above the six-FP cluster `0.592`–`0.619`.
- **Expected effect:** potentially 6/8 YOLO FP removals; no effect on Trigger B additions unless applied to them too.
- **Regression risk:** high relative to sample size. False `01` shares the true y band, false `03` lies above it, and legitimate low branches may be rejected in unseen drawings.
- **Generalizability:** uncertain; only two true examples.
- **Change scope:** `SPATIAL_POLICY` or a branch-specific spatial gate in `yolo_service.py`.

### B. Disable or more strictly gate Trigger B branch additions

- **Target:** VLM-induced FP in `08` and `13`.
- **True-positive preservation evidence:** both GT-positive images already have high-confidence YOLO branch detections; YOLO branch recall is `2/2` in this dataset.
- **Expected effect:** 2/2 observed VLM-added FPs prevented, returning GPT branch accuracy from `3/13` toward the YOLO-only `5/13` without changing the existing raw detections.
- **Regression risk:** future YOLO branch false negatives would no longer be recoverable if branch addition is disabled entirely. A stricter tight-bbox/connectivity requirement has lower recall risk but needs validation.
- **Generalizability:** high for preventing unsupported synthetic branch additions; evidence is limited for recall outside this set.
- **Change scope:** branch-only Trigger B eligibility or response-application gate in `htp_vlm_fallback_service.py`.

### C. Add a branch-specific visual/geometric support gate

- **Target:** YOLO FP and Trigger B additions that represent crown outlines, trunk regions, or undifferentiated internal lines.
- **True-positive preservation evidence:** an actual branch should contain lines that visibly diverge from or connect to the trunk, a property not represented by current bbox overlap metrics.
- **Expected effect:** potentially broader than A/B, but the number cannot be supported from stored bbox data alone.
- **Regression risk:** moderate to high; line extraction is sensitive to drawing style and occlusion, and a VLM connectivity judgment may remain stochastic.
- **Generalizability:** conceptually strongest semantic signal, empirically unvalidated here.
- **Change scope:** new branch-specific post-verification support logic or richer VLM verification context; larger than A or B.

## Recommended First Change

Prioritize **B: restrict Trigger B from adding a new branch unless a much stronger branch-specific condition is met**. It directly addresses two errors introduced by VLM, preserves both observed true positives because they already come from YOLO, and has a smaller blast radius than changing the shared spatial behavior. A complete disable is the simplest experiment; a conservative branch-only application gate is safer for future recall. No change is implemented in this audit.
