# HTP hardening 인계 후 검증 기록 — 2026-09-06

브랜치: `fix/htp-tree-main-validation`. 기존 working tree와 frozen baseline을 보존했다.
reset/revert/checkout, commit/push/merge/deploy, 모델 가중치·global confidence threshold·`.env` 수정은 하지 않았다.

## 1. Root causes

- 기존 main 보호 정책으로 tree로 오탐한 사람/페이지 영역이 display와 관계 계산에 남았다.
- canonical detail당 bbox 하나로 처리하던 응답 병합은 복구한 팔·다리와 열매의 실제 개수를 표현하지 못했다.
- 앞선 hardening에서 conditional tree replacement가 일반 main recovery와 섞여 불필요한 root 복구가 요청되었다.
- 거절된 secondary tree를 모든 용도에서 삭제하면서 flower multi-tree 집계가 줄었다.
- root의 보수적 시각 기준이 Trigger B에만 있어 Trigger A의 low-confidence YOLO root FP가 살아남았다.
- 인계 당시 root 재검증은 이미 4/4 저장되어 있었다. 다만 `htp_test_04`는 여전히 false positive였다.
  넓어진 줄기 밑동과 내부 수피 선을 별도 뿌리와 구별하는 기준을 보강했다.
- PDI의 단순 부분문자열 비교는 창문/문, 신발/발을 혼동했다. 질문 유형이 default_pdi여도 실제로 부재를 전제하는 경우가 있었다.
- Report의 detected 값은 문 개폐를 나타내지 않는다. RAG의 일반 상징은 개별 그림의 사실이 아니다.
  기존 검사기는 관계 섹션 밖의 모순을 놓치고, 올바른 '개폐 여부를 알 수 없다' 문장은 잘못 차단했다.

## 2. 변경 파일

인계된 구현을 유지·보완한 production 파일:

- `app/services/htp_vlm_fallback_service.py`: main 검증/복구, cardinality, root 기준, HTTP 재시도 금지.
- `app/services/yolo_service.py`: 대표/display/관계 tree와 flower 집계 parent 역할 분리. 인계받은 변경 유지.
- `app/services/pdi_service.py`: boolean/count 기반 부재 검증, 한국어 조사/영문 단어 경계, 미측정 잎 질문 차단.
- `app/services/htp_report_service.py`: prompt grounding, 전 섹션 관계 모순 검사, 문 상태 unknown 구별.

검증 파일:

- `tests/test_htp_vlm_main_recovery.py`, `tests/test_htp_vlm_fallback_service.py`, `tests/test_htp_grounding.py`
- `evaluation/hardening_verify.py`: 덮어쓰지 않는 production 평가, raw detections/VLM payload/HTTP count 및 baseline 비교.
- `evaluation/grounding_verify.py`: 실제 PDI/RAG/report 생성; DB persistence만 메모리 대역 사용.
- `evaluation/inspect_app_cases.py`: 지정 실패/최근 검사 탐지 자료의 read-only 조회.

## 3. 최종 일반 규칙

- 기존 한 번의 이미지 VLM 응답에 tree main 검증, 필요한 main 복구, detail 복구를 함께 요청한다.
- root는 별도로 뻗은 명확한 뿌리 선만 인정한다. 지면선, 넓어진 밑동, 줄기 실루엣 내부 수피 선은 제외한다.
- countable detail은 label당 여러 bbox를 허용하고 기존/추가 instance와의 중복 및 parent 공간 일관성을 확인한다.
- tree replacement 요청과 recovered-tree detail 요청은 분리한다.
- rejected tree는 대표/display/관계에서 제외하되 flower 공간 집계의 힌트로만 보존한다.
- flower multi-tree 및 fruit representative-tree 집계, branch Trigger B 금지, shoes spatial guard를 유지한다.
- 오류 시 원본 YOLO 결과를 반환한다. `max_retries=0`으로 SDK의 숨은 HTTP 재시도도 막는다.
- PDI는 존재하는 부위나 미측정 부위를 missing이라고 전제하지 않도록 검사한다. count>0는 존재다.
- Report는 입력에 없는 개폐/관계를 사실로 쓰지 않고, PDI 없는 심리 단정을 제한한다.

## 4. Unit tests

`.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests`

최종 36 tests 통과. HTTP 500에서 실제 mock transport 요청 1회와 exact-original fail-open을 검증했다.
pytest는 이 가상환경에 설치되어 있지 않아 프로젝트의 unittest 테스트를 직접 실행했다.

## 5. DEV 13장 — frozen baseline과 image × attribute 비교

- Baseline: `results_final_dev_candidate/yolo_gpt`, **128/142**.
- Final: `results_hardening_final/yolo_gpt`, **131/142**.
- 개선 3개, degraded 0개, changed_wrong 0개.
- 전 image × attribute 행: [comparison.json](results_hardening_final/comparison.json).
- 실행 소스 SHA256: [manifest.json](results_hardening_final/manifest.json).

| Image | Attribute | GT | Baseline | Final |
|---|---|---:|---:|---:|
| htp_test_02 | tree.fruit_count | 5 | 4 | 5 |
| htp_test_03 | house.window_count | 2 | 1 | 2 |
| htp_test_05 | tree.root | false | true | false |

degraded: `[]`. changed_wrong: `[]`.

root 4개(04/06/07/13)는 `results_root_repeat_02`와 final DEV에서 각 2회 모두 false로 정답이었다.
별도 root 4장 결과는 41/44로 해당 baseline과 동일하다. 두 번의 일치는 확률적 안정성의 제한된 증거이며 보장은 아니다.
13장 모두 tree.detected=true다. 이 142개 지표에는 main bbox 정답이 포함되지 않는다.
01 flower=3, 09 flower=2로 multi-tree 집계가 유지되었고 팔·다리·신발 항목의 추가 회귀는 없었다.

남은 오답 11개는 모두 기존 오답이다:

- branch 8개: 01/03/04/06/07/09/10/11.
- root 2개: 10/11.
- leg_count 1개: 03, GT=2 / baseline=final=4.

## 6. test_253 before/after

[최종 분석](results_failure_final/yolo_gpt/test_253_source.json), [raw/응답 감사 기록](results_failure_final/yolo_gpt/test_253_source.audit.json).

- Raw tree 4개: 실제 tree 0.9609, 사람/부분/페이지 FP 0.708 / 0.303 / 0.443.
- Final: 실제 tree 유지. FP 3개는 display·대표·관계에서 제외. flower aggregation-only 행은 보존.
- Raw에는 house/person main이 없었다. 최종 둘 다 `openai_vlm`으로 복구.
- 이전 세션 인계의 복구 cardinality 1개 문제에 대해 최종 arms=2, legs=2 확인.
- orphan shoe 제거, shoes=false, fruit=0. VLM HTTP 1회, error=null.
- 관찰된 별도 한계: 실제 이미지 수관은 보이지만 final crown.detected=false다. 이번 요구의 main/팔/다리/신발/열매 성공과 별개인 detail FN이다.

## 7. htp_test_02 before/after

[최종 분석](results_hardening_final/yolo_gpt/htp_test_02.json), [raw/응답 감사 기록](results_hardening_final/yolo_gpt/htp_test_02.audit.json).

- GT=5, frozen baseline=4, final=5.
- YOLO의 잘못된 low-confidence fruit 1개가 제거되고 별도 과일 bbox 2개가 추가되어 5개가 되었다.
- 5개 최종 bbox는 서로 다른 instance다. 대표 tree 선택 및 flower 집계 정책을 유지했다.

## 8. API call count

- 최종 DEV 13장: Responses HTTP **13회**, 각 이미지 1회.
- 별도 root 4장: **4회**, 각 이미지 1회.
- test_253 최종: **1회**.
- 성공한 이미지 검증 총 **18회/18 image runs**. 각 `.audit.json`의 `responses_http_calls`로 확인 가능하다.
- PDI/report는 기존 Chat Completions, RAG는 Embeddings 경로이며 이미지 VLM의 추가 호출이 아니다.
- 샌드박스 API 연결 실패 결과도 별도 폴더에 보존했으며 정확도/성공 검증에 섞지 않았다.

## 9. PDI production 결과

실제 `create_pdi_questions()`와 실제 GPT/RAG를 실행했다. 사용자 검사 DB에 쓰지 않도록 Session persistence만 메모리 대역으로 바꿨다. 질문 ID null은 이 때문이다.

- test_253: [질문](results_grounding_253_final_v2/pdi_questions.json).
  '집에 문을 그리지 않으신 이유가 있을까요?', '사람을 그리실 때 손과 발은 왜 그리지 않으셨나요?'는 각각 door=false, hands=0, feet=0과 일치한다.
  roof/wall/chimney 및 arms/legs는 존재하므로 missing 질문이 없었다.
- htp_test_02: [최종 질문](results_grounding_02_rag_final_v4/pdi_questions.json).
  문·창문·지붕 및 손·발·팔·다리가 존재한다. 해당 부위를 missing이라고 묻지 않았다.
- 중간 실제 생성에서 '잎사귀나 가지를 그리지 않음'이 나왔다. leaves 미측정과 branch 부재를 혼합하지 못하도록 회귀 테스트와 필터를 보완했다.
- default_pdi로 잘못 분류된 부재 질문도 같은 존재 검증을 받는다.

## 10. Report production 결과

- 로컬 앱 `htp_knowledge` 컬렉션은 0건이었다. 빈 RAG의 production 경로도 실제 실행했다.
- 별도 평가용 Chroma에 저장소 HTP 자료 74개를 실제 임베딩했다. 기존 앱 인덱스는 보존했다.
- 실 검색은 19개 chunk를 반환했다. PDI/생활 맥락 없이 이 자료의 일반 상징을 아이의 사실로 쓰지 않도록 prompt를 보강했다.
- 문 상태 unknown 문장의 잘못된 차단도 수정했다. 미지원 개폐 단정 및 touching=false 모순은 계속 차단한다.
- [최종 실제 RAG report](results_grounding_02_rag_final_v4/report.json): 생성 및 grounding 검사 통과.
  요약은 '집, 나무, 사람 그림이 모두 포함되어 있으나 PDI 응답은 없어 해석에 제한이 있습니다.'이며
  main_emotion은 '확인 어려움'이다. positive_note는 실제 표현된 부위만 기술한다.
  문 개폐는 정보가 없다고 설명하며, 서로 겹치거나 맞닿지 않는다고 관찰한다.
  앞선 잘못된 '모든 요소가 중간 크기' 요약도 최종 응답에는 없다.
- [test_253 실제 report](results_grounding_253_final_v2/report.json): 빈 RAG 경로에서 실제 생성 통과.
  존재하는 지붕·굴뚝·벽과 팔·다리를 관찰하고, 문/창문 및 손/발 부재는 final JSON과 일치한다.
- 최종 detector 소스 SHA256은 DEV 실행 manifest와 일치한다. 이후 변경은 PDI/report와 검증 코드에 한정되었다.

## 11. 추가 앱 main-object FP 분석

앱 DB read-only 연결이 sandbox 및 승인된 실행에서 모두 OperationalError로 실패했다.
따라서 사용자가 말한 최신 앱 검사와 동일한 사례인지는 미확인이다.
다만 로컬 `htp_test_02`의 **실제 모델별 추론**에서 반대 방향 FP를 확인했다:

| Model | Raw label | Canonical | Confidence | Bbox |
|---|---|---|---:|---|
| person | female_person | person | 0.538 | [966,328,1476,1014] |
| tree | tree | tree | 0.9653 | [953,329,1477,1015] |
| person | female_person | person | 0.9289 | [714,980,910,1521] |

첫 행은 실제 나무 영역이고 마지막 행이 실제 사람이다.
[모델별 증거](results_local_model_audit/htp_test_02.json).
이 person FP는 final display에도 남지만 높은 confidence의 실제 사람이 대표라 현재 대표 person feature는 유지된다.

최소 변경 설계 검토: house/tree/person의 서로 다른 canonical main이 같은 영역을 주장하면 기존 한 번의 VLM 응답에 **양쪽 후보를 함께** 넣어 검증한다. 겹침만으로 삭제하거나 항상 tree/person 중 한쪽을 우선하지 않는다. 명시적 거절만 display/대표에서 제외하고 오류/불확실성은 보존한다. flower parent 정책은 별도로 유지한다. 이번 작업에서는 이 후속 정책을 적용하지 않았다.

## 12. 남은 구조적 한계

- 142개 지표가 tree/person main FP 및 bbox 품질을 직접 점수화하지 않아 총점만으로 main 안전성을 판단할 수 없다.
- person/tree cross-model FP, 기존 branch/root 오답, 기존 YOLO leg 중복 및 test_253 crown FN이 남아 있다.
- rejected tree를 flower 집계 힌트로 남기는 정책은 꽃의 정확한 parent identity 검증을 대신하지 않는다.
- countable 추가 bbox의 overlap 기반 중복 판정은 가림/겹친 실제 instance를 완벽하게 구분하지 못한다.
- PDI 텍스트/한국어 조사 및 report 모순 검사는 제한된 규칙이다. 모든 동의어·복합문장·심리적 표현에 대한 의미 검증기는 아니다.
- RAG가 존재해도 자료 자체의 일반 상징을 개별 아이에 적용하려는 생성 경향이 있다. prompt 보강과 좁은 사후 검사는 모든 환각 제거를 보장하지 않는다.
- report grounding 위반은 ValueError로 거절한다. 추가 LLM 복구 호출은 하지 않는다.
- 실제 앱 DB/라우터 저장 E2E는 DB 접속 불가로 미검증이다. production service 진입점과 실제 API 생성까지만 검증했다.
