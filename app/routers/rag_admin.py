from fastapi import APIRouter, Query

from app.core.config import CHROMA_HTP_COLLECTION, CHROMA_PARENTING_COLLECTION
from app.services.chroma_service import search_documents
from app.services.htp_ingest_service import ingest_htp_knowledge
from app.services.ingest_service import ingest_parenting_guides

router = APIRouter(prefix="/api/admin/rag", tags=["RAG Admin"])


@router.post("/ingest")
def ingest():
    """
    parenting_guides.json을 ChromaDB parenting_guides collection에 저장한다.
    """
    return ingest_parenting_guides(reset=True)


@router.get("/search-test")
def search_test(
    q: str = Query(..., description="검색할 사용자 질문"),
    top_k: int = Query(4, description="검색 결과 개수"),
):
    """
    사용자 질문이 어떤 parenting guide와 매칭되는지 테스트한다.
    """
    return search_documents(
        query=q,
        top_k=top_k,
        collection_name=CHROMA_PARENTING_COLLECTION,
    )


@router.post("/ingest-htp")
def ingest_htp():
    """
    htp_knowledge.json을 ChromaDB htp_knowledge collection에 저장한다.
    """
    return ingest_htp_knowledge(reset=True)


@router.get("/search-htp-test")
def search_htp_test(
    q: str = Query(..., description="검색할 HTP 분석 query"),
    top_k: int = Query(4, description="검색 결과 개수"),
):
    """
    HTP feature/PDI query가 어떤 HTP 지식 chunk와 매칭되는지 테스트한다.
    """
    return search_documents(
        query=q,
        top_k=top_k,
        collection_name=CHROMA_HTP_COLLECTION,
    )