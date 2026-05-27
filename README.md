# 🎨 GDAM Backend

HTP 그림 기반 AI 심리 분석 및 육아 상담 서비스 <strong>그담(GDAM)</strong>의 백엔드 API 서버입니다.

본 프로젝트는 **FastAPI + PostgreSQL + OpenAI API + ChromaDB + YOLO/OpenCV** 기반으로 구성되어 있으며, 아이가 그린 HTP 그림을 분석해 리포트를 생성하고, 이후 부모가 리포트를 바탕으로 육아 상담을 받을 수 있도록 설계되었습니다.

---

## 📌 프로젝트 개요

* 서비스명: **그담(GDAM)**
* 목적: 아이의 HTP 그림 검사 결과를 기반으로 부모에게 이해하기 쉬운 심리 분석 리포트와 육아 방향을 제공
* 주요 기능:

  * 자녀 정보 관리
  * HTP 검사 생성 및 이미지 업로드
  * YOLO/OpenCV 기반 그림 특징 추출
  * HTP 리포트 생성용 RAG
  * 리포트 기반 육아 상담 챗봇
  * 사용자 인증 및 JWT 기반 로그인
  * Swagger 기반 API 문서 제공

---

## 현재 구현 상태

### 1. Backend 기본 구조

* FastAPI 기반 백엔드 서버 구축
* Swagger/OpenAPI 문서 자동 생성
* 라우터 분리 구조 적용
* 서비스 로직 분리
* 환경변수 기반 설정 관리
* `.env.example` 기반 팀원 환경 설정 공유 구조 구성

### 2. Database

* PostgreSQL 연동 완료
* SQLAlchemy ORM 적용
* psycopg 기반 DB 연결
* 주요 DB 테이블 생성 완료

  * `users`
  * `children`
  * `htp_tests`
  * `chat_sessions`
  * `chat_messages`
* 개발용 테이블 생성/삭제/시드 스크립트 작성
* 이미지 파일은 DB에 직접 저장하지 않고, 로컬 경로만 DB에 저장

### 3. Auth / JWT / Google OAuth

* 회원가입 API 구현
* 로그인 API 구현
* 비밀번호 해싱 적용
* JWT access token 발급 구조 구현
* 인증이 필요한 API에서 현재 사용자 정보를 가져오는 구조 적용
* Google OAuth 로그인 구현
* 프론트 플로우 기준 auth API 수정 반영
* ⚠️ 배포 도메인 기준 Google OAuth redirect URI 최종 정렬 필요

### 4. Children

* 자녀 목록 조회
* 자녀 등록
* 자녀 정보 수정
* 자녀 삭제
* 로그인 사용자 기준으로 자녀 데이터 관리

### 5. HTP Test / PDI

* HTP 검사 row 생성
* 검사 이미지 업로드
* 업로드 이미지를 `uploads/` 폴더에 저장
* DB에는 이미지 경로 저장
* PDI 질문 생성 API 구현
* PDI 질문 생성 시 질문 목록 반환
* PDI 질문별 단계적 답변 및 건너뛰기 기능 구현
* 그리기 소요 시간 저장 endpoint 추가
* PDI 전체 건너뛰기 가능 상태 반영
* 프론트 검사 플로우 기준 tests API 응답 개선
* 검사 상태 조회 API 구성
* ⚠️ `/tests/{test_id}/analyze`에 실제 YOLO/OpenCV/RAG 결과를 연결하는 작업은 추가 확인 필요

### 6. YOLO / OpenCV 분석 파이프라인

* HTP YOLO/OpenCV 분석 파이프라인 구현 PR 반영
* multi-model YOLO inference pipeline 추가
* 집/나무/사람 모델을 분리한 다중 YOLO 모델 구조 반영

  * house model
  * tree model
  * person model
* multi-model YOLO 설정을 위한 `.env.example` 업데이트
* deployment 환경변수 및 dependencies 업데이트
* ⚠️ 세 모델의 output을 리포트 생성 schema에 맞게 최종 정렬하는 작업은 추가 확인 필요
* ⚠️ 프론트에 전달할 분석 결과/시각화 결과 형식 최종 확인 필요

### 7. HTP 리포트 생성 RAG

* HTP 리포트 생성을 위한 RAG 데이터 디렉토리 구성
* HTP 지식 데이터와 출처 데이터 분리
* HTP 리포트 생성용 ChromaDB collection 분리 구조 구성
* HTP 분석 결과를 바탕으로 리포트 JSON을 생성하는 방향 설계
* ⚠️ 실제 `/tests/{test_id}/analyze`에 YOLO/OpenCV 결과와 HTP RAG 연결 필요
* ⚠️ GPT 응답을 `summary_text`, `report_text`, `report_json`, `recommendations_json` 형태로 저장하는 흐름 정리 필요

### 8. 육아 상담 RAG 챗봇

* 육아 상담용 RAG 데이터셋 구축
* `parenting_guides.json` / `sources.json` 기반 데이터 관리
* OpenAI embedding 생성
* ChromaDB 저장 기능 구현
* RAG 검색 테스트 API 구현
* GPT API 기반 근거 답변 생성 구현
* 답변에 출처와 안전 안내문 포함
* 채팅 세션 및 메시지 DB 저장 구조 구현
* ⚠️ 리포트 기반 context 연결 및 이전 대화 history 반영 고도화 필요

### 9. Reports

* 리포트 목록 조회 API 구성
* 리포트 상세 조회 API 구성
* 별도 `reports` 테이블 없이 `htp_tests`를 리포트 저장소로 활용
* `report_json`, `recommendations_json` 기반 프론트 리포트 화면 구성 가능
* ⚠️ 실제 HTP 분석 결과 기반 리포트 생성 연결 필요

### 10. Deployment

* AWS EC2 기반 서버 실행 준비
* systemd 기반 FastAPI 서비스 실행 구조 설정
* deployment 환경변수 및 dependencies 업데이트
* DuckDNS 도메인 연결 작업 진행
* Nginx reverse proxy 설정 진행
* Google OAuth redirect URI 등록을 위한 도메인 정렬 진행
* ⚠️ SSL 인증서 발급 및 HTTPS 최종 적용 필요
* ⚠️ 프론트엔드와 API base URL 최종 정렬 필요

### 11. Frontend API Sync

* Home API를 프론트 디자인 기준으로 정렬
* Auth/Mypage API를 프론트 플로우 기준으로 수정
* Children API validation 추가
* Tests API 응답을 프론트 검사 플로우 기준으로 개선
* Reports API를 프론트 화면 기준으로 정렬
* Chat API를 프론트 화면 기준으로 정렬
* ⚠️ 현재 작업 브랜치가 `feat/api-frontend-sync`이므로 main 반영 여부는 PR 머지 후 확인 필요

---

## ⚙️ 기술 스택

| 구분                | 기술                               |
| ----------------- | -------------------------------- |
| Backend Framework | FastAPI                          |
| API Docs          | Swagger / OpenAPI                |
| Language          | Python                           |
| Database          | PostgreSQL                       |
| ORM               | SQLAlchemy                       |
| DB Driver         | psycopg                          |
| Authentication    | JWT, password hashing            |
| LLM               | OpenAI API                       |
| Embedding         | OpenAI Embedding Model           |
| Vector DB         | ChromaDB                         |
| Image Processing  | OpenCV                           |
| Object Detection  | YOLO                             |
| Deployment        | AWS EC2, systemd, Nginx, DuckDNS |
| Data Format       | JSON / JSONB                     |

---

## 📂 프로젝트 구조

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   └── prompts.py
│   ├── data/
│   │   └── rag/
│   │       ├── htp_report_generation/
│   │       │   ├── htp_knowledge.json
│   │       │   └── sources.json
│   │       └── parenting_chatbot/
│   │           ├── parenting_guides.json
│   │           └── sources.json
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── session.py
│   │   └── chroma/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── child.py
│   │   ├── htp_test.py
│   │   └── chat.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── home.py
│   │   ├── children.py
│   │   ├── tests.py
│   │   ├── reports.py
│   │   ├── chat.py
│   │   ├── mypage.py
│   │   └── rag_admin.py
│   ├── schemas/
│   └── services/
├── scripts/
│   ├── create_tables.py
│   ├── drop_tables.py
│   ├── seed_test_data.py
│   ├── ingest_parenting_guides.py
│   └── ingest_htp_knowledge.py
├── uploads/
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 로컬 실행 방법

### 1. 가상환경 생성 및 활성화

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성합니다.

```env
# OpenAI
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# ChromaDB
CHROMA_PATH=./app/db/chroma
CHROMA_PARENTING_COLLECTION=parenting_guides
CHROMA_HTP_COLLECTION=htp_knowledge

# PostgreSQL
DATABASE_URL=postgresql+psycopg://gdam_user:your_db_password@localhost:5432/gdam_db

# YOLO HTP Models
YOLO_HTP_HOUSE_WEIGHTS_PATH=본인_weights경로/house_best.pt
YOLO_HTP_TREE_WEIGHTS_PATH=본인_weights경로/tree_best.pt
YOLO_HTP_PERSON_WEIGHTS_PATH=본인_weights경로/person_best.pt
YOLO_HTP_MODEL_NAME_HOUSE=yolov8m_house
YOLO_HTP_MODEL_NAME_TREE=yolov8m_tree
YOLO_HTP_MODEL_NAME_PERSON=yolov8m_person
YOLO_HTP_CONF_THRESHOLD=0.25
YOLO_HTP_FALLBACK_ENABLED=true

# JWT
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

`.env` 파일에는 API key, DB password, JWT secret 등이 포함되므로 GitHub에 업로드하지 않습니다.
팀원 공유용으로는 `.env.example`만 업로드합니다.

### 4. DB 테이블 생성

```bash
python scripts/create_tables.py
```

개발 중 테이블을 초기화해야 하는 경우:

```bash
python scripts/drop_tables.py
python scripts/create_tables.py
python scripts/seed_test_data.py
```

### 5. RAG 데이터 ingest

육아 상담 RAG 데이터 저장:

```bash
python scripts/ingest_parenting_guides.py
```

HTP 리포트 RAG 데이터 저장:

```bash
python scripts/ingest_htp_knowledge.py
```

또는 Swagger에서 관리자용 API를 통해 ingest할 수 있습니다.

### 6. 서버 실행

```bash
uvicorn app.main:app --reload
```

서버 실행 후 Swagger 문서에 접속합니다.

```text
http://127.0.0.1:8000/docs
```

---

## 📄 API 구성

## Auth

| Method | Endpoint       | 설명           |
| ------ | -------------- | ------------ |
| POST   | `/auth/signup` | 회원가입         |
| POST   | `/auth/login`  | 로그인 및 JWT 발급 |
| POST   | `/auth/logout` | 로그아웃         |

---

## Home

| Method | Endpoint        | 설명            |
| ------ | --------------- | ------------- |
| GET    | `/home/summary` | 홈 화면 요약 정보 조회 |

홈 화면에서 다음 정보를 제공합니다.

* 마지막 검사 경과
* 최근 검사 요약
* 최근 리포트 요약
* 최근 챗봇 대화 요약

---

## Children

| Method | Endpoint               | 설명       |
| ------ | ---------------------- | -------- |
| GET    | `/children`            | 자녀 목록 조회 |
| POST   | `/children`            | 자녀 등록    |
| PATCH  | `/children/{child_id}` | 자녀 정보 수정 |
| DELETE | `/children/{child_id}` | 자녀 삭제    |

---

## Tests

| Method | Endpoint                     | 설명         |
| ------ | ---------------------------- | ---------- |
| POST   | `/tests`                     | HTP 검사 생성  |
| POST   | `/tests/{test_id}/image`     | 검사 이미지 업로드 |
| GET    | `/tests/{test_id}/questions` | PDI 질문 조회  |
| POST   | `/tests/{test_id}/answers`   | PDI 답변 저장  |
| POST   | `/tests/{test_id}/analyze`   | HTP 분석 요청  |
| GET    | `/tests/{test_id}`           | 검사 상세 조회   |

현재 `/tests/{test_id}/analyze`는 YOLO/OpenCV/HTP RAG 연결을 위한 핵심 endpoint입니다.
최종 목표는 다음 흐름입니다.

```text
검사 이미지 업로드
→ house/tree/person YOLO 모델 각각 추론
→ 세 모델의 detection output 조합
→ OpenCV 기반 세부 feature 추출
→ PDI 답변과 함께 HTP RAG prompt 구성
→ GPT가 리포트 생성
→ DB에 summary/report/recommendation 저장
```

---

## Reports

| Method | Endpoint               | 설명        |
| ------ | ---------------------- | --------- |
| GET    | `/reports`             | 리포트 목록 조회 |
| GET    | `/reports/{report_id}` | 리포트 상세 조회 |

현재 `report_id`는 내부적으로 `htp_tests.id`와 동일하게 사용합니다.

---

## Chat

| Method | Endpoint                                   | 설명                     |
| ------ | ------------------------------------------ | ---------------------- |
| POST   | `/api/chat/sessions`                       | 채팅 세션 생성               |
| GET    | `/api/chat/sessions`                       | 채팅 세션 목록 조회            |
| GET    | `/api/chat/sessions/{session_id}`          | 채팅 세션 상세 조회            |
| POST   | `/api/chat/sessions/{session_id}/messages` | 사용자 메시지 전송 및 RAG 답변 생성 |
| GET    | `/api/chat/suggested-prompts`              | 추천 질문 조회               |

챗봇은 단순 GPT 응답이 아니라, 관리된 육아 가이드 데이터를 ChromaDB에서 검색한 뒤 해당 근거를 prompt에 포함하여 답변을 생성합니다.

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
      "display_sources": "CDC, Positive Parenting Tips for Healthy Child Development",
      "source_urls": "https://stacks.cdc.gov/...",
      "licenses": "Public Domain",
      "usage_decisions": "사용 가능"
    }
  ],
  "safety_notice": "본 답변은 전문 심리 진단이나 치료를 대체하지 않으며, 아이의 상태가 지속적으로 걱정되거나 위험 신호가 보이면 전문가 상담을 권장합니다."
}
```

---

## Mypage

| Method | Endpoint                | 설명          |
| ------ | ----------------------- | ----------- |
| GET    | `/mypage`               | 마이페이지 정보 조회 |
| PATCH  | `/mypage/account`       | 계정 정보 수정    |
| PATCH  | `/mypage/notifications` | 알림 설정 수정    |

---

## RAG Admin

| Method | Endpoint                         | 설명                     |
| ------ | -------------------------------- | ---------------------- |
| POST   | `/api/admin/rag/ingest`          | RAG 데이터 ChromaDB 저장    |
| GET    | `/api/admin/rag/search-test`     | RAG 검색 테스트             |
| POST   | `/api/admin/rag/ingest-htp`      | HTP 지식 데이터 ChromaDB 저장 |
| GET    | `/api/admin/rag/search-test-htp` | HTP RAG 검색 테스트         |

관리자용 endpoint이며, 개발 중 RAG 데이터 ingest와 검색 품질 확인에 사용합니다.

---

## 🧠 RAG 구조

## 1. 육아 상담 RAG

### 데이터 위치

```text
app/data/rag/parenting_chatbot/
├── parenting_guides.json
└── sources.json
```

### 동작 흐름

```text
사용자 질문
→ 질문 embedding 생성
→ ChromaDB parenting collection 검색
→ 관련 guide와 source 추출
→ GPT prompt에 근거로 삽입
→ 답변 생성
→ 답변, 출처, 안전 안내문 반환
```

### 주요 안전 규칙

* 검색된 육아 가이드를 중심으로 답변
* 아이의 심리 상태나 질환을 단정하지 않음
* HTP 리포트는 참고 정보로만 사용
* 부모를 비난하지 않음
* 실천 가능한 대화 예시와 행동 가이드를 제공
* 위험 신호가 있는 경우 전문기관 상담 안내
* 전문 심리 진단이나 치료를 대체하지 않는다는 안내 포함

---

## 2. HTP 리포트 생성 RAG

### 데이터 위치

```text
app/data/rag/htp_report_generation/
├── htp_knowledge.json
└── sources.json
```

### 목표 흐름

```text
YOLO/OpenCV feature
+ PDI 답변
+ 자녀 기본 정보
→ HTP 지식 collection 검색
→ 관련 근거를 GPT prompt에 삽입
→ 보호자가 이해하기 쉬운 리포트 생성
→ DB 저장
```

### 리포트 저장 목표 필드

```text
summary_text
report_text
report_json
recommendations_json
```

리포트는 진단처럼 단정하지 않고, 그림에서 관찰된 특징과 아이의 답변을 바탕으로 보호자가 참고할 수 있는 방향으로 작성합니다.

---

## 🖼️ YOLO / OpenCV 분석 구조

HTP 그림 분석은 단일 모델이 아니라, 집/나무/사람 각각의 fine-tuned YOLO 모델을 사용하는 구조로 확장합니다.

```text
입력 이미지
→ house YOLO model
→ tree YOLO model
→ person YOLO model
→ detection 결과 통합
→ OpenCV 기반 feature 추출
→ HTP report RAG로 전달
```

### 환경변수 예시

```env
YOLO_HTP_HOUSE_WEIGHTS_PATH=본인_weights경로/house_best.pt
YOLO_HTP_TREE_WEIGHTS_PATH=본인_weights경로/tree_best.pt
YOLO_HTP_PERSON_WEIGHTS_PATH=본인_weights경로/person_best.pt
YOLO_HTP_MODEL_NAME_HOUSE=yolov8m_house
YOLO_HTP_MODEL_NAME_TREE=yolov8m_tree
YOLO_HTP_MODEL_NAME_PERSON=yolov8m_person
YOLO_HTP_CONF_THRESHOLD=0.25
YOLO_HTP_FALLBACK_ENABLED=true
```

`*.pt` 가중치 파일은 용량이 크므로 GitHub에 업로드하지 않습니다.
각 팀원은 본인 로컬 또는 서버의 실제 가중치 경로를 `.env`에 설정해야 합니다.

---

## 🔐 Git 관리 주의사항

다음 파일과 폴더는 GitHub에 업로드하지 않습니다.

```text
.env
.env.*
.venv/
app/db/chroma/
uploads/
media/
generated/
outputs/
*.pt
```

단, 팀원 환경 설정 공유를 위해 `.env.example`은 업로드합니다.

---

## ☁️ 배포 메모

현재 AWS EC2 기반 배포를 진행합니다.

기본 구조는 다음과 같습니다.

```text
Client
→ DuckDNS domain
→ Nginx
→ FastAPI Uvicorn service
→ PostgreSQL / ChromaDB / uploads
```

서버에서는 systemd를 통해 FastAPI 백엔드 서비스를 관리합니다.

주요 확인 명령어:

```bash
sudo systemctl status gdam-backend
sudo systemctl restart gdam-backend
sudo journalctl -u gdam-backend -f
```

GitHub main branch 변경 사항을 서버에 반영할 때는 EC2 서버에서 pull 후 서비스를 재시작합니다.

```bash
cd backend
source .venv/bin/activate
git pull origin main
pip install -r requirements.txt
sudo systemctl restart gdam-backend
```

---

## 🔜 남은 작업

### 우선순위 높음

* [ ] 프론트엔드와 API request/response 최종 정렬
* [ ] Google OAuth redirect URI 및 배포 도메인 정리
* [ ] SSL 인증서 발급 및 HTTPS 적용
* [ ] YOLO 3개 모델 추론 로직 연결
* [ ] 세 모델의 detection output 통합 schema 정의
* [ ] OpenCV feature 추출 결과 schema 정의
* [ ] `/tests/{test_id}/analyze`에 실제 HTP 분석 파이프라인 연결
* [ ] HTP 리포트 생성 RAG 최종 연결
* [ ] PDI 답변을 리포트 생성 prompt에 반영

### 우선순위 중간

* [ ] 육아 상담 챗봇에서 리포트 context 활용 강화
* [ ] 채팅 답변에 이전 대화 history 반영
* [ ] RAG 검색 품질 개선
* [ ] RAG source 표시 형식 간소화
* [ ] 리포트 JSON 형식 프론트 화면과 맞추기
* [ ] 예외 처리 및 에러 응답 형식 통일

### 추후 개선

* [ ] 이미지 저장소를 로컬 `uploads/`에서 AWS S3로 확장
* [ ] CI/CD 적용 검토
* [ ] Docker 적용 검토
* [ ] 관리자용 RAG 데이터 관리 기능 추가
* [ ] 테스트 코드 작성

---

## 👥 Team SAI

* 김민하
* 김민지
* 김하영
* 박하은
* 이희원

---

## 📎 참고

이 README는 현재 개발 진행 상황을 기준으로 작성되었습니다.
실제 API 응답 형식이나 환경변수명은 프론트엔드 연동 및 팀원 작업 결과에 따라 변경될 수 있습니다.
