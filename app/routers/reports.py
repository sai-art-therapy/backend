from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.child import Child
from app.models.htp_test import HtpTest

router = APIRouter()

# TODO: 로그인/JWT 구현 후 실제 로그인 사용자 ID로 교체
TEST_USER_ID = 1


def calculate_korean_age(birth_year: int) -> int:
    current_year = date.today().year
    return current_year - birth_year


@router.get("", summary="검사 리포트 목록 조회")
def get_reports(db: Session = Depends(get_db)):
    reports = (
        db.query(HtpTest, Child)
        .join(Child, HtpTest.child_id == Child.id)
        .filter(HtpTest.user_id == TEST_USER_ID)
        .order_by(HtpTest.test_date.desc())
        .all()
    )

    return [
        {
            "report_id": report.id,
            "child_id": child.id,
            "child_name": child.name,
            "birth_year": child.birth_year,
            "age": calculate_korean_age(child.birth_year),
            "gender": child.gender,
            "test_date": report.test_date,
            "test_status": report.test_status,
            "summary": report.summary_text,
            "main_emotion": report.main_emotion,
            "result_image_path": report.result_image_path,
        }
        for report, child in reports
    ]


@router.get("/{report_id}", summary="검사 리포트 상세 조회")
def get_report_detail(report_id: int, db: Session = Depends(get_db)):
    result = (
        db.query(HtpTest, Child)
        .join(Child, HtpTest.child_id == Child.id)
        .filter(
            HtpTest.id == report_id,
            HtpTest.user_id == TEST_USER_ID,
        )
        .first()
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리포트를 찾을 수 없습니다.",
        )

    report, child = result

    return {
        "report_id": report.id,
        "child": {
            "child_id": child.id,
            "name": child.name,
            "birth_year": child.birth_year,
            "age": calculate_korean_age(child.birth_year),
            "gender": child.gender,
        },
        "test": {
            "test_status": report.test_status,
            "test_date": report.test_date,
            "consent_agreed": report.consent_agreed,
            "original_image_path": report.original_image_path,
            "result_image_path": report.result_image_path,
            "yolo_result_json": report.yolo_result_json,
        },
        "report": {
            "summary_text": report.summary_text,
            "main_emotion": report.main_emotion,
            "report_text": report.report_text,
            "report_json": report.report_json,
            "recommendations_json": report.recommendations_json,
        },
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }