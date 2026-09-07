from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.child import Child
from app.models.htp_test import HtpTest
from app.models.report_share import ReportShare
from app.routers.reports import (
    REPORT_IMAGE_FIELDS,
    REPORT_IMAGE_MEDIA_TYPES,
    _resolve_report_image_path,
    calculate_korean_age,
    format_test_date_label,
    parse_report_json,
)
from app.services.report_share_service import find_active_report_share


router = APIRouter()
ReportImageKind = Literal["original", "result"]


def _extract_share_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "share" or not token.strip():
        return None
    return token.strip()


def get_current_report_share(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> ReportShare:
    token = _extract_share_token(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="공유 토큰이 필요합니다.",
            headers={"WWW-Authenticate": "Share"},
        )

    share = find_active_report_share(db, token)
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유효한 공유 링크를 찾을 수 없습니다.",
        )
    return share


def _shared_image_url(image_kind: ReportImageKind, image_path: str | None):
    if not image_path:
        return None
    return f"/shared-reports/images/{image_kind}"


def serialize_shared_report(
    report: HtpTest,
    child: Child,
    share: ReportShare,
) -> dict:
    report_json = parse_report_json(report.report_json)
    summary = report_json.get("summary", {})
    tabs = report_json.get("tabs", {})
    recommendations = (
        report_json.get("recommendations")
        or report.recommendations_json
        or []
    )

    return {
        "share": {"expires_at": share.expires_at},
        "report": {
            "child": {
                "name": child.name,
                "age": calculate_korean_age(child.birth_year),
                "gender": child.gender,
            },
            "test": {
                "test_date": report.test_date,
                "test_date_label": format_test_date_label(report.test_date),
            },
            "summary": {
                "title": summary.get("title") or "HTP 그림 분석 결과",
                "one_line_summary": summary.get("one_line_summary")
                or report.summary_text,
                "summary_text": report.summary_text,
                "main_emotion": report.main_emotion
                or summary.get("main_emotion"),
                "disclaimer": summary.get("disclaimer"),
            },
            "tabs": {
                "house": tabs.get("house"),
                "tree": tabs.get("tree"),
                "person": tabs.get("person"),
            },
            "relationship_analysis": report_json.get("relationship_analysis"),
            "recommendations": recommendations,
            "safety_notice": report_json.get("safety_notice"),
            "images": {
                "original_image_url": _shared_image_url(
                    "original", report.original_image_path
                ),
                "result_image_url": _shared_image_url(
                    "result", report.result_image_path
                ),
            },
        },
    }


@router.get("", summary="공유 리포트 조회")
def get_shared_report(
    response: Response,
    db: Session = Depends(get_db),
    share: ReportShare = Depends(get_current_report_share),
):
    result = (
        db.query(HtpTest, Child)
        .join(Child, HtpTest.child_id == Child.id)
        .filter(
            HtpTest.id == share.report_id,
            HtpTest.test_status == "completed",
        )
        .first()
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공유 리포트를 찾을 수 없습니다.",
        )

    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Vary"] = "Authorization"
    report, child = result
    return serialize_shared_report(report, child, share)


@router.get(
    "/images/{image_kind}",
    summary="공유 리포트 이미지 조회",
    response_class=FileResponse,
)
def get_shared_report_image(
    image_kind: ReportImageKind,
    db: Session = Depends(get_db),
    share: ReportShare = Depends(get_current_report_share),
):
    report = db.query(HtpTest).filter(HtpTest.id == share.report_id).first()
    if report is None or report.test_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공유 리포트를 찾을 수 없습니다.",
        )

    image_path = getattr(report, REPORT_IMAGE_FIELDS[image_kind])
    resolved_path = _resolve_report_image_path(image_path) if image_path else None
    if resolved_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리포트 이미지를 찾을 수 없습니다.",
        )

    return FileResponse(
        path=resolved_path,
        media_type=REPORT_IMAGE_MEDIA_TYPES[resolved_path.suffix.lower()],
        headers={
            "Cache-Control": "private, no-store",
            "Referrer-Policy": "no-referrer",
            "Vary": "Authorization",
            "X-Content-Type-Options": "nosniff",
        },
    )
