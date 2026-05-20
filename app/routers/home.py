from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.child import Child
from app.models.htp_test import HtpTest
from app.models.user import User

router = APIRouter()


@router.get("/summary", summary="홈 화면 요약 조회")
def get_home_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 가장 최근 자녀
    child = (
        db.query(Child)
        .filter(Child.user_id == current_user.id)
        .order_by(Child.created_at.desc())
        .first()
    )

    if child is None:
        return {
            "child_id": None,
            "child_name": None,
            "days_since_last_test": None,
            "test_count": 0,
            "change_summary": None,
            "test_cta": "자녀를 등록하고 첫 검사를 진행해보세요.",
            "recent_report_summary": None,
            "chatbot_summary": None,
        }

    # 완료된 검사 목록
    tests = (
        db.query(HtpTest)
        .filter(HtpTest.child_id == child.id, HtpTest.test_status == "completed")
        .order_by(HtpTest.test_date.desc())
        .all()
    )

    test_count = len(tests)
    latest_test = tests[0] if tests else None

    days_since_last_test = None
    if latest_test:
        days_since_last_test = (date.today() - latest_test.test_date.date()).days

    test_cta = None
    if latest_test is None:
        test_cta = "첫 번째 검사를 진행해보세요."
    elif days_since_last_test >= 14:
        test_cta = f"최근 검사 이후 {days_since_last_test}일이 지났어요. 새로운 검사를 진행해보세요."

    return {
        "child_id": child.id,
        "child_name": child.name,
        "days_since_last_test": days_since_last_test,
        "test_count": test_count,
        "change_summary": latest_test.summary_text if latest_test else None,
        "test_cta": test_cta,
        "recent_report_summary": latest_test.report_text if latest_test else None,
        "chatbot_summary": None,
    }