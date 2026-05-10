# 🎨 그담(GDAM) Backend API

HTP 그림 기반 AI 심리 분석 및 육아 방향 안내 서비스 **그담(GDAM)**의 백엔드 API 명세 및 RAG 기능 구현 문서입니다.

본 프로젝트는 **FastAPI + Swagger(OpenAPI)** 기반으로 API를 설계하였으며,  
현재는 프론트엔드 개발을 위한 Mock API를 기반으로 하되, 일부 기능은 실제 AI/RAG 연동까지 진행되었습니다.

---

# 📌 프로젝트 개요

* 서비스명: **그담 (GDAM)**
* 목적: 아이의 그림(HTP 검사)을 기반으로 심리 상태를 분석하고, 부모에게 맞춤형 육아 방향을 제공
* 현재 상태:

  * ✅ API 명세 설계 완료
  * ✅ 육아 상담 RAG 챗봇 1차 구현 완료
  * ✅ OpenAI Embedding + ChromaDB 기반 검색 테스트 완료
  * ✅ GPT API 기반 근거 답변 생성 테스트 완료
  * ❌ PostgreSQL DB 연동 전
  * ❌ YOLOv8 그림 분석 모델 API 연동 전
  * ❌ HTP 리포트 생성 RAG 정식 연동 전

---

# ⚙️ 기술 스택

* **Backend Framework**: FastAPI
* **API Documentation**: Swagger (OpenAPI)
* **Language**: Python 3.13
* **Environment**: venv
* **LLM API**: OpenAI API
* **Embedding Model**: OpenAI text-embedding 계열
* **Vector DB**: ChromaDB
* **Data Format**: JSON

---

# 📂 프로젝트 구조

```text
backend/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── core/                # 환경변수 및 프롬프트 설정
│   │   ├── config.py
│   │   └── prompts.py
│   ├── data/                # RAG용 JSON 데이터
│   │   └── rag/
│   │       ├── htp_report_generation/
│   │       │   ├── htp_knowledge.json
│   │       │   └── sources.json
│   │       └── parenting_chatbot/
│   │           ├── parenting_guides.json
│   │           └── sources.json
│   ├── db/                  # 로컬 DB 및 ChromaDB 저장 위치
│   │   └── chroma/
│   ├── routers/             # API 라우터
│   │   ├── auth.py
│   │   ├── home.py
│   │   ├── children.py
│   │   ├── tests.py
│   │   ├── reports.py
│   │   ├── chat.py
│   │   ├── mypage.py
│   │   └── rag_admin.py
│   ├── schemas/             # 요청/응답 데이터 모델
│   │   ├── auth.py
│   │   ├── home.py
│   │   ├── children.py
│   │   ├── tests.py
│   │   ├── reports.py
│   │   ├── chat.py
│   │   └── mypage.py
│   └── services/            # 비즈니스 로직 및 외부 API 연동
│       ├── chroma_service.py
│       ├── ingest_service.py
│       ├── openai_service.py
│       ├── rag_service.py
│       ├── report_service.py
│       └── source_service.py
├── scripts/
│   └── ingest_parenting_guides.py
├── requirements.txt
├── .env.example
└── README.md
```

---

# 🚀 실행 방법

## 1. 가상환경 생성 및 활성화

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2. 패키지 설치

```bash
pip install -r requirements.txt
```

`requirements.txt`에는 다음 패키지가 포함됩니다.

```text
fastapi
uvicorn
python-dotenv
openai
chromadb
pydantic
python-multipart
```

## 3. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성합니다.

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_CHAT_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PATH=./app/db/chroma
CHROMA_COLLECTION=parenting_guides
```

`.env` 파일은 API Key가 포함되므로 GitHub에 업로드하지 않습니다.  
팀원 공유용으로는 `.env.example` 파일만 업로드합니다.

## 4. 서버 실행

```bash
uvicorn app.main:app --reload
```

---

# 📄 API 문서 (Swagger)

서버 실행 후 아래 주소로 접속합니다.

```text
http://127.0.0.1:8000/docs
```

Swagger UI에서 전체 API 명세 및 테스트를 진행할 수 있습니다.

---

# 📌 API 구성 (탭 기준)

## 🏠 Home

* `GET /home/summary`

홈 화면 요약 정보를 제공합니다.

* 마지막 검사 경과
* 변화 요약
* 최근 리포트 요약
* 챗봇 요약

---

## 💬 Chat

* `POST /api/chat/sessions`
* `GET /api/chat/sessions`
* `GET /api/chat/sessions/{session_id}`
* `POST /api/chat/sessions/{session_id}/messages`

리포트 기반 상담 및 RAG 기반 육아 상담 답변을 제공합니다.

현재 `POST /api/chat/sessions/{session_id}/messages`는 사용자의 질문을 받아 RAG 기반 답변을 생성하도록 연결되어 있습니다.

### 요청 예시

```json
{
  "message": "아이가 스마트폰을 너무 오래 봐서 끄라고 하면 화를 내요. 어떻게 해야 하나요?",
  "report_id": null
}
```

### 응답 예시

```json
{
  "session_id": 1,
  "answer": "RAG 검색 결과를 바탕으로 GPT가 생성한 육아 상담 답변",
  "sources": [
    {
      "guide_id": "pg_009",
      "category": "건강한 생활",
      "subcategory": "스마트폰·미디어 사용 조절",
      "display_sources": "CDC, Positive Parenting Tips for Healthy Child Development - Preschoolers ages 3-5 | CDC, Positive Parenting Tips for Healthy Child Development - Middle Childhood ages 9-11",
      "source_urls": "https://stacks.cdc.gov/view/cdc/155270 | https://stacks.cdc.gov/view/cdc/155269",
      "licenses": "Public Domain | Public Domain",
      "usage_decisions": "사용 가능 | 사용 가능"
    }
  ],
  "safety_notice": "본 답변은 전문 심리 진단이나 치료를 대체하지 않으며, 아이의 상태가 지속적으로 걱정되거나 위험 신호가 보이면 전문가 상담을 권장합니다."
}
```

---

## 🧠 Tests (검사)

* `POST /tests`
* `POST /tests/{test_id}/image`
* `GET /tests/{test_id}/questions`
* `POST /tests/{test_id}/answers`
* `POST /tests/{test_id}/analyze`
* `GET /tests/{test_id}`

HTP 검사 진행 및 AI 분석 요청 API입니다.

현재는 Mock 데이터 기반으로 API 명세를 제공합니다.

---

## 📊 Reports

* `GET /reports`
* `GET /reports/{report_id}`

검사 결과 리포트 조회 API입니다.

현재는 Mock 데이터 기반으로 동작합니다.  
향후 HTP 분석 결과 및 RAG 기반 리포트 생성 결과와 연동할 예정입니다.

---

## 👶 Children

* `GET /children`
* `POST /children`
* `PATCH /children/{child_id}`
* `DELETE /children/{child_id}`

자녀 정보 관리 API입니다.

---

## 👤 Mypage

* `GET /mypage`
* `PATCH /mypage/account`
* `PATCH /mypage/notifications`

계정 및 알림 설정 관리 API입니다.

---

## 🔐 Auth

* `POST /auth/signup`
* `POST /auth/login`
* `POST /auth/logout`

사용자 인증 API입니다.

현재는 Mock 데이터 기반이며, 향후 JWT 인증 방식으로 확장할 예정입니다.

---

## 🧩 RAG Admin

* `POST /api/admin/rag/ingest`
* `GET /api/admin/rag/search-test`

육아 상담 RAG 데이터셋을 ChromaDB에 저장하고, 검색 결과를 테스트하기 위한 관리자용 API입니다.

### RAG 데이터 저장

```text
POST /api/admin/rag/ingest
```

또는 터미널에서 다음 명령어를 실행할 수 있습니다.

```bash
python scripts/ingest_parenting_guides.py
```

성공 시 예시 출력:

```text
{'count': 10, 'message': '10개 parenting guide를 ChromaDB에 저장했습니다.'}
```

### RAG 검색 테스트

```text
GET /api/admin/rag/search-test
```

예시 query:

```text
아이가 스마트폰을 너무 오래 봐요
```

예상 검색 결과:

```text
pg_009
건강한 생활 > 스마트폰·미디어 사용 조절
```

---

# 🧠 육아 상담 RAG 챗봇

## 1. 구현 목적

부모가 HTP 그림 검사 결과 리포트를 확인한 이후, 챗봇을 통해 육아 관련 질문을 할 수 있도록 RAG 기반 육아 상담 챗봇을 구현했습니다.

단순히 GPT API에 사용자 질문을 바로 전달하는 방식이 아니라, 직접 구축한 육아 가이드 JSON 데이터셋을 기반으로 관련 문서를 검색한 뒤, 검색된 근거를 GPT prompt에 포함하여 답변을 생성합니다.

이를 통해 답변이 일반적인 생성형 AI 응답에 그치지 않고, 출처가 관리된 육아 가이드 자료를 기반으로 생성되도록 설계했습니다.

---

## 2. RAG 데이터 구조

RAG에 사용되는 데이터는 다음 경로에 위치합니다.

```text
app/data/rag/parenting_chatbot/
├── parenting_guides.json
└── sources.json
```

### parenting_guides.json

육아 상담에 활용되는 가이드 데이터입니다.

각 guide는 다음 정보를 포함합니다.

```text
id
source_ids
category
subcategory
child_state
parent_concern
situation
parent_goal
recommended_response
avoid_response
parent_script_example
practical_action
observation_points
warning_signs
referral_guide
keywords
age_range
evidence_level
confidence_level
```

### sources.json

각 guide가 어떤 자료를 기반으로 작성되었는지 관리하는 출처 파일입니다.

각 source는 다음 정보를 포함합니다.

```text
source_id
organization
title
source_url
file_type
license
source_verification
usage_decision
usable_topics
notes
```

---

## 3. RAG 동작 흐름

```text
사용자 질문
→ FastAPI 백엔드 수신
→ 사용자 질문 embedding 생성
→ ChromaDB에서 관련 parenting guide 검색
→ 검색된 guide와 source 정보를 GPT prompt에 삽입
→ GPT API가 근거 기반 답변 생성
→ 답변 + 출처 + 안전 안내문 반환
```

---

## 4. ChromaDB 저장 방식

`parenting_guides.json`의 각 guide 객체를 하나의 document로 변환하여 ChromaDB에 저장합니다.

| 구분 | 저장 내용 |
| --- | --- |
| document | 아이 상태, 부모 고민, 상황, 권장 반응, 피해야 할 반응, 부모 대화 예시, 실천 방법, 관찰 포인트, 경고 신호, 전문기관 안내 |
| metadata | guide_id, category, subcategory, source_ids, display_sources, source_urls, licenses, age_range, evidence_level, confidence_level |

---

## 5. 안전 규칙

챗봇 답변 생성 시 다음 규칙을 적용합니다.

```text
1. 검색된 육아 가이드에 근거해서만 답변
2. 검색 결과에 없는 내용은 지어내지 않음
3. 아이의 심리 상태나 정신질환을 단정적으로 진단하지 않음
4. HTP 리포트가 제공되더라도 참고 정보로만 사용
5. 부모를 비난하지 않고 실천 가능한 대화 예시와 행동 가이드 제공
6. 위험 신호가 포함된 경우 전문기관 상담 안내
7. 의료, 심리치료, 전문 진단을 대체하지 않는다는 안내 포함
8. 답변 마지막에 참고 guide_id와 출처 표시
```

응답에는 항상 다음 안전 안내문을 포함합니다.

```text
본 답변은 전문 심리 진단이나 치료를 대체하지 않으며, 아이의 상태가 지속적으로 걱정되거나 위험 신호가 보이면 전문가 상담을 권장합니다.
```

---

# ⚠️ 현재 상태

본 API는 현재 다음과 같은 상태입니다.

* ✅ FastAPI + Swagger 기반 API 명세 구현
* ✅ Mock API 기반 프론트엔드 개발용 엔드포인트 제공
* ✅ 육아 상담 RAG 챗봇 백엔드 1차 구현
* ✅ parenting_guides.json / sources.json 기반 데이터셋 구축
* ✅ ChromaDB 벡터 DB 저장 기능 구현
* ✅ OpenAI embedding 기반 검색 기능 구현
* ✅ GPT API 기반 답변 생성 기능 구현
* ❌ PostgreSQL DB 미연동
* ❌ YOLOv8 그림 분석 모델 미연동
* ❌ 실제 사용자 인증/JWT 미적용
* ❌ HTP 리포트 생성 RAG 정식 미연동

---

# 🔜 향후 계획

* PostgreSQL DB 연동
* 사용자별 채팅 기록 저장
* React 모바일 웹 챗봇 UI 연동
* HTP 리포트 `report_id` 기반 context 연결
* YOLOv8 기반 그림 분석 API 연결
* GPT + RAG 기반 HTP 리포트 생성 기능 구현
* 인증(JWT) 적용
* AWS EC2 배포
* RAG 검색 품질 개선
  * `top_k` 조정
  * category 필터링
  * 위험 키워드 우선 감지
  * 답변 출처 1~2개로 제한

---

# 🔐 Git 관리 주의사항

다음 파일 및 폴더는 GitHub에 업로드하지 않습니다.

```text
.env
.venv/
app/db/chroma/
```

`.env.example`은 팀원들이 환경변수 형식을 확인할 수 있도록 업로드합니다.

---

# 👥 Team SAI

* 김민하
* 김민지
* 김하영
* 박하은
* 이희원

---