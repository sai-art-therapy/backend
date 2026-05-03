from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class AccountUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None


class NotificationUpdateRequest(BaseModel):
    report_notification: bool
    chat_notification: bool


@router.get("", summary="마이페이지 정보 조회")
def get_mypage():
    return {
        "user_id": 1,
        "name": "김민하",
        "email": "minha@example.com",
        "child_count": 1,
        "notification": {
            "report_notification": True,
            "chat_notification": True
        }
    }


@router.patch("/account", summary="계정 정보 수정")
def update_account(request: AccountUpdateRequest):
    return {
        "message": "계정 정보 수정 완료"
    }


@router.patch("/notifications", summary="알림 설정 수정")
def update_notifications(request: NotificationUpdateRequest):
    return {
        "report_notification": request.report_notification,
        "chat_notification": request.chat_notification,
        "message": "알림 설정 수정 완료"
    }