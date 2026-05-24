from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.child import Child
from app.models.htp_test import HtpTest
from app.models.user import User

router = APIRouter()


def format_days_ago(test_date) -> tuple[int, str]:
    days_ago = (date.today() - test_date.date()).days

    if days_ago == 0:
        return days_ago, "오늘"
    if days_ago == 1:
        return days_ago, "1일 전"

    return days_ago, f"{days_ago}일 전"


def format_test_date_label(test_date) -> str:
    return f"{test_date.month}월 {test_date.day}일"


def build_test_order_map(tests_asc: list[HtpTest]) -> dict[int, int]:
    """
    오래된 검사부터 1번째, 2번째, 3번째 검사로 계산한다.
    """
    return {test.id: index + 1 for index, test in enumerate(tests_asc)}


def build_default_test_card() -> dict:
    return {
        "title": "그림 속 마음 이야기",
        "subtitle": "HTP 검사로 아이의 마음을 들여다봐요",
        "button_text": "검사 시작하기",
        "steps": [
            "그림 그리기",
            "사진 업로드",
            "AI 분석",
            "결과 확인",
        ],
    }


def build_general_chatbot_card() -> dict:
    return {
        "mode": "general",
        "title": "육아 고민, AI에게 물어보세요",
        "description": "검사를 하지 않아도 괜찮아요. 아이에 대한 궁금증을 편하게 이야기해 보세요.",
        "child": None,
        "latest_test": None,
        "recommended_questions": [
            "HTP 검사가 뭔가요?",
            "아이가 그림을 잘 안 그리려고 해요",
            "요즘 아이가 부쩍 짜증을 내요",
        ],
        "button_text": "AI 챗봇 바로가기",
    }


def build_report_chatbot_card(
    child: Child,
    latest_test: HtpTest,
    test_order: int,
) -> dict:
    days_ago, days_ago_label = format_days_ago(latest_test.test_date)

    # TODO:
    # 현재 recommended_questions는 프론트 화면 연결을 위한 임시 문구이다.
    # 추후에는 latest_test.report_json, summary_text, main_emotion,
    # recommendations_json, pdi_summary_json 등을 기반으로
    # 실제 검사 결과에서 드러난 특징에 맞는 질문을 생성하도록 수정한다.
    #
    # 예:
    # - report_json에서 "자아상 약화" 관련 특징이 감지된 경우
    #   → "{child.name}의 자아상이 왜 약한 걸까요?"
    # - main_emotion이 "불안"인 경우
    #   → "{child.name}의 불안을 줄이려면 어떻게 도와줘야 할까요?"
    # - recommendations_json에 활동 제안이 있는 경우
    #   → "다음에는 어떤 활동을 함께해볼까요?"

    return {
        "mode": "with_report",
        "title": "최근 결과에 대해 더 알아볼까요?",
        "description": None,
        "child": {
            "child_id": child.id,
            "name": child.name,
        },
        "latest_test": {
            "test_id": latest_test.id,
            "days_ago": days_ago,
            "days_ago_label": days_ago_label,
            "test_order": test_order,
            "test_order_label": f"{test_order}번째 검사",
        },
        "recommended_questions": [
            f"{child.name}의 자아상이 왜 약한 걸까요?",
            "자신감을 키워주려면 어떻게 해야 할까요?",
            "다음에는 어떤 활동을 함께해볼까요?",
        ],
        "button_text": "AI 챗봇 바로가기",
    }


def build_recent_report_item(
    test: HtpTest,
    child: Child,
    test_order: int,
) -> dict:
    return {
        "test_id": test.id,
        "child_id": child.id,
        "child_name": child.name,
        "test_date": test.test_date.date().isoformat(),
        "test_date_label": format_test_date_label(test.test_date),
        "test_order": test_order,
        "test_order_label": f"{test_order}번째 검사",
        "main_emotion": test.main_emotion,
    }


@router.get("", summary="홈 화면 조회")
def get_home(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    child = (
        db.query(Child)
        .filter(Child.user_id == current_user.id)
        .order_by(Child.created_at.desc())
        .first()
    )

    # 아직 자녀가 없는 경우
    if child is None:
        return {
            "headline": "우리 아이, 요즘 어떤 마음일까요?",
            "child": None,
            "test_card": build_default_test_card(),
            "chatbot_card": build_general_chatbot_card(),
            "recent_reports_card": {
                "title": "최근 검사 리포트를 확인해보세요",
                "reports": [],
            },
        }

    # 해당 자녀의 완료된 검사만 조회
    completed_tests_desc = (
        db.query(HtpTest)
        .filter(
            HtpTest.user_id == current_user.id,
            HtpTest.child_id == child.id,
            HtpTest.test_status == "completed",
        )
        .order_by(HtpTest.test_date.desc())
        .all()
    )

    completed_tests_asc = list(reversed(completed_tests_desc))
    test_order_map = build_test_order_map(completed_tests_asc)

    latest_test = completed_tests_desc[0] if completed_tests_desc else None

    if latest_test is None:
        chatbot_card = build_general_chatbot_card()
    else:
        chatbot_card = build_report_chatbot_card(
            child=child,
            latest_test=latest_test,
            test_order=test_order_map[latest_test.id],
        )

    recent_reports = [
        build_recent_report_item(
            test=test,
            child=child,
            test_order=test_order_map[test.id],
        )
        for test in completed_tests_desc[:2]
    ]

    return {
        "headline": "우리 아이, 요즘 어떤 마음일까요?",
        "child": {
            "child_id": child.id,
            "name": child.name,
        },
        "test_card": build_default_test_card(),
        "chatbot_card": chatbot_card,
        "recent_reports_card": {
            "title": "최근 검사 리포트를 확인해보세요",
            "reports": recent_reports,
        },
    }


# =========================
# 기존 홈 요약 API
# 프론트 신규 홈 화면에서는 GET /home 사용
# Swagger 혼동 방지를 위해 숨김 처리
# =========================

@router.get("/summary", summary="홈 화면 요약 조회", include_in_schema=False)
def get_home_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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