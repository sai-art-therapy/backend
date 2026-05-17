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


if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL이 설정되지 않았습니다. .env 파일을 확인하세요.")