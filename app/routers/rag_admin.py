import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.core.config import (
    CHROMA_HTP_COLLECTION,
    CHROMA_PARENTING_COLLECTION,
    RAG_ADMIN_ENABLED,
    RAG_ADMIN_TOKEN,
)
from app.services.chroma_service import search_documents
from app.services.htp_ingest_service import ingest_htp_knowledge
from app.services.ingest_service import ingest_parenting_guides


def require_rag_admin(
    admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    if not RAG_ADMIN_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="관리자 API가 비활성화되어 있습니다.",
        )
    if not admin_token or not RAG_ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="관리자 인증이 필요합니다.",
        )
    if not secrets.compare_digest(admin_token, RAG_ADMIN_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 없습니다.",
        )


router = APIRouter(
    prefix="/api/admin/rag",
    tags=["RAG Admin"],
    dependencies=[Depends(require_rag_admin)],
)


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
