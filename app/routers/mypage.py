from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.child import Child
from app.models.user import User

router = APIRouter()


class AccountUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None


class NotificationUpdateRequest(BaseModel):
    report_notification: bool
    chat_notification: bool


@router.get("", summary="마이페이지 정보 조회")
def get_mypage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    child_count = db.query(Child).filter(Child.user_id == current_user.id).count()

    return {
        "user_id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "child_count": child_count,
        "notification": {
            "report_notification": True,
            "chat_notification": True,
        },
    }


@router.patch("/account", summary="계정 정보 수정")
def update_account(
    request: AccountUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.name is not None:
        current_user.name = request.name
    if request.email is not None:
        current_user.email = request.email

    db.commit()
    db.refresh(current_user)

    return {
        "message": "계정 정보 수정 완료",
        "name": current_user.name,
        "email": current_user.email,
    }


@router.patch("/notifications", summary="알림 설정 수정")
def update_notifications(
    request: NotificationUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    return {
        "report_notification": request.report_notification,
        "chat_notification": request.chat_notification,
        "message": "알림 설정 수정 완료",
    }