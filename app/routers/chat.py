from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.htp_test import HtpTest
from app.services.rag_service import answer_with_rag

router = APIRouter()

# TODO: 로그인/JWT 구현 후 실제 로그인 사용자 ID로 교체
TEST_USER_ID = 1


class ChatSessionCreateRequest(BaseModel):
    child_id: Optional[int] = None
    htp_test_id: Optional[int] = None
    title: Optional[str] = None


class ChatMessageRequest(BaseModel):
    message: str
    report_id: Optional[int] = None


@router.post("/sessions", summary="새 채팅 시작", status_code=status.HTTP_201_CREATED)
def create_chat_session(
    request: ChatSessionCreateRequest,
    db: Session = Depends(get_db),
):
    if request.htp_test_id is not None:
        htp_test = (
            db.query(HtpTest)
            .filter(
                HtpTest.id == request.htp_test_id,
                HtpTest.user_id == TEST_USER_ID,
            )
            .first()
        )

        if htp_test is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="기반 리포트를 찾을 수 없습니다.",
            )

    title = request.title

    if title is None:
        if request.htp_test_id is not None:
            title = "리포트 기반 상담"
        else:
            title = "일반 육아 상담"

    chat_session = ChatSession(
        user_id=TEST_USER_ID,
        child_id=request.child_id,
        htp_test_id=request.htp_test_id,
        title=title,
    )

    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    return {
        "session_id": chat_session.id,
        "user_id": chat_session.user_id,
        "child_id": chat_session.child_id,
        "htp_test_id": chat_session.htp_test_id,
        "title": chat_session.title,
        "created_at": chat_session.created_at,
        "updated_at": chat_session.updated_at,
        "message": "새 상담이 시작되었습니다.",
    }


@router.get("/sessions", summary="이전 상담 목록 조회")
def get_chat_sessions(db: Session = Depends(get_db)):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == TEST_USER_ID)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    result = []

    for session in sessions:
        last_message = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .first()
        )

        result.append(
            {
                "session_id": session.id,
                "child_id": session.child_id,
                "htp_test_id": session.htp_test_id,
                "title": session.title,
                "last_message": last_message.content if last_message else None,
                "updated_at": session.updated_at,
                "created_at": session.created_at,
            }
        )

    return result


@router.get("/sessions/{session_id}", summary="상담 내용 불러오기")
def get_chat_session(session_id: int, db: Session = Depends(get_db)):
    chat_session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == TEST_USER_ID,
        )
        .first()
    )

    if chat_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="상담방을 찾을 수 없습니다.",
        )

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return {
        "session_id": chat_session.id,
        "child_id": chat_session.child_id,
        "htp_test_id": chat_session.htp_test_id,
        "title": chat_session.title,
        "created_at": chat_session.created_at,
        "updated_at": chat_session.updated_at,
        "messages": [
            {
                "message_id": message.id,
                "role": message.role,
                "content": message.content,
                "sources": message.sources_json,
                "created_at": message.created_at,
            }
            for message in messages
        ],
    }


@router.post("/sessions/{session_id}/messages", summary="챗봇 메시지 전송")
def send_chat_message(
    session_id: int,
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
):
    chat_session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == TEST_USER_ID,
        )
        .first()
    )

    if chat_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="상담방을 찾을 수 없습니다.",
        )

    # 1. 사용자 메시지 저장
    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=request.message,
        sources_json=None,
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # 2. 리포트 기반 상담이면 chat_session.htp_test_id를 우선 사용
    report_id = request.report_id

    if report_id is None and chat_session.htp_test_id is not None:
        report_id = chat_session.htp_test_id

    # 3. RAG 답변 생성
    result = answer_with_rag(
        message=request.message,
        report_id=str(report_id) if report_id is not None else None,
    )

    # 4. assistant 메시지 저장
    assistant_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=result["answer"],
        sources_json=result["sources"],
    )
    db.add(assistant_message)

    # 5. 상담방 updated_at 갱신 유도
    chat_session.title = chat_session.title

    db.commit()
    db.refresh(assistant_message)
    db.refresh(chat_session)

    return {
        "session_id": session_id,
        "user_message": {
            "message_id": user_message.id,
            "role": user_message.role,
            "content": user_message.content,
            "created_at": user_message.created_at,
        },
        "assistant_message": {
            "message_id": assistant_message.id,
            "role": assistant_message.role,
            "content": assistant_message.content,
            "sources": assistant_message.sources_json,
            "created_at": assistant_message.created_at,
        },
        "answer": result["answer"],
        "sources": result["sources"],
        "safety_notice": result["safety_notice"],
    }


@router.get("/suggested-prompts", summary="추천 질문 조회")
def get_suggested_prompts(
    context: str = Query("general", description="home, report, general 중 하나"),
    htp_test_id: Optional[int] = None,
):
    if context == "home":
        prompts = [
            "자신감을 키워주려면 어떻게 해야 할까요?",
            "다음에는 어떤 활동을 함께해볼까요?",
            "아이의 마음을 더 잘 이해하려면 어떻게 대화하면 좋을까요?",
        ]

    elif context == "report":
        prompts = [
            "이번 검사 결과를 쉽게 설명해 주세요.",
            "함께할 활동을 추천해주세요.",
            "지난 검사와 비교하면 어떤가요?",
            "아이에게 어떤 말로 도와주면 좋을까요?",
        ]

    else:
        prompts = [
            "HTP 검사가 뭔가요?",
            "아이가 그림을 잘 안 그리려고 해요.",
            "요즘 아이가 부쩍 짜증을 내요.",
            "아이와 대화를 시작하는 방법을 알려주세요.",
        ]

    return {
        "context": context,
        "htp_test_id": htp_test_id,
        "prompts": prompts,
    }