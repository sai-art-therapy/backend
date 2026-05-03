from fastapi import APIRouter

router = APIRouter()


@router.get("", summary="검사 리포트 목록 조회")
def get_reports():
    return [
        {
            "report_id": 1,
            "child_id": 1,
            "child_name": "김OO",
            "test_date": "2026-05-03",
            "summary": "안정감을 필요로 하는 상태로 보입니다.",
            "main_emotion": "anxiety"
        }
    ]


@router.get("/{report_id}", summary="검사 리포트 상세 조회")
def get_report_detail(report_id: int):
    return {
        "report_id": report_id,
        "child_id": 1,
        "test_date": "2026-05-03",
        "summary": "아이는 현재 안정감을 필요로 하는 상태로 보입니다.",
        "drawing_analysis": {
            "house": "집의 크기와 위치에서 안정감 관련 특징이 관찰되었습니다.",
            "tree": "나무의 형태에서 정서 표현 특징이 관찰되었습니다.",
            "person": "사람 그림에서 자기표현 관련 특징이 관찰되었습니다."
        },
        "parenting_guide": "아이의 감정을 먼저 공감해주고 편안한 대화를 유도해주세요."
    }