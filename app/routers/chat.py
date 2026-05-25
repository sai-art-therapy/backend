from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.child import Child
from app.models.htp_test import HtpTest
from app.models.user import User
from app.services.rag_service import answer_with_rag

router = APIRouter()

CHAT_HISTORY_LIMIT = 8


class ChatSessionCreateRequest(BaseModel):
    child_id: Optional[int] = None
    htp_test_id: Optional[int] = None
    title: Optional[str] = None


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    report_id: Optional[int] = None


def get_chat_mode(session: ChatSession) -> str:
    return "report_based" if session.htp_test_id is not None else "general"


def format_test_date_label(test_date) -> str:
    return f"{test_date.month}월 {test_date.day}일"


def get_test_order_map(
    db: Session,
    user_id: int,
    child_id: int,
) -> dict[int, int]:
    """
    해당 자녀의 완료된 검사를 오래된 순서대로 1번째, 2번째, 3번째 검사로 계산한다.
    """
    tests = (
        db.query(HtpTest)
        .filter(
            HtpTest.user_id == user_id,
            HtpTest.child_id == child_id,
            HtpTest.test_status == "completed",
        )
        .order_by(HtpTest.test_date.asc())
        .all()
    )

    return {test.id: index + 1 for index, test in enumerate(tests)}


def get_child_payload(
    db: Session,
    child_id: int | None,
    user_id: int,
) -> dict | None:
    if child_id is None:
        return None

    child = (
        db.query(Child)
        .filter(Child.id == child_id, Child.user_id == user_id)
        .first()
    )

    if child is None:
        return None

    return {
        "child_id": child.id,
        "name": child.name,
    }


def get_linked_report_payload(
    db: Session,
    htp_test_id: int | None,
    user_id: int,
) -> dict | None:
    if htp_test_id is None:
        return None

    report = (
        db.query(HtpTest)
        .filter(
            HtpTest.id == htp_test_id,
            HtpTest.user_id == user_id,
        )
        .first()
    )

    if report is None:
        return None

    test_order_map = get_test_order_map(
        db=db,
        user_id=user_id,
        child_id=report.child_id,
    )
    test_order = test_order_map.get(report.id, 1)

    return {
        "report_id": report.id,
        "test_id": report.id,
        "child_id": report.child_id,
        "test_date": report.test_date.date().isoformat(),
        "test_date_label": format_test_date_label(report.test_date),
        "test_order": test_order,
        "test_order_label": f"{test_order}번째 검사",
        "summary_text": report.summary_text,
        "main_emotion": report.main_emotion,
    }


def validate_child_ownership(
    db: Session,
    child_id: int | None,
    user_id: int,
) -> None:
    if child_id is None:
        return

    child = (
        db.query(Child)
        .filter(Child.id == child_id, Child.user_id == user_id)
        .first()
    )

    if child is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="자녀 정보를 찾을 수 없습니다.",
        )


def validate_report_ownership(
    db: Session,
    htp_test_id: int | None,
    user_id: int,
) -> HtpTest | None:
    if htp_test_id is None:
        return None

    htp_test = (
        db.query(HtpTest)
        .filter(
            HtpTest.id == htp_test_id,
            HtpTest.user_id == user_id,
        )
        .first()
    )

    if htp_test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="기반 리포트를 찾을 수 없습니다.",
        )

    if htp_test.test_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="완료된 리포트만 상담에 연결할 수 있습니다.",
        )

    return htp_test


def build_chat_history(
    db: Session,
    session_id: int,
    before_message_id: int,
    limit: int = CHAT_HISTORY_LIMIT,
) -> list[dict]:
    recent_messages = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session_id,
            ChatMessage.id < before_message_id,
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )

    recent_messages.reverse()

    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in recent_messages
    ]


def serialize_message(message: ChatMessage) -> dict:
    return {
        "message_id": message.id,
        "role": message.role,
        "content": message.content,
        "sources": message.sources_json,
        "created_at": message.created_at,
    }


def serialize_session(
    session: ChatSession,
    db: Session,
    user_id: int,
    include_messages: bool = False,
) -> dict:
    child_payload = get_child_payload(
        db=db,
        child_id=session.child_id,
        user_id=user_id,
    )

    linked_report_payload = get_linked_report_payload(
        db=db,
        htp_test_id=session.htp_test_id,
        user_id=user_id,
    )

    last_message = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .first()
    )

    message_count = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .count()
    )

    payload = {
        "session_id": session.id,
        "chat_mode": get_chat_mode(session),
        "child": child_payload,
        "linked_report": linked_report_payload,
        "htp_test_id": session.htp_test_id,
        "title": session.title,
        "last_message": last_message.content if last_message else None,
        "message_count": message_count,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }

    if include_messages:
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

        payload["messages"] = [
            serialize_message(message)
            for message in messages
        ]

    return payload


@router.post("/sessions", summary="새 채팅 시작", status_code=status.HTTP_201_CREATED)
def create_chat_session(
    request: ChatSessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_child_ownership(
        db=db,
        child_id=request.child_id,
        user_id=current_user.id,
    )

    htp_test = validate_report_ownership(
        db=db,
        htp_test_id=request.htp_test_id,
        user_id=current_user.id,
    )

    child_id = request.child_id

    if child_id is None and htp_test is not None:
        child_id = htp_test.child_id

    title = request.title
    if title is None:
        title = "리포트 기반 상담" if request.htp_test_id is not None else "일반 육아 상담"

    chat_session = ChatSession(
        user_id=current_user.id,
        child_id=child_id,
        htp_test_id=request.htp_test_id,
        title=title,
    )

    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    response = serialize_session(
        session=chat_session,
        db=db,
        user_id=current_user.id,
    )
    response["message"] = "새 상담이 시작되었습니다."

    return response


@router.get("/sessions", summary="이전 상담 목록 조회")
def get_chat_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    return [
        serialize_session(
            session=session,
            db=db,
            user_id=current_user.id,
        )
        for session in sessions
    ]


@router.get("/sessions/{session_id}", summary="상담 내용 불러오기")
def get_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chat_session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
        .first()
    )

    if chat_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="상담방을 찾을 수 없습니다.",
        )

    return serialize_session(
        session=chat_session,
        db=db,
        user_id=current_user.id,
        include_messages=True,
    )


@router.post("/sessions/{session_id}/messages", summary="챗봇 메시지 전송")
def send_chat_message(
    session_id: int,
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chat_session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
        .first()
    )

    if chat_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="상담방을 찾을 수 없습니다.",
        )

    message_text = request.message.strip()

    if not message_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="메시지를 입력해주세요.",
        )

    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=message_text,
        sources_json=None,
    )

    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    chat_history = build_chat_history(
        db=db,
        session_id=session_id,
        before_message_id=user_message.id,
        limit=CHAT_HISTORY_LIMIT,
    )

    report_id = request.report_id
    if report_id is None and chat_session.htp_test_id is not None:
        report_id = chat_session.htp_test_id

    result = answer_with_rag(
        message=message_text,
        db=db,
        report_id=report_id,
        user_id=current_user.id,
        chat_history=chat_history,
    )

    assistant_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=result["answer"],
        sources_json=result["sources"],
    )

    db.add(assistant_message)

    if chat_session.title in ["새 상담", "일반 육아 상담", "리포트 기반 상담"]:
        chat_session.title = message_text[:30]

    chat_session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    db.refresh(chat_session)

    return {
        "session": serialize_session(
            session=chat_session,
            db=db,
            user_id=current_user.id,
        ),
        "user_message": serialize_message(user_message),
        "assistant_message": serialize_message(assistant_message),
        "answer": result["answer"],
        "sources": result["sources"],
        "safety_notice": result["safety_notice"],
        "used_context": {
            "history_message_count": len(chat_history),
            "htp_test_id": report_id,
            "rag_source_count": len(result["sources"]),
        },
    }


@router.get("/suggested-prompts", summary="추천 질문 조회")
def get_suggested_prompts(
    context: str = Query("general", description="home, report, general 중 하나"),
    htp_test_id: Optional[int] = None,
):
    # TODO:
    # 현재 추천 질문은 프론트 화면 연결을 위한 임시 하드코딩 문구이다.
    # 추후 htp_test_id가 전달되면 해당 리포트의 report_json, summary_text,
    # main_emotion, recommendations_json, pdi_summary_json 등을 기반으로
    # 실제 검사 결과에 맞는 추천 질문을 동적으로 생성한다.

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