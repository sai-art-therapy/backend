from openai import OpenAI

from app.core.config import (
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
    OPENAI_EMBEDDING_MODEL,
)

client = OpenAI(api_key=OPENAI_API_KEY)


def create_embedding(text: str) -> list[float]:
    """
    입력 텍스트를 OpenAI embedding vector로 변환한다.
    ChromaDB 저장/검색에 사용된다.
    """
    response = client.embeddings.create(
        model=OPENAI_EMBEDDING_MODEL,
        input=text
    )
    return response.data[0].embedding


def generate_answer(prompt: str) -> str:
    """
    RAG 검색 결과와 사용자 질문을 바탕으로 GPT 답변을 생성한다.
    """
    response = client.responses.create(
        model=OPENAI_CHAT_MODEL,
        input=prompt
    )
    return response.output_text