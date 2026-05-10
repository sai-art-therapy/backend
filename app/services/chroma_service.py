import chromadb

from app.core.config import CHROMA_PATH, CHROMA_COLLECTION
from app.services.openai_service import create_embedding

client = chromadb.PersistentClient(path=CHROMA_PATH)

collection = client.get_or_create_collection(
    name=CHROMA_COLLECTION
)


def reset_collection():
    """
    기존 ChromaDB collection을 삭제하고 새로 만든다.
    데이터셋을 다시 넣을 때 사용한다.
    """
    global collection

    try:
        client.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION
    )


def add_documents(ids: list[str], documents: list[str], metadatas: list[dict]):
    """
    document를 embedding한 뒤 ChromaDB에 저장한다.
    """
    embeddings = [create_embedding(doc) for doc in documents]

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )


def search_documents(query: str, top_k: int = 4) -> list[dict]:
    """
    사용자 질문을 embedding한 뒤 ChromaDB에서 관련 guide를 검색한다.
    """
    query_embedding = create_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    output = []

    if not results["ids"] or not results["ids"][0]:
        return output

    for i in range(len(results["ids"][0])):
        output.append({
            "id": results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })

    return output