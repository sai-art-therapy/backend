import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# ChromaDB 설정
CHROMA_PATH = os.getenv("CHROMA_PATH", "./app/db/chroma")
CHROMA_PARENTING_COLLECTION = os.getenv("CHROMA_PARENTING_COLLECTION", "parenting_guides")
CHROMA_HTP_COLLECTION = os.getenv("CHROMA_HTP_COLLECTION", "htp_knowledge")

# PostgreSQL 설정
DATABASE_URL = os.getenv("DATABASE_URL")

# YOLO HTP 이미지 분석 설정
YOLO_HTP_WEIGHTS_PATH = os.getenv("YOLO_HTP_WEIGHTS_PATH", "ml_models/yolo/best.pt")
YOLO_HTP_MODEL_NAME = os.getenv("YOLO_HTP_MODEL_NAME", "yolov8n_htp_20epoch")
YOLO_HTP_CONF_THRESHOLD = float(os.getenv("YOLO_HTP_CONF_THRESHOLD", "0.25"))
YOLO_HTP_FALLBACK_ENABLED = os.getenv("YOLO_HTP_FALLBACK_ENABLED", "true").lower() == "true"


if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL이 설정되지 않았습니다. .env 파일을 확인하세요.")