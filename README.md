# 🎨 GDAM Backend

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=flat-square&logo=postgresql&logoColor=white"/>
  <img src="https://img.shields.io/badge/ChromaDB-RAG-5B5FC7?style=flat-square"/>
  <img src="https://img.shields.io/badge/OpenAI-LLM-412991?style=flat-square&logo=openai&logoColor=white"/>
  <img src="https://img.shields.io/badge/AWS EC2-Deploy-FF9900?style=flat-square&logo=amazonaws&logoColor=white"/>
</p>

<p align="center">
아동 HTP 그림 검사와 PDI 답변을 기반으로 보호자 양육 지원 리포트와 상담 챗봇을 제공하는 FastAPI 백엔드 서버
</p>

---

## 📌 Overview

GDAM Backend는 아동 HTP(집-나무-사람) 그림 검사와 PDI 답변을 기반으로 보호자에게 참고용 리포트와 양육 상담 챗봇을 제공하는 FastAPI 기반 백엔드 서버입니다.

본 레포지토리는 전체 서비스 중 **백엔드 API, 데이터베이스, 이미지 분석 연동, RAG, 리포트 생성, 챗봇 기능**을 담당합니다.

> 본 서비스의 HTP 리포트와 챗봇 답변은 보호자 양육 지원을 위한 참고 자료이며, 의료적 진단이나 전문 상담을 대체하지 않습니다.

<br>

## 🧭 Repository Role

| 구분 | Repository |
| --- | --- |
| Project Overview | [GDAM Organization](https://github.com/sai-art-therapy) |
| Frontend | [Frontend Repository](https://github.com/sai-art-therapy/frontend) |
| Backend | [Backend Repository](https://github.com/sai-art-therapy/backend) |
| AI / Model | [AI Repository](https://github.com/sai-art-therapy/ai) |

<br>

## 👥 Team Contribution

| 담당자 | 담당 영역 | 주요 작업 |
| --- | --- | --- |
| 김민하 | Backend / Database / RAG / Infra | FastAPI 서버 구조 설계, PostgreSQL 모델 및 API 구현, 양육 가이드 데이터셋 구축 및 ChromaDB 연동, HTP 지식 데이터 RAG 구축, OpenAI 기반 챗봇 구현, 홈/검사/리포트/채팅 API 개발, AWS EC2 배포, Nginx 및 HTTPS 설정 |
| 김하영 | Auth / PDI / Report | Google OAuth 로그인, JWT 인증, HTP 학술 지식 데이터셋 구축 및 정제, PDI 질문 생성 및 답변 저장 로직, HTP 리포트 생성 파이프라인 구현, 리포트 생성용 프롬프트 및 결과 구조 설계 |
| 김민지 | AI Integration / Image Analysis | HTP 데이터셋 구축 및 객체 클래스 재정의, YOLOv8 기반 집·나무·사람 객체 탐지 모델 Fine-tuning 및 추론, 객체 탐지 결과 검증 및 후처리 로직 적용, 이미지 분석 결과 리포트 생성 기능 연동 |
---

## 주요 기능

### 1. 사용자 인증 및 자녀 관리

* Google OAuth 기반 로그인
* JWT access token 발급 및 인증 사용자 조회
* 자녀 정보 등록, 조회, 수정, 삭제

### 2. HTP 검사 흐름

* HTP 검사 생성
* 집, 나무, 사람 그림 이미지 업로드
* 검사 상태 관리
* 그리기 소요 시간 저장

### 3. 이미지 분석

* YOLO 모델 기반 집/나무/사람 객체 탐지
* OpenCV 기반 이미지 후처리
* 객체 위치, 크기, 비율 등 시각적 특징 추출
* 분석 결과 이미지 및 JSON 저장

### 4. PDI 질문 및 답변

* 이미지 분석 결과 기반 PDI 질문 생성
* 질문별 답변 저장
* 답변하기 어려운 질문 스킵 처리
* PDI 답변을 리포트 생성에 반영

### 5. AI 리포트 생성

* HTP 관련 지식 데이터 기반 RAG 검색
* 이미지 분석 결과와 PDI 답변을 함께 활용
* OpenAI API 기반 참고용 HTP 리포트 JSON 생성
* 리포트 목록 및 상세 조회 API 제공

### 6. 양육 상담 챗봇

* 일반 양육 상담 세션 생성
* HTP 리포트 기반 상담 세션 생성
* ChromaDB 기반 양육 가이드 RAG 검색
* 최근 대화 히스토리를 반영한 챗봇 답변 생성

### 7. 홈 / 마이페이지

* 최근 검사 및 리포트 요약 제공
* 리포트 기반 상담 카드 제공
* 사용자 프로필 조회 및 수정
* 회원 탈퇴 처리

---

## 기술 스택

| 영역              | 기술                             |
| --------------- | ------------------------------ |
| Language        | Python                         |
| Framework       | FastAPI, Uvicorn               |
| Database        | PostgreSQL                     |
| ORM             | SQLAlchemy                     |
| Auth            | Google OAuth, JWT, python-jose |
| AI / LLM        | OpenAI API                     |
| RAG / Vector DB | ChromaDB, OpenAI Embedding     |
| Image Analysis  | YOLOv8, OpenCV, Pillow         |
| Config          | Pydantic, python-dotenv        |
| Infra           | AWS EC2, Nginx, HTTPS(Certbot) |

---

## 폴더 구조

```text
backend/
├── app/
│   ├── main.py
│   ├── core/          # 설정, 인증, 프롬프트
│   ├── db/            # DB 세션, ChromaDB
│   ├── models/        # SQLAlchemy 모델
│   ├── routers/       # API 라우터
│   ├── schemas/       # Pydantic 스키마
│   ├── services/      # 비즈니스 로직, RAG, OpenAI, YOLO
│   └── data/rag/      # RAG용 지식 데이터
├── ml_models/yolo/    # YOLO 모델 파일
├── scripts/           # DB/RAG 초기화 스크립트
├── uploads/           # 업로드 이미지 및 분석 결과 저장
├── requirements.txt
├── .env.example
└── README.md
```

---

## 실행 방법

### 1. 가상환경 생성 및 패키지 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

`.env`에는 OpenAI API Key, PostgreSQL URL, JWT Secret, Google OAuth 정보 등을 설정합니다.
실제 키 값은 GitHub에 업로드하지 않습니다.

### 3. PostgreSQL 테이블 생성

```bash
python scripts/create_tables.py
```

### 4. RAG 데이터 적재

```bash
python scripts/ingest_parenting_guides.py
```

HTP 지식 데이터는 서버 실행 후 관리자 API를 통해 적재할 수 있습니다.

```bash
curl -X POST http://localhost:8000/api/admin/rag/ingest-htp
```

### 5. 개발 서버 실행

```bash
uvicorn app.main:app --reload
```

* API 서버: `http://localhost:8000`
* Swagger 문서: `http://localhost:8000/docs`

---

## 주요 환경 변수

```env
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=
OPENAI_EMBEDDING_MODEL=

DATABASE_URL=

CHROMA_PATH=
CHROMA_PARENTING_COLLECTION=
CHROMA_HTP_COLLECTION=

JWT_SECRET_KEY=
JWT_ALGORITHM=
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
FRONTEND_AUTH_CALLBACK_URL=

YOLO_HTP_HOUSE_WEIGHTS_PATH=
YOLO_HTP_TREE_WEIGHTS_PATH=
YOLO_HTP_PERSON_WEIGHTS_PATH=
YOLO_HTP_IMAGE_SIZE=
YOLO_HTP_CONF_THRESHOLD=
YOLO_HTP_FALLBACK_ENABLED=
```

---

## 배포 환경

* AWS EC2 Ubuntu 서버
* FastAPI + Uvicorn
* Nginx reverse proxy
* HTTPS 인증서 적용
* PostgreSQL 데이터베이스
* ChromaDB persistent vector store
* 프론트엔드 배포 주소와 CORS 연동

운영 서버에서는 환경 변수를 별도로 관리하며, `.env`, API Key, DB URL, Secret Key 등 민감정보는 레포지토리에 포함하지 않습니다.
