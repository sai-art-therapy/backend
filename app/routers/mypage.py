from datetime import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.child import Child
from app.models.user import User

router = APIRouter()


class ProfileUpdateRequest(BaseModel):
    nickname: str


class AccountUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None


class NotificationUpdateRequest(BaseModel):
    report_notification: bool
    chat_notification: bool


def validate_nickname(nickname: str) -> None:
    """
    닉네임 조건:
    - 2~10자
    - 한글/영어/숫자만 허용
    """
    if not re.fullmatch(r"[가-힣a-zA-Z0-9]{2,10}", nickname):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="닉네임은 2~10자 한글/영어/숫자만 가능합니다.",
        )


def format_joined_date(created_at: datetime) -> str:
    return created_at.strftime("%Y-%m-%d")


def format_joined_message(created_at: datetime) -> str:
    return f"{created_at.strftime('%Y.%m.%d')}부터 그림 AI 시작했어요"


@router.get("", summary="마이페이지 정보 조회")
def get_mypage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    children = (
        db.query(Child)
        .filter(Child.user_id == current_user.id)
        .order_by(Child.created_at.desc())
        .all()
    )

    return {
        "user": {
            "user_id": current_user.id,
            "nickname": current_user.nickname or current_user.name,
            "email": current_user.email,
            "profile_image_url": None,
        },
        "summary": {
            "joined_date": format_joined_date(current_user.created_at),
            "joined_message": format_joined_message(current_user.created_at),
        },
        "children": [
            {
                "child_id": child.id,
                "name": child.name,
                "birth_year": child.birth_year,
                "gender": child.gender,
                "created_at": child.created_at,
                "updated_at": child.updated_at,
            }
            for child in children
        ],
    }


@router.patch("/profile", summary="프로필 수정")
def update_profile(
    request: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_nickname(request.nickname)

    existing_user = (
        db.query(User)
        .filter(User.nickname == request.nickname, User.id != current_user.id)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 사용 중인 닉네임입니다.",
        )

    current_user.nickname = request.nickname
    current_user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(current_user)

    return {
        "user_id": current_user.id,
        "nickname": current_user.nickname,
        "message": "프로필 수정 완료",
    }


@router.delete("/account", summary="회원 탈퇴")
def delete_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.delete(current_user)
    db.commit()

    return {
        "message": "회원 탈퇴가 완료되었습니다.",
    }


# =========================
# 현재 프론트 화면에서는 사용하지 않는 API
# Swagger 혼동 방지를 위해 숨김 처리
# =========================

@router.patch("/account", summary="계정 정보 수정", include_in_schema=False)
def update_account(
    request: AccountUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.name is not None:
        current_user.name = request.name
    if request.email is not None:
        current_user.email = request.email

    current_user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(current_user)

    return {
        "message": "계정 정보 수정 완료",
        "name": current_user.name,
        "email": current_user.email,
    }


@router.patch("/notifications", summary="알림 설정 수정", include_in_schema=False)
def update_notifications(
    request: NotificationUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    return {
        "report_notification": request.report_notification,
        "chat_notification": request.chat_notification,
        "message": "알림 설정 수정 완료",
    }
