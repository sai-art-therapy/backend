from datetime import date
import json

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


def parse_report_json(report_json):
    if report_json is None:
        return {}

    if isinstance(report_json, dict):
        return report_json

    if isinstance(report_json, str):
        try:
            return json.loads(report_json)
        except Exception:
            return {}

    return {}


def safe_get_report_json(report_json, *keys):
    data = parse_report_json(report_json)

    result = data
    for key in keys:
        if not isinstance(result, dict):
            return None
        result = result.get(key)

    return result


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


def serialize_report_list_item(
    report: HtpTest,
    child: Child,
    test_order: int,
) -> dict:
    report_json = parse_report_json(report.report_json)

    return {
        "report_id": report.id,
        "test_id": report.id,
        "child_id": child.id,
        "child_name": child.name,
        "birth_year": child.birth_year,
        "age": calculate_korean_age(child.birth_year),
        "gender": child.gender,
        "test_date": report.test_date,
        "test_date_label": format_test_date_label(report.test_date),
        "test_order": test_order,
        "test_order_label": f"{test_order}번째 검사",
        "test_status": report.test_status,
        "pdi_status": report.pdi_status,
        "summary_text": report.summary_text,
        "main_emotion": report.main_emotion,
        "result_image_path": report.result_image_path,
        "analysis_mode": report_json.get("summary", {}).get("analysis_mode"),
        "pdi_used": report_json.get("summary", {}).get("pdi_used"),
        "confidence_level": report_json.get("summary", {}).get("confidence_level"),
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


def serialize_report_detail(
    report: HtpTest,
    child: Child,
    test_order: int,
) -> dict:
    report_json = parse_report_json(report.report_json)
    summary = report_json.get("summary", {})
    tabs = report_json.get("tabs", {})
    relationship_analysis = report_json.get("relationship_analysis")
    recommendations = report_json.get("recommendations") or report.recommendations_json or []
    safety_notice = report_json.get("safety_notice")

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
            "test_date_label": format_test_date_label(report.test_date),
            "test_order": test_order,
            "test_order_label": f"{test_order}번째 검사",
            "consent_agreed": report.consent_agreed,
            "drawing_time_minutes": report.drawing_time_minutes,
            "original_image_path": report.original_image_path,
            "result_image_path": report.result_image_path,
        },
        "summary": {
            "title": summary.get("title") or "HTP 그림 분석 결과",
            "one_line_summary": summary.get("one_line_summary") or report.summary_text,
            "summary_text": report.summary_text,
            "main_emotion": report.main_emotion or summary.get("main_emotion"),
            "risk_level": summary.get("risk_level"),
            "analysis_mode": summary.get("analysis_mode"),
            "pdi_used": summary.get("pdi_used"),
            "confidence_level": summary.get("confidence_level"),
            "disclaimer": summary.get("disclaimer"),
        },
        "tabs": {
            "house": tabs.get("house"),
            "tree": tabs.get("tree"),
            "person": tabs.get("person"),
        },
        "relationship_analysis": relationship_analysis,
        "recommendations": recommendations,
        "safety_notice": safety_notice,
        "images": {
            "original_image_path": report.original_image_path,
            "result_image_path": report.result_image_path,
        },
        "analysis": {
            "yolo_result_json": report.yolo_result_json,
            "visual_features_json": report.visual_features_json,
            "pdi_summary_json": report.pdi_summary_json,
        },
        "raw_report": {
            "report_text": report.report_text,
            "report_json": report_json,
        },
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


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

    response = []

    order_map_cache: dict[int, dict[int, int]] = {}

    for report, child in reports:
        if child.id not in order_map_cache:
            order_map_cache[child.id] = get_test_order_map(
                db=db,
                user_id=current_user.id,
                child_id=child.id,
            )

        test_order = order_map_cache[child.id].get(report.id, 1)

        response.append(
            serialize_report_list_item(
                report=report,
                child=child,
                test_order=test_order,
            )
        )

    return response


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

    test_order_map = get_test_order_map(
        db=db,
        user_id=current_user.id,
        child_id=child.id,
    )

    test_order = test_order_map.get(report.id, 1)

    return serialize_report_detail(
        report=report,
        child=child,
        test_order=test_order,
    )