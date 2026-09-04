from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.htp_canvas_drawing import HtpCanvasDrawing
from app.models.htp_test import HtpTest
from app.models.user import User
from app.schemas.tests import CanvasDrawingUploadResponse
from app.services.canvas_drawing_service import (
    CanvasDrawingValidationError,
    canvas_payload_to_dict,
    parse_and_validate_canvas_drawing,
)

router = APIRouter()

HTP_ORIGINAL_DIR = Path("uploads") / "htp" / "original"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
ALLOWED_IMAGE_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}
REPLACEABLE_TEST_STATUSES = {"created", "image_uploaded", "analysis_failed"}


def _get_test_or_404(test_id: int, user_id: int, db: Session) -> HtpTest:
    htp_test = (
        db.query(HtpTest)
        .filter(HtpTest.id == test_id, HtpTest.user_id == user_id)
        .first()
    )
    if htp_test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="검사 정보를 찾을 수 없습니다.",
        )
    return htp_test


def _validate_rendered_image(image_bytes: bytes) -> tuple[str, int, int]:
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "empty_image", "message": "그림 이미지가 비어 있습니다."},
        )
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "image_too_large",
                "message": f"그림 이미지는 {MAX_IMAGE_BYTES // (1024 * 1024)}MB 이하여야 합니다.",
            },
        )

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = image.format
            width, height = image.size
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail={
                        "code": "unsupported_image_format",
                        "message": "PNG, JPEG, WEBP 이미지만 업로드할 수 있습니다.",
                    },
                )
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "invalid_image_dimensions",
                        "message": "이미지 크기가 올바르지 않거나 허용 범위를 초과했습니다.",
                    },
                )
            image.verify()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_image",
                "message": "읽을 수 없는 이미지 파일입니다.",
            },
        ) from exc

    return ALLOWED_IMAGE_FORMATS[image_format], width, height


def _rounded_drawing_minutes(duration_ms: int) -> int:
    return max(1, int((duration_ms + 30_000) // 60_000))


@router.post(
    "/{test_id}/drawing",
    summary="앱에서 직접 그린 HTP 그림 업로드",
    response_model=CanvasDrawingUploadResponse,
)
async def upload_canvas_drawing(
    test_id: int,
    drawing_data: str = Form(
        ...,
        description=(
            "캔버스 크기, 전체 소요 시간, stroke별 좌표/시간/실측 필압을 담은 "
            "JSON 문자열"
        ),
    ),
    file: UploadFile = File(
        ...,
        description="캔버스를 PNG, JPEG 또는 WEBP로 내보낸 이미지",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    htp_test = _get_test_or_404(test_id, current_user.id, db)
    if htp_test.test_status not in REPLACEABLE_TEST_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "drawing_not_replaceable",
                "message": "이미지 분석이 진행된 검사의 그림은 교체할 수 없습니다.",
            },
        )

    try:
        payload, drawing_stats = parse_and_validate_canvas_drawing(drawing_data)
    except CanvasDrawingValidationError as exc:
        raise HTTPException(
            status_code=(
                413
                if exc.code == "drawing_data_too_large"
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    image_bytes = await file.read(MAX_IMAGE_BYTES + 1)
    file_ext, rendered_width, rendered_height = _validate_rendered_image(image_bytes)

    HTP_ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
    original_filename = file.filename or f"canvas_drawing{file_ext}"
    saved_filename = f"test_{test_id}_canvas_{uuid4().hex}{file_ext}"
    saved_path = HTP_ORIGINAL_DIR / saved_filename
    saved_path.write_bytes(image_bytes)

    try:
        canvas_drawing = (
            db.query(HtpCanvasDrawing)
            .filter(HtpCanvasDrawing.htp_test_id == htp_test.id)
            .first()
        )
        if canvas_drawing is None:
            canvas_drawing = HtpCanvasDrawing(htp_test_id=htp_test.id)
            db.add(canvas_drawing)

        canvas_drawing.schema_version = payload.schema_version
        canvas_drawing.canvas_width = payload.canvas.width
        canvas_drawing.canvas_height = payload.canvas.height
        canvas_drawing.rendered_width = rendered_width
        canvas_drawing.rendered_height = rendered_height
        canvas_drawing.duration_ms = payload.duration_ms
        canvas_drawing.stroke_count = drawing_stats.stroke_count
        canvas_drawing.point_count = drawing_stats.point_count
        canvas_drawing.pressure_point_count = drawing_stats.pressure_point_count
        canvas_drawing.has_measured_pressure = drawing_stats.pressure_available
        canvas_drawing.drawing_data_json = canvas_payload_to_dict(payload)
        canvas_drawing.rendered_image_path = str(saved_path)

        htp_test.original_image_path = str(saved_path)
        htp_test.test_status = "image_uploaded"
        htp_test.pdi_status = "not_started"
        htp_test.drawing_time_minutes = _rounded_drawing_minutes(payload.duration_ms)

        # Re-uploading after an analysis failure must never retain stale AI output.
        htp_test.result_image_path = None
        htp_test.yolo_result_json = None
        htp_test.visual_features_json = None
        htp_test.pdi_summary_json = None
        htp_test.summary_text = None
        htp_test.main_emotion = None
        htp_test.report_text = None
        htp_test.report_json = None
        htp_test.recommendations_json = None

        db.commit()
        db.refresh(canvas_drawing)
        db.refresh(htp_test)
    except Exception:
        db.rollback()
        saved_path.unlink(missing_ok=True)
        raise

    return {
        "test_id": htp_test.id,
        "drawing_id": canvas_drawing.id,
        "filename": original_filename,
        "saved_path": htp_test.original_image_path,
        "input_type": "canvas",
        "test_status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "next_action": "analyze_image",
        "duration_ms": canvas_drawing.duration_ms,
        "drawing_time_minutes": htp_test.drawing_time_minutes,
        "stroke_count": canvas_drawing.stroke_count,
        "point_count": canvas_drawing.point_count,
        "pressure_point_count": canvas_drawing.pressure_point_count,
        "pressure_available": canvas_drawing.has_measured_pressure,
        "message": "직접 그린 그림과 그리기 데이터가 저장되었습니다.",
    }
