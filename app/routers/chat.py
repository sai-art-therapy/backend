from fastapi import APIRouter
from pydantic import BaseModel

from app.services.rag_service import answer_with_rag

router = APIRouter()


class ChatMessageRequest(BaseModel):
    message: str
    report_id: int | None = None


@router.post("/sessions", summary="새 채팅 시작")
def create_chat_session():
    return {
        "session_id": 1,
        "message": "새 상담이 시작되었습니다."
    }


@router.get("/sessions", summary="이전 상담 목록 조회")
def get_chat_sessions():
    return [
        {
            "session_id": 1,
            "title": "불안감 관련 상담",
            "last_message": "아이의 감정을 먼저 공감해주는 것이 좋습니다.",
            "updated_at": "2026-05-03T12:00:00"
        }
    ]


@router.get("/sessions/{session_id}", summary="상담 내용 불러오기")
def get_chat_session(session_id: int):
    return {
        "session_id": session_id,
        "messages": [
            {
                "role": "user",
                "content": "최근 리포트 기반으로 어떻게 도와주면 좋을까요?"
            },
            {
                "role": "assistant",
                "content": "아이의 감정을 먼저 인정해주고 안정적인 루틴을 만들어주는 것이 좋습니다."
            }
        ]
    }


@router.post("/sessions/{session_id}/messages", summary="챗봇 메시지 전송")
def send_chat_message(session_id: int, request: ChatMessageRequest):
    result = answer_with_rag(
        message=request.message,
        report_id=str(request.report_id) if request.report_id is not None else None
    )

    return {
        "session_id": session_id,
        "answer": result["answer"],
        "sources": result["sources"],
        "safety_notice": result["safety_notice"]
    }