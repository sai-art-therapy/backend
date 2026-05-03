# 🎨 그담(GDAM) Backend API

HTP 그림 기반 AI 심리 분석 및 육아 방향 안내 서비스 **그담(GDAM)**의 백엔드 API 명세입니다.

본 프로젝트는 **FastAPI + Swagger(OpenAPI)** 기반으로 API를 설계하였으며,
현재는 **프론트엔드 개발을 위한 API 명세(Mock API)** 단계입니다.

---

# 📌 프로젝트 개요

* 서비스명: **그담 (GDAM)**
* 목적: 아이의 그림(HTP 검사)을 기반으로 심리 상태를 분석하고
  부모에게 맞춤형 육아 방향을 제공
* 현재 상태:

  * ✅ API 명세 설계 완료
  * ❌ 실제 DB / AI 모델 연동 전 (Mock 데이터 사용)

---

# ⚙️ 기술 스택

* **Backend Framework**: FastAPI
* **API Documentation**: Swagger (OpenAPI)
* **Language**: Python 3.13
* **Environment**: venv

---

# 📂 프로젝트 구조

```
backend/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── routers/             # API 라우터
│   │   ├── auth.py
│   │   ├── home.py
│   │   ├── children.py
│   │   ├── tests.py
│   │   ├── reports.py
│   │   ├── chat.py
│   │   └── mypage.py
│   └── schemas/             # 요청/응답 데이터 모델
│       ├── auth.py
│       ├── home.py
│       ├── children.py
│       ├── tests.py
│       ├── reports.py
│       ├── chat.py
│       └── mypage.py
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
pip install fastapi uvicorn python-multipart
pip install pydantic[email]
```

## 3. 서버 실행

```bash
uvicorn app.main:app --reload
```

---

# 📄 API 문서 (Swagger)

서버 실행 후 아래 주소로 접속:

```
http://127.0.0.1:8000/docs
```

👉 모든 API 명세를 Swagger UI에서 확인 가능

---

# 📌 API 구성 (탭 기준)

## 🏠 Home

* `GET /home/summary`
* 홈 화면 요약 정보 제공

  * 마지막 검사 경과
  * 변화 요약
  * 최근 리포트 요약
  * 챗봇 요약

---

## 💬 Chat

* `POST /chat/sessions`
* `GET /chat/sessions`
* `GET /chat/sessions/{session_id}`
* `POST /chat/sessions/{session_id}/messages`

👉 리포트 기반 RAG 상담 기능

---

## 🧠 Tests (검사)

* `POST /tests`
* `POST /tests/{test_id}/image`
* `GET /tests/{test_id}/questions`
* `POST /tests/{test_id}/answers`
* `POST /tests/{test_id}/analyze`
* `GET /tests/{test_id}`

👉 HTP 검사 진행 및 AI 분석 요청

---

## 📊 Reports

* `GET /reports`
* `GET /reports/{report_id}`

👉 검사 결과 리포트 조회

---

## 👶 Children

* `GET /children`
* `POST /children`
* `PATCH /children/{child_id}`
* `DELETE /children/{child_id}`

👉 자녀 정보 관리

---

## 👤 Mypage

* `GET /mypage`
* `PATCH /mypage/account`
* `PATCH /mypage/notifications`

👉 계정 및 알림 설정 관리

---

## 🔐 Auth

* `POST /auth/signup`
* `POST /auth/login`
* `POST /auth/logout`

👉 사용자 인증

---

# ⚠️ 현재 상태

본 API는 현재:

* DB 미연동
* AI 모델 미연동
* Mock 데이터 반환

👉 프론트엔드 개발을 위한 **API 계약(Mock API)** 단계입니다.

---

# 🔜 향후 계획

* PostgreSQL DB 연동
* YOLOv8 기반 그림 분석 API 연결
* GPT-4o + RAG 기반 리포트 생성
* 인증(JWT) 적용
* AWS EC2 배포

---

# 👥 Team SAI

* 김민하
* 김민지
* 김하영
* 박하은
* 이희원

---
