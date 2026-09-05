# Error Audit

This audit uses only the saved files under `evaluation/results/` and the current production code. No inference or OpenAI request was rerun. A detection is treated as added or removed only when that change is directly observable by comparing the saved YOLO-only and YOLO+GPT `all_detections`. The current VLM metadata contains aggregate counts and `error`, but no per-candidate decision reason; reasons are therefore not inferred.

## Shoes

### Improved

| Image | GT | YOLO-only | YOLO+GPT | Causal detection-level change | Classification |
|---|---:|---:|---:|---|---|
| `htp_test_01` | true | false | true | Added `shoes`, confidence `0.5`, bbox `[87,403,139,419]`, `use_for_analysis=true`, `source=openai_vlm`; passes person spatial check | VLM missing-detail addition (Trigger B) |
| `htp_test_02` | true | false | true | Added `shoes`, confidence `0.5`, bbox `[721,1475,907,1518]`, `use_for_analysis=true`, `source=openai_vlm`; passes person spatial check | VLM missing-detail addition (Trigger B) |
| `htp_test_03` | false | true | false | Removed `sneakers`, confidence `0.4252`, bbox `[602,294,779,484]`, `use_for_analysis=true`; this detection passed the existing person spatial check before removal | VLM verification (Trigger A) |
| `htp_test_04` | true | false | true | Added `shoes`, confidence `0.5`, bbox `[468,1114,611,1150]`, `use_for_analysis=true`, `source=openai_vlm`; passes person spatial check | VLM missing-detail addition (Trigger B) |
| `htp_test_05` | true | false | true | Added `shoes`, confidence `0.5`, bbox `[469,1036,580,1061]`, `use_for_analysis=true`, `source=openai_vlm`; passes person spatial check | VLM missing-detail addition (Trigger B) |
| `htp_test_11` | true | false | true | Added `shoes`, confidence `0.5`, bbox `[80,1016,202,1042]`, `use_for_analysis=true`, `source=openai_vlm`; passes person spatial check | VLM missing-detail addition (Trigger B) |
| `htp_test_12` | true | false | true | Added `shoes`, confidence `0.5`, bbox `[455,1111,605,1147]`, `use_for_analysis=true`, `source=openai_vlm`; passes person spatial check | VLM missing-detail addition (Trigger B) |
| `htp_test_13` | true | false | true | Added `shoes`, confidence `0.5`, bbox `[480,1002,586,1026]`, `use_for_analysis=true`, `source=openai_vlm`; passes person spatial check | VLM missing-detail addition (Trigger B) |

The seven true-positive recoveries were missing-detail additions. The `htp_test_03` improvement was instead removal of a false `sneakers` detection through low-confidence verification.

### Degraded

| Image | GT | YOLO-only | YOLO+GPT | Removed detection(s) | Selected person bbox | Trigger |
|---|---:|---:|---:|---|---|---|
| `htp_test_06` | true | true | false | `sneakers`, confidence `0.5367`, bbox `[266,302,449,403]`, `use_for_analysis=true` | `[340,852,515,1189]` | Trigger A |
| `htp_test_09` | true | true | false | `female_shoes`, confidence `0.3103`, bbox `[589,916,628,940]`, `use_for_analysis=true` | `[447,712,599,995]` | Trigger A |
| `htp_test_10` | true | true | false | `sneakers`, confidence `0.3564`, bbox `[362,344,510,442]`, and overlapping `male_shoes`, confidence `0.2602`, bbox `[363,356,510,443]`; both `use_for_analysis=true` | `[439,759,622,1130]` | Trigger A |

All causal detections were present before VLM, absent afterward, within the configured `0.25 <= confidence < 0.60` verification range, and accepted by the current spatial check before removal. No replacement `shoes` detection was added in these three images. The saved metadata confirms aggregate removals (`1`, `1`, and `2`) and has `error=null`, but it does not store candidate-level `present`, decision reason, or textual rationale.

### Common pattern

The shared failure mechanism is VLM verification of an existing low-confidence shoe alias followed by removal—not Trigger B, label normalization, or post-processing count aggregation. The labels vary (`sneakers`, `female_shoes`, and `male_shoes`), confidence spans `0.2602`–`0.5367`, and the bboxes differ, so the saved evidence does not support a narrower label- or confidence-specific rule. The unusual separation between some shoe and selected-person bboxes still passes the current permissive spatial policy; that policy is an upstream eligibility condition, but the immediate accuracy regression occurs when the VLM returns the candidate as absent.

## Root

### Improved

| Image | GT | Removed root detection(s) | Nearby tree-bottom evidence in YOLO-only | Classification |
|---|---:|---|---|---|
| `htp_test_05` | false | `root 0.3153 [787,905,918,941]`; `root 0.2904 [782,899,999,943]` | `trunk 0.7631 [795,765,911,928]`; several `grass` boxes around y=898–943 | VLM verification |
| `htp_test_07` | false | `root 0.5424 [803,843,952,881]` | `trunk 0.6578 [816,692,936,872]`; `grass` boxes `[766,843,809,882]`, `[952,839,1015,882]` | VLM verification |
| `htp_test_08` | false | `root 0.4546 [833,901,1065,951]`; `root 0.3988 [834,908,957,949]` | `trunk 0.6459 [852,771,947,919]`, `trunk 0.4582 [843,778,955,946]`; several `grass` boxes around y=902–952 | VLM verification |
| `htp_test_13` | false | `root 0.3668 [796,839,1044,883]`; `root 0.3522 [814,838,973,880]` | `trunk 0.8324 [822,658,935,850]`; several `grass` boxes around y=840–884 | VLM verification |

All removed roots passed the current tree spatial check and lay at the trunk/ground region. The repeated coexistence of trunk endings and grass in the same lower-tree band is consistent with detector ambiguity among root, trunk base, and ground decoration. The VLM successfully rejected these low-confidence root detections. Metadata contains no per-detection reason, so the exact visual cue used by the model is unknown.

### Remaining false positives

| Image | GT | Root retained after VLM | Trigger-A status | Nearby evidence |
|---|---:|---|---|---|
| `htp_test_04` | false | `root 0.3928 [183,937,257,979]`; `root 0.3414 [182,933,317,980]` | Eligible; retained | `trunk 0.6709 [189,796,250,951]` and multiple grass boxes at the tree base |
| `htp_test_06` | false | `root 0.4598 [687,826,826,867]` | Eligible; retained | `trunk 0.7309 [692,672,818,858]`, `branch 0.3371`, and nearby grass |
| `htp_test_10` | false | `root 0.6916 [808,890,1047,950]` | Not eligible: confidence is above `0.60` | `trunk 0.6971 [830,763,947,905]` and nearby grass |
| `htp_test_11` | false | `root 0.4818 [849,946,963,989]` | Eligible; retained | `trunk 0.7238 [854,831,962,978]` and nearby grass |

### Common pattern

The VLM improved root accuracy by removing seven low-confidence detections across four images, reducing false positives from eight to four. Three remaining false-positive images (`04`, `06`, `11`) contained eligible candidates that the VLM retained; these are VLM verification errors based on the final state, although no stored reason is available. `htp_test_10` is different: its root confidence is `0.6916`, so it never enters Trigger A and remains a detector false positive outside VLM scope. Tree-base overlap with trunk/grass is visible in both successful and unsuccessful cases, so it is a detector ambiguity signal rather than a sufficient predictor of VLM outcome.

## Branch

### New false positives

| Image | GT | YOLO-only | YOLO+GPT | Added detection | Surrounding YOLO state |
|---|---:|---:|---:|---|---|
| `htp_test_08` | false | false | true | `branch`, confidence `0.5`, bbox `[808,411,992,533]`, `use_for_analysis=true`, `source=openai_vlm`; passes tree spatial check | selected tree `[750,404,1052,951]`; crown `[752,405,1048,822]`; trunks `[852,771,947,919]`, `[843,778,955,946]`; no branch before VLM |
| `htp_test_13` | false | false | true | `branch`, confidence `0.5`, bbox `[816,630,930,704]`, `use_for_analysis=true`, `source=openai_vlm`; passes tree spatial check | selected tree `[699,379,1069,885]`; crown `[700,380,1069,703]`; trunk `[822,658,935,850]`; no branch before VLM |

These are not verified existing detections. They are new `source=openai_vlm` detections created because `branch` was missing, so the operative path is Trigger B. The synthetic confidence `0.5` is only a compatibility value. Both returned bboxes pass the unchanged spatial policy and consequently set `tree.parts.branch.detected=true`.

### Likely failure mechanism

Evidence-based classification: **VLM missing-detail addition**. The immediate error originates when Trigger B labels crown/trunk-region line work as a missing branch and supplies a bbox. Spatial validation then accepts both boxes, but does not originate the false detection. The saved metadata has only aggregate counts and no explanation, so whether the model specifically confused crown outlines, trunk outlines, or internal lines cannot be determined. This is most directly a missing-detail prompt/visual-verification failure, with spatial validation acting as a permissive downstream gate.

## Fruit / Flower Counts

### Detector errors

- `htp_test_02 fruit_count`: GT is `5`; YOLO-only contains four fruit detections, all spatially valid. The initial `5 -> 4` shortfall is therefore a detector miss (one GT instance has no retained raw fruit detection), not representative-object aggregation.
- `htp_test_01 flower_count`: all three GT flowers are present as raw flower detections. This is not a detector miss.
- `htp_test_09 flower_count`: both GT flowers are present as raw flower detections. This is not a detector miss.

### VLM-induced errors

`htp_test_02` changes from fruit count `4` to `3` because VLM verification removes:

- `fruit`, confidence `0.3346`, bbox `[1193,608,1249,663]`, `use_for_analysis=true`.

That detection passed the selected-tree spatial check before removal. The other retained fruit detections are `0.7152 [1232,387,1274,436]`, `0.5825 [1080,503,1121,563]`, and `0.5211 [1080,622,1114,687]`. Metadata says one total detection was removed with `error=null`, but contains no fruit/leaf confusion reason. Classification: one detector miss plus one VLM verification false negative. It is not a post-processing association error: the two main tree boxes are near-duplicate boxes for the same tree, and all four YOLO-only fruit boxes pass against the representative tree.

### Post-processing errors

#### `htp_test_01 flower_count`

- Raw flowers: 3; final count: 2.
- Main-object detections: 3 (`tree 0.9420 [389,146,515,334]`, `tree 0.8103 [62,274,159,421]`, `tree 0.9063 [390,146,516,342]`).
- Representative tree selected by `_pick_best_bbox()`: `[389,146,515,334]`.
- `flower 0.9160 [30,286,59,332]`: spatial check **fails** against the representative tree.
- `flower 0.9159 [451,337,479,374]`: passes.
- `flower 0.8172 [397,297,425,337]`: passes.

Classification: representative-object aggregation. The excluded flower is associated with a different detected tree region and is ignored because counting uses one representative tree.

#### `htp_test_09 flower_count`

- Raw flowers: 2; final count: 1.
- Main-object detections: 4 (`tree 0.9760 [35,403,399,938]`, `tree 0.7987 [445,709,599,914]`, `tree 0.9680 [36,403,398,938]`, `tree 0.6454 [731,499,1054,935]`).
- Representative tree: `[35,403,399,938]`.
- `flower 0.9086 [82,849,134,938]`: passes.
- `flower 0.8860 [646,866,693,938]`: fails against the representative tree.

Classification: representative-object aggregation. This repeats the `htp_test_01` multi-main-object association pattern: the detector found both flowers, but one lies outside the single selected tree bbox and is not aggregated through another tree detection.

#### `htp_test_02 fruit_count`

- Raw fruit count is already 4 versus GT 5.
- Both main tree detections (`0.9637 [961,327,1478,1019]`, `0.9653 [953,329,1477,1015]`) describe effectively the same tree region.
- Representative tree is `[953,329,1477,1015]` and all four raw fruits pass its spatial check.

Classification: not representative-object aggregation. The errors are detector miss followed by VLM verification removal.

## Root Cause Classification

| Error group | Classification | Evidence |
|---|---|---|
| Shoes improvements in `01/02/04/05/11/12/13` | VLM missing-detail addition | New `source=openai_vlm` shoes boxes cause false→true |
| Shoes improvement in `03` | VLM verification | Existing low-confidence false `sneakers` removed |
| Shoes degradation in `06/09/10` | VLM verification | Spatially accepted, GT-positive shoe aliases removed; no replacement added |
| Root improvements in `05/07/08/13` | VLM verification | Low-confidence root boxes removed |
| Remaining root FP in `04/06/11` | VLM verification | Eligible root boxes retained |
| Remaining root FP in `10` | detector | Confidence `0.6916` is outside Trigger A; VLM does not act on it |
| New branch FP in `08/13` | VLM missing-detail addition | No prior branch; VLM adds synthetic `branch 0.5` boxes |
| `02` fruit initial undercount | detector | Only four raw fruit boxes for GT five |
| `02` fruit additional degradation | VLM verification | Spatially valid `fruit 0.3346` removed |
| `01` flower undercount | representative-object aggregation | Three raw flowers, one fails only against single selected tree |
| `09` flower undercount | representative-object aggregation | Two raw flowers across multiple tree regions, one excluded by selected tree |

No reviewed error is best classified as a pure spatial-validation bug from saved evidence. Spatial checks explain which detections influence final features, but the causal errors here are detector output, VLM action, or selection of only one representative main object. Where VLM rationale is absent from metadata, the finer visual reason remains **uncertain**.

## Recommended Fix Priority

1. Audit and constrain Trigger B `branch` addition first. It creates two new false positives and is the direct cause of branch accuracy falling from `0.384615` to `0.230769`. Validate the distinction between an explicit branch and crown/trunk outlines using a broader held-out set before changing production behavior.
2. Audit Trigger A shoe false-negative decisions. The same action removes correct shoe detections in three images. Preserve the current aliases while testing whether candidate crops/context or decision criteria—not a label-specific exception—improve verification.
3. Address multi-main-object aggregation for count features. `htp_test_01` and `htp_test_09` independently show raw flowers excluded because only one representative tree is used. Any future design should associate parts with all valid main objects and deduplicate, rather than introduce image-specific exceptions.
4. Review root verification calibration. VLM removal halves root false positives, so preserve that benefit while investigating the eligible retained false positives in `04/06/11`. Treat `htp_test_10` separately because its high-confidence detector FP is outside VLM scope.
5. Investigate count recovery only after the association issue is isolated. `htp_test_02` combines a detector miss and a VLM-induced removal; it should not be treated as the same failure as the flower aggregation cases.

These are investigation priorities only. No production rule, threshold, prompt, spatial policy, normalization, or evaluation metric is changed by this audit.
