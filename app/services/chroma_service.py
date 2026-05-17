import chromadb

from app.core.config import CHROMA_PATH
from app.services.openai_service import create_embedding

client = chromadb.PersistentClient(path=CHROMA_PATH)


def get_collection(collection_name: str):
    return client.get_or_create_collection(name=collection_name)


def reset_collection(collection_name: str):
    """
    특정 ChromaDB collection을 삭제하고 새로 만든다.
    데이터셋을 다시 넣을 때 사용한다.
    """
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    return get_collection(collection_name)


def add_documents(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
    collection_name: str,
):
    """
    document를 embedding한 뒤 지정한 ChromaDB collection에 저장한다.
    """
    collection = get_collection(collection_name)
    embeddings = [create_embedding(doc) for doc in documents]

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def search_documents(
    query: str,
    top_k: int = 4,
    collection_name: str = "parenting_guides",
) -> list[dict]:
    """
    query를 embedding한 뒤 지정한 ChromaDB collection에서 관련 문서를 검색한다.
    """
    collection = get_collection(collection_name)
    query_embedding = create_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    output = []

    if not results["ids"] or not results["ids"][0]:
        return output

    for i in range(len(results["ids"][0])):
        output.append(
            {
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
        )

    return output
