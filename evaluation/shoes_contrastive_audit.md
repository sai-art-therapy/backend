# Shoes Contrastive Audit

This audit is based only on saved results and the current source code. No inference or OpenAI request was run. Coordinates are original-image pixels. `IoU(P)` is shoe/person IoU; `overlap%` is the percentage of shoe area intersecting the selected person; `rel-y` is `(shoe_center_y - person_y1) / person_height`; distances are minimum edge-to-edge pixel distances. VLM reasons are not stored and are not inferred.

## Scope and outcome

| Image | GT shoes | YOLO-only | YOLO+GPT | Saved action | Repeatability |
|---|---:|---:|---:|---|---|
| `htp_test_03` | false | true | false | removed `sneakers 0.4252` | removed 3/3 |
| `htp_test_06` | true | true | false | removed `sneakers 0.5367` | removed 3/3 |
| `htp_test_09` | true | true | false | removed `female_shoes 0.3103` | removed 3/3 |
| `htp_test_10` | true | true | false | removed `sneakers 0.3564` and `male_shoes 0.2602` | both removed 3/3 |

## Raw shoe detections

All rows below come from YOLO-only `all_detections`; all have `use_for_analysis=true`. `A` means the detection is in the actual Trigger A set under the current selected-parent/spatial filtering and `0.25 <= confidence < 0.60` condition.

### `htp_test_03`

Selected person: `male_person 0.8210 [618,1132,848,1614]`.

| Label | Confidence | Bbox | Center | A | IoU(P) | overlap% | center in P | rel-y | area/P | foot overlap / distance | leg overlap / distance |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|
| sneakers | 0.4252 | `[602,294,779,484]` | `(690.5,389.0)` | yes | 0 | 0% | no | -1.541 | 0.3034 | no / 1080.0 | no / 930.0 |

### `htp_test_06`

Selected person: `female_person 0.9489 [340,852,515,1189]`. Another main-person detection exists at `[582,349,968,866]` with confidence `0.8699`, but production selects only the higher-confidence box.

| Label | Conf. | Bbox | Center | A | Spatial pass | rel-y | area/P | nearest foot | nearest leg |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| sneakers | 0.7570 | `[215,765,269,820]` | `(242,792.5)` | no | no | -0.177 | 0.0504 | 347.1 | 238.5 |
| female_shoes | 0.6565 | `[930,844,958,876]` | `(944,860)` | no | no | 0.024 | 0.0152 | 519.6 | 466.6 |
| female_shoes | 0.6393 | `[542,780,584,825]` | `(563,802.5)` | no | no | -0.147 | 0.0320 | 332.9 | 215.1 |
| sneakers | 0.5367 | `[266,302,449,403]` | `(357.5,352.5)` | **yes** | **yes** | -1.482 | 0.3134 | 751.0 | 631.0 |
| sneakers | 0.4784 | `[557,829,584,863]` | `(570.5,846)` | no | no | -0.018 | 0.0156 | 298.4 | 183.3 |
| female_shoes | 0.4726 | `[833,826,882,872]` | `(857.5,849)` | no | no | -0.009 | 0.0382 | 443.3 | 378.4 |
| female_shoes | 0.4707 | `[909,841,934,882]` | `(921.5,861.5)` | no | no | 0.028 | 0.0174 | 498.7 | 444.8 |
| sneakers | 0.4079 | `[907,842,934,883]` | `(920.5,862.5)` | no | no | 0.031 | 0.0188 | 496.5 | 442.6 |
| sneakers | 0.3500 | `[92,767,150,824]` | `(121,795.5)` | no | no | -0.168 | 0.0561 | 392.0 | 302.0 |
| female_shoes | 0.3200 | `[251,585,282,614]` | `(266.5,599.5)` | no | no | -0.749 | 0.0152 | 546.6 | 433.3 |
| female_shoes | 0.2591 | `[543,803,564,825]` | `(553.5,814)` | no | no | -0.113 | 0.0078 | 333.1 | 215.4 |
| sneakers | 0.2535 | `[257,530,295,580]` | `(276,555)` | no | no | -0.881 | 0.0322 | 578.7 | 464.7 |

Every shoe/person IoU and shoe-area overlap is zero, and every shoe center is outside the selected person. The causal Trigger A candidate is the large far-above `sneakers 0.5367` box.

### `htp_test_09`

Selected person: `female_person 0.9474 [447,712,599,995]`. Another main-person detection exists at `[36,405,399,933]`, confidence `0.8776`.

| Label | Conf. | Bbox | Center | A | Spatial pass | IoU(P) | overlap% | rel-y | area/P | nearest foot | nearest leg |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| sneakers | 0.8452 | `[794,798,860,865]` | `(827,831.5)` | no | no | 0 | 0% | 0.422 | 0.1028 | 240.3 | 222.2 |
| female_shoes | 0.7976 | `[81,849,132,897]` | `(106.5,873)` | no | no | 0 | 0% | 0.569 | 0.0569 | 345.0 | 338.2 |
| female_shoes | 0.6025 | `[664,909,690,936]` | `(677,922.5)` | no | no | 0 | 0% | 0.744 | 0.0163 | 93.0 | 88.0 |
| female_shoes | 0.5631 | `[646,910,668,934]` | `(657,922)` | no | no | 0 | 0% | 0.742 | 0.0123 | 77.0 | 70.0 |
| female_shoes | 0.4727 | `[651,867,693,906]` | `(672,886.5)` | no | no | 0 | 0% | 0.617 | 0.0381 | 96.0 | 75.0 |
| female_shoes | 0.3240 | `[612,915,638,938]` | `(625,926.5)` | no | no | 0 | 0% | 0.758 | 0.0139 | 45.6 | 36.0 |
| female_shoes | 0.3103 | `[589,916,628,940]` | `(608.5,928)` | **yes** | **yes** | 0.0055 | 25.64% | 0.763 | 0.0218 | 29.1 | 13.0 |
| female_shoes | 0.2744 | `[357,919,384,936]` | `(370.5,927.5)` | no | no | 0 | 0% | 0.761 | 0.0107 | 91.1 | 86.0 |
| female_shoes | 0.2731 | `[274,892,324,934]` | `(299,913)` | no | no | 0 | 0% | 0.710 | 0.0488 | 149.5 | 146.0 |

The causal candidate center is just outside the person, but 25.64% of its area overlaps the person. It is near the lower person region and only 13 px from a leg and 29.1 px from a foot. This is the only causal true-shoe candidate with meaningful local anatomical support.

### `htp_test_10`

Selected person: `male_person 0.9101 [439,759,622,1130]`. Two low-confidence person boxes at approximately `[681,380,1068,952]` are not selected.

| Label | Conf. | Bbox | Center | A | Spatial pass | rel-y | area/P | nearest foot | nearest leg |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| sneakers | 0.6931 | `[331,348,417,428]` | `(374,388)` | no | no | -1.000 | 0.1013 | 667.3 | 613.4 |
| sneakers | 0.3564 | `[362,344,510,442]` | `(436,393)` | **yes** | **yes** | -0.987 | 0.2136 | 652.0 | 598.0 |
| male_shoes | 0.2602 | `[363,356,510,443]` | `(436.5,399.5)` | **yes** | **yes** | -0.969 | 0.1884 | 651.0 | 597.0 |
| sneakers | 0.2574 | `[330,343,481,433]` | `(405.5,388)` | no | no | -1.000 | 0.2002 | 661.0 | 607.0 |

All shoe/person IoUs and overlap fractions are zero; all centers are outside the person. The two causal candidates are large, overlapping aliases far above the selected person's feet and legs.

## Person, leg, and foot support

| Image | Selected person bbox | Foot detections | Leg detections |
|---|---|---|---|
| `03` | `[618,1132,848,1614]` | `0.8323 [740,1564,800,1613]`; `0.8129 [655,1568,725,1610]` | `0.5145 [655,1524,726,1610]`; `0.5127 [734,1414,810,1614]`; `0.3386 [738,1524,802,1613]`; `0.2732 [655,1414,739,1610]` |
| `06` | `[340,852,515,1189]` | `0.8914 [440,1154,491,1187]`; `0.8633 [360,1155,413,1189]` | `0.8063 [361,1040,429,1189]`; `0.7194 [428,1034,491,1189]` |
| `09` | `[447,712,599,995]` | `0.7987 [470,966,518,993]`; `0.7497 [531,966,576,991]` | `0.8836 [530,908,576,991]`; `0.8821 [470,909,522,993]` |
| `10` | `[439,759,622,1130]` | `0.8968 [552,1093,609,1125]`; `0.8923 [458,1094,518,1129]` | `0.9028 [458,1040,519,1129]`; `0.8989 [550,1039,609,1125]` |

All four images have strong foot and leg detections for the selected person. However, the causal shoe boxes in `03`, `06`, and `10` have no overlap with those supports and are hundreds of pixels away. Therefore, mere existence of foot/leg detections does not separate the false case from all three GT-positive cases.

## Actual Trigger A input

For candidate verification, the service sends the complete original image as a base64 data URL; it does not crop the candidate. The text payload supplies, for every candidate:

- `candidate_id`
- raw `label`
- YOLO `confidence`
- original-pixel `bbox`

It also supplies image width/height, all other low-confidence candidates, and the list of Trigger B missing labels. It does **not** explicitly supply the selected person bbox, foot bboxes, leg bboxes, person association, spatial-policy result, or nearest-support measurements.

The Trigger A instruction is: verify whether “that exact labeled element is visibly present near the supplied bbox.” The conservative shoes wording—requiring a shoe outline distinct from foot or leg—explicitly applies only to requested missing labels, not to low-confidence candidate verification.

Actual causal inputs/actions:

| Image | Candidate label/confidence/bbox | Saved action |
|---|---|---|
| `03` | `sneakers 0.4252 [602,294,779,484]` | removed |
| `06` | `sneakers 0.5367 [266,302,449,403]` | removed |
| `09` | `female_shoes 0.3103 [589,916,628,940]` | removed |
| `10` | `sneakers 0.3564 [362,344,510,442]`; `male_shoes 0.2602 [363,356,510,443]` | both removed |

The metadata records only aggregate verified/added/removed counts and `error`; it stores no candidate-level reason.

## Contrastive answers

### A. Is there a common YOLO/spatial distinction?

No single observed YOLO/spatial signal separates `03` from all of `06/09/10` while preserving their causal detections.

- `09` differs usefully: its causal box is near the person bottom, 13 px from a leg, 29.1 px from a foot, and partially overlaps the person.
- `06` and `10` do not: their causal boxes resemble `03` more than `09`. They are far above the selected person, have no person/foot/leg overlap, and are hundreds of pixels from foot/leg boxes.
- The current spatial helper nevertheless admits `03`, `06`, and `10`. `_is_adjacent_below()` checks only an upper bound on `part.y1 - person.y2`; any large negative gap satisfies it when x-overlap is sufficient. Thus a box far above the person can be classified as `adjacent_below`.

### B. Can confidence distinguish them?

No. The correctly removed false candidate has confidence `0.4252`; incorrect removals span both below and above it (`0.2602`, `0.3103`, `0.3564`, `0.5367`). No threshold within the current values separates the groups.

### C. Can aliases distinguish them?

No. `sneakers` occurs in the correct removal (`03`) and incorrect removals (`06`, `10`). `female_shoes` identifies `09`, but is not common to the other failures. `male_shoes` occurs only as an overlapping second candidate in `10`. Alias alone is not generalizable.

### D. Would foot/leg support preserve true positives while removing `03`?

It can plausibly separate `09` from `03`, but not preserve the current causal boxes in `06` and `10`: those boxes have no local foot/leg support and look spatially like the `03` false positive. A rule based solely on support for the *candidate bbox* would reject `03`, `06`, and `10` together.

Foot/leg support becomes more useful as context for a second question: after rejecting a suspicious shoe candidate, does the selected person have a separate, clearly visible shoe at its actual foot region? The current single request does not ask that question when any shoe alias existed before verification.

### E. Closest failure category

The primary failure is **deletion policy/orchestration**, with **spatial support** as an upstream contributor:

1. Trigger B missing labels are calculated before Trigger A decisions.
2. A spatially admitted shoe candidate means `shoes` is not requested as missing.
3. If VLM rejects that candidate, it is deleted.
4. The same response cannot provide a replacement shoe bbox because `shoes` was not in the missing-label request.

For `06` and `10`, the VLM may be correctly rejecting the exact supplied far-away boxes even though image-level GT shoes is true elsewhere. The final false negative therefore does not prove that the VLM misread those candidate boxes. `09`, whose candidate has local support, is closer to a genuine VLM verification false negative. The full image is already provided, so “insufficient pixels/crop context” is not supported; the missing explicit person/foot association and request structure are more relevant.

## Fix candidates

### Priority 1 — Conditional same-call recovery for rejected canonical details

- **Idea:** When the only existing canonical shoe evidence consists of Trigger A candidates, also request a replacement/missing `shoes` decision in the same VLM call. Apply the returned missing bbox only if all relevant shoe candidates are rejected and the replacement passes existing validation/spatial policy.
- **Why `03` can remain removed:** rejection still removes its far-away false candidate; no replacement is added unless a separate clear shoe outline exists.
- **Why `06/09/10` may be preserved:** even if the supplied candidate bbox is wrong or rejected, VLM can identify an actual shoe near the selected person's feet instead of leaving the attribute false solely because pre-verification presence suppressed Trigger B.
- **Side effects:** more missing-label decisions and possible duplicate/replacement boxes; requires careful deduplication and atomic response application.
- **Overfitting risk:** low to moderate. It applies to any canonical detail represented only by uncertain candidates, not image IDs, but should initially be constrained to semantics where replacement is safe.
- **Production scope:** VLM candidate/missing request construction and response application; no YOLO threshold change required.

### Priority 2 — Supply explicit parent and anatomical support context to Trigger A

- **Idea:** Include selected person bbox plus nearby foot/leg bboxes and association status in the existing candidate payload, while retaining the full image.
- **Why `03` can remain removed:** its candidate is 1080 px from the nearest foot and 930 px from the nearest leg, clearly contradicting the provided association.
- **Why `06/09/10` may be preserved:** `09` has strong local support. For `06/10`, explicit context would show that the supplied candidate is unrelated but may help VLM locate the selected person's real foot region when combined with conditional recovery; by itself it cannot preserve those exact candidate boxes.
- **Side effects:** larger prompt and reliance on upstream foot/leg detections; incorrect selected-person association can mislead the VLM.
- **Overfitting risk:** moderate, especially in multi-person drawings.
- **Production scope:** VLM prompt payload construction only, preferably paired with Priority 1.

### Priority 3 — Correct the general `adjacent_below` directional constraint

- **Idea:** Require a lower-bound relationship as well as the existing maximum gap so that a supposed below-part cannot be arbitrarily far above its parent.
- **Why `03` can remain removed:** its rel-y is `-1.541` and it is far above the person.
- **Why `06/09/10` may be preserved:** it directly preserves only `09`, whose candidate is near the lower person region. It would also prevent misleading far-away candidates in `06/10` from creating a pre-verification shoes presence, allowing a recovery path to check the actual foot region if Priority 1 is implemented.
- **Side effects:** could exclude legitimate boxes inside the lower person bbox unless the accepted band is defined carefully; affects every label using `adjacent_below`, including roots.
- **Overfitting risk:** moderate because this changes shared spatial behavior.
- **Production scope:** spatial helper/policy behavior; broader regression testing required.

## Recommended first change

Implement **conditional same-call recovery for a canonical detail whose only evidence is rejected Trigger A candidates**. It addresses the actual false-negative transition without assuming that the rejected far-away boxes in `06/10` are true shoes, preserves one-call behavior, and does not depend on confidence or alias patterns that the contrastive data disproves. No change is implemented in this audit.
