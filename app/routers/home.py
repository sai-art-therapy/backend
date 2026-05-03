from fastapi import APIRouter

router = APIRouter()


@router.get("/summary", summary="홈 화면 요약 조회")
def get_home_summary():
    return {
        "child_id": 1,
        "child_name": "김OO",
        "days_since_last_test": 14,
        "test_count": 3,
        "change_summary": "최근 검사에서 불안 표현은 줄고 안정감 표현이 증가했습니다.",
        "test_cta": "최근 검사 이후 2주가 지났어요. 새로운 검사를 진행해보세요.",
        "recent_report_summary": "아이는 현재 안정감을 필요로 하는 상태로 보입니다.",
        "chatbot_summary": "최근 상담에서는 아이의 감정 표현을 기다려주는 양육 방식이 추천되었습니다."
    }