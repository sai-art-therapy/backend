import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_VLM_FALLBACK_ENABLED = os.getenv("OPENAI_VLM_FALLBACK_ENABLED", "false").lower() == "true"
OPENAI_VLM_MODEL = os.getenv("OPENAI_VLM_MODEL", "gpt-5.6-luna")
OPENAI_VLM_VERIFY_CONF_MAX = float(os.getenv("OPENAI_VLM_VERIFY_CONF_MAX", "0.60"))

# ChromaDB 설정
CHROMA_PATH = os.getenv("CHROMA_PATH", "./app/db/chroma")
CHROMA_PARENTING_COLLECTION = os.getenv("CHROMA_PARENTING_COLLECTION", "parenting_guides")
CHROMA_HTP_COLLECTION = os.getenv("CHROMA_HTP_COLLECTION", "htp_knowledge")

# PostgreSQL 설정
DATABASE_URL = os.getenv("DATABASE_URL")
SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"

# YOLO HTP 이미지 분석 설정 (house / tree / person 모델 분리)
YOLO_HTP_HOUSE_WEIGHTS_PATH  = os.getenv("YOLO_HTP_HOUSE_WEIGHTS_PATH",  "ml_models/yolo/house_best.pt")
YOLO_HTP_TREE_WEIGHTS_PATH   = os.getenv("YOLO_HTP_TREE_WEIGHTS_PATH",   "ml_models/yolo/tree_best.pt")
YOLO_HTP_PERSON_WEIGHTS_PATH = os.getenv("YOLO_HTP_PERSON_WEIGHTS_PATH", "ml_models/yolo/person_best.pt")

YOLO_HTP_MODEL_NAME_HOUSE    = os.getenv("YOLO_HTP_MODEL_NAME_HOUSE",  "yolov8m_house")
YOLO_HTP_MODEL_NAME_TREE     = os.getenv("YOLO_HTP_MODEL_NAME_TREE",   "yolov8m_tree")
YOLO_HTP_MODEL_NAME_PERSON   = os.getenv("YOLO_HTP_MODEL_NAME_PERSON", "yolov8m_person")

YOLO_HTP_IMAGE_SIZE      = int(os.getenv("YOLO_HTP_IMAGE_SIZE", "640"))
YOLO_HTP_CONF_THRESHOLD  = float(os.getenv("YOLO_HTP_CONF_THRESHOLD", "0.25"))
YOLO_HTP_FALLBACK_ENABLED = os.getenv("YOLO_HTP_FALLBACK_ENABLED", "true").lower() == "true"

# JWT 설정
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# 운영 관리자 API는 명시적으로 활성화한 환경에서만 사용합니다.
RAG_ADMIN_ENABLED = os.getenv("RAG_ADMIN_ENABLED", "false").lower() == "true"
RAG_ADMIN_TOKEN = os.getenv("RAG_ADMIN_TOKEN")

# Google OAuth 설정
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL이 설정되지 않았습니다. .env 파일을 확인하세요.")

if (
    not JWT_SECRET_KEY
    or len(JWT_SECRET_KEY) < 32
    or JWT_SECRET_KEY == "your-secret-key-change-this"
):
    raise ValueError("JWT_SECRET_KEY는 32자 이상의 안전한 값이어야 합니다.")

if RAG_ADMIN_ENABLED and (not RAG_ADMIN_TOKEN or len(RAG_ADMIN_TOKEN) < 32):
    raise ValueError(
        "RAG_ADMIN_ENABLED=true인 경우 RAG_ADMIN_TOKEN을 32자 이상으로 설정해야 합니다."
    )
