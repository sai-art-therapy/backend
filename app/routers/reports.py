from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.child import Child
from app.models.htp_test import HtpTest
from app.models.user import User

router = APIRouter()


def calculate_korean_age(birth_year: int) -> int:
    current_year = date.today().year
    return current_year - birth_year


def safe_get_report_json(report_json, *keys):
    """report_json이 dict든 str이든 안전하게 값 꺼내기."""
    import json
    if report_json is None:
        return None
    if isinstance(report_json, str):
        try:
            report_json = json.loads(report_json)
        except Exception:
            return None
    result = report_json
    for key in keys:
        if not isinstance(result, dict):
            return None
        result = result.get(key)
    return result


@router.get("", summary="검사 리포트 목록 조회")
def get_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reports = (
        db.query(HtpTest, Child)
        .join(Child, HtpTest.child_id == Child.id)
        .filter(
            HtpTest.user_id == current_user.id,
            HtpTest.test_status == "completed",
        )
        .order_by(HtpTest.test_date.desc())
        .all()
    )

    return [
        {
            "report_id": report.id,
            "test_id": report.id,
            "child_id": child.id,
            "child_name": child.name,
            "birth_year": child.birth_year,
            "age": calculate_korean_age(child.birth_year),
            "gender": child.gender,
            "test_date": report.test_date,
            "test_status": report.test_status,
            "pdi_status": report.pdi_status,
            "summary_text": report.summary_text,
            "main_emotion": report.main_emotion,
            "result_image_path": report.result_image_path,
            "analysis_mode": safe_get_report_json(report.report_json, "summary", "analysis_mode"),
            "pdi_used": safe_get_report_json(report.report_json, "summary", "pdi_used"),
            "confidence_level": safe_get_report_json(report.report_json, "summary", "confidence_level"),
            "created_at": report.created_at,
            "updated_at": report.updated_at,
        }
        for report, child in reports
    ]


@router.get("/{report_id}", summary="검사 리포트 상세 조회")
def get_report_detail(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = (
        db.query(HtpTest, Child)
        .join(Child, HtpTest.child_id == Child.id)
        .filter(
            HtpTest.id == report_id,
            HtpTest.user_id == current_user.id,
        )
        .first()
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리포트를 찾을 수 없습니다.",
        )

    report, child = result

    if report.test_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="아직 리포트 생성이 완료되지 않은 검사입니다.",
        )

    return {
        "report_id": report.id,
        "test_id": report.id,
        "child": {
            "child_id": child.id,
            "name": child.name,
            "birth_year": child.birth_year,
            "age": calculate_korean_age(child.birth_year),
            "gender": child.gender,
        },
        "test": {
            "test_status": report.test_status,
            "pdi_status": report.pdi_status,
            "test_date": report.test_date,
            "consent_agreed": report.consent_agreed,
            "original_image_path": report.original_image_path,
            "result_image_path": report.result_image_path,
        },
        "analysis": {
            "yolo_result_json": report.yolo_result_json,
            "visual_features_json": report.visual_features_json,
            "pdi_summary_json": report.pdi_summary_json,
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