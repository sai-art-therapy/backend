from datetime import datetime
from pathlib import Path
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.child import Child
from app.models.htp_pdi import HtpPdiInteraction
from app.models.htp_test import HtpTest
from app.services.htp_analysis_service import (
    get_pdi_choice_payload,
)
from app.services.htp_rag_service import search_htp_knowledge_for_report
from app.services.htp_report_service import (
    apply_report_to_test,
    generate_htp_report,
)
from app.services.pdi_service import (
    create_pdi_questions,
    format_pdi_questions,
    save_pdi_answers as save_pdi_answers_service,
    skip_pdi as skip_pdi_service,
)
from app.services.yolo_service import analyze_htp_image_with_yolo

router = APIRouter()

# TODO: 로그인/JWT 구현 후 실제 로그인 사용자 ID로 교체
TEST_USER_ID = 1

UPLOAD_ROOT = Path("uploads")
HTP_ORIGINAL_DIR = UPLOAD_ROOT / "htp" / "original"
HTP_RESULT_DIR = UPLOAD_ROOT / "htp" / "result"


class TestCreateRequest(BaseModel):
    child_id: int
    consent_agreed: bool
    test_type: str = "HTP"


class PdiAnswerItem(BaseModel):
    question_id: int
    answer_text: str


class PdiAnswerSaveRequest(BaseModel):
    answers: List[PdiAnswerItem]


def get_test_or_404(test_id: int, db: Session) -> HtpTest:
    htp_test = (
        db.query(HtpTest)
        .filter(
            HtpTest.id == test_id,
            HtpTest.user_id == TEST_USER_ID,
        )
        .first()
    )

    if htp_test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="검사 정보를 찾을 수 없습니다.",
        )

    return htp_test


def apply_image_analysis_result_to_test(
    htp_test: HtpTest,
    analysis_result: dict,
) -> None:
    """YOLO/OpenCV 분석 결과를 HTP 검사 객체에 반영한다."""
    htp_test.test_status = "pdi_choice_pending"
    htp_test.pdi_status = "not_started"
    htp_test.result_image_path = analysis_result["result_image_path"]
    htp_test.yolo_result_json = analysis_result["yolo_result_json"]
    htp_test.visual_features_json = analysis_result["visual_features_json"]

    # 이전 리포트가 남아있을 수 있으므로 초기화
    htp_test.summary_text = None
    htp_test.main_emotion = None
    htp_test.report_text = None
    htp_test.report_json = None
    htp_test.recommendations_json = None
    htp_test.pdi_summary_json = None


def build_image_analysis_response(
    htp_test: HtpTest,
    analysis_result: dict,
) -> dict:
    return {
        "test_id": htp_test.id,
        "test_status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "result_image_path": htp_test.result_image_path,
        "result_image_paths": analysis_result.get(
            "result_image_paths",
            htp_test.yolo_result_json.get("result_image_paths", {})
            if htp_test.yolo_result_json
            else {},
        ),
        "yolo_result_json": htp_test.yolo_result_json,
        "visual_features_json": htp_test.visual_features_json,
        "display_detections": analysis_result["display_detections"],
        "pdi_choice": get_pdi_choice_payload(),
        "message": "이미지 분석이 완료되었습니다. PDI 진행 여부를 선택해주세요.",
    }


@router.post("", summary="검사 시작", status_code=status.HTTP_201_CREATED)
def create_test(request: TestCreateRequest, db: Session = Depends(get_db)):
    if not request.consent_agreed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미지 분석 목적 사용 동의가 필요합니다.",
        )

    child = (
        db.query(Child)
        .filter(
            Child.id == request.child_id,
            Child.user_id == TEST_USER_ID,
        )
        .first()
    )

    if child is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="자녀 정보를 찾을 수 없습니다.",
        )

    htp_test = HtpTest(
        user_id=TEST_USER_ID,
        child_id=request.child_id,
        test_status="created",
        test_date=datetime.utcnow(),
        consent_agreed=True,
        consent_agreed_at=datetime.utcnow(),
        pdi_status="not_started",
    )

    db.add(htp_test)
    db.commit()
    db.refresh(htp_test)

    return {
        "test_id": htp_test.id,
        "child_id": htp_test.child_id,
        "test_status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "consent_agreed": htp_test.consent_agreed,
        "created_at": htp_test.created_at,
        "message": "검사가 시작되었습니다.",
    }


@router.post("/{test_id}/image", summary="그림 이미지 업로드")
def upload_test_image(
    test_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    htp_test = get_test_or_404(test_id, db)

    HTP_ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)

    original_filename = file.filename or "uploaded_image"
    file_ext = Path(original_filename).suffix
    saved_filename = f"test_{test_id}_{uuid4().hex}{file_ext}"
    saved_path = HTP_ORIGINAL_DIR / saved_filename

    with saved_path.open("wb") as buffer:
        buffer.write(file.file.read())

    htp_test.original_image_path = str(saved_path)
    htp_test.test_status = "image_uploaded"

    db.commit()
    db.refresh(htp_test)

    return {
        "test_id": htp_test.id,
        "filename": original_filename,
        "saved_path": htp_test.original_image_path,
        "test_status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "message": "이미지 업로드 완료",
    }


@router.post("/{test_id}/analyze", summary="HTP 이미지 분석 및 PDI 선택 대기")
def analyze_test_image(test_id: int, db: Session = Depends(get_db)):
    htp_test = get_test_or_404(test_id, db)

    if not htp_test.original_image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="분석할 이미지가 업로드되지 않았습니다.",
        )

    HTP_RESULT_DIR.mkdir(parents=True, exist_ok=True)

    analysis_result = analyze_htp_image_with_yolo(htp_test.original_image_path)

    apply_image_analysis_result_to_test(
        htp_test=htp_test,
        analysis_result=analysis_result,
    )

    db.commit()
    db.refresh(htp_test)

    return build_image_analysis_response(
        htp_test=htp_test,
        analysis_result=analysis_result,
    )


@router.post("/{test_id}/analyze-yolo", summary="YOLO 기반 HTP 이미지 분석 테스트")
def analyze_test_image_yolo(test_id: int, db: Session = Depends(get_db)):
    """Swagger에서 YOLO 연결 상태를 명확히 테스트하기 위한 endpoint.

    실제 흐름에서는 /tests/{test_id}/analyze를 사용해도 된다.
    """
    htp_test = get_test_or_404(test_id, db)

    if not htp_test.original_image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="분석할 이미지가 업로드되지 않았습니다.",
        )

    HTP_RESULT_DIR.mkdir(parents=True, exist_ok=True)

    analysis_result = analyze_htp_image_with_yolo(htp_test.original_image_path)

    apply_image_analysis_result_to_test(
        htp_test=htp_test,
        analysis_result=analysis_result,
    )

    db.commit()
    db.refresh(htp_test)

    return build_image_analysis_response(
        htp_test=htp_test,
        analysis_result=analysis_result,
    )


@router.post("/{test_id}/pdi/start", summary="PDI 질문 생성")
def start_pdi(test_id: int, db: Session = Depends(get_db)):
    htp_test = get_test_or_404(test_id, db)

    if htp_test.test_status != "pdi_choice_pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDI를 시작할 수 있는 상태가 아닙니다.",
        )

    interactions = create_pdi_questions(htp_test=htp_test, db=db)

    db.commit()

    for interaction in interactions:
        db.refresh(interaction)
    db.refresh(htp_test)

    return {
        "test_id": htp_test.id,
        "test_status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "guide_message": "아이의 답변을 고치거나 해석하지 말고, 가능한 한 아이가 말한 표현 그대로 입력해주세요.",
        "questions": format_pdi_questions(interactions),
    }


@router.post("/{test_id}/pdi/answers", summary="PDI 답변 저장")
def save_pdi_answers(
    test_id: int,
    request: PdiAnswerSaveRequest,
    db: Session = Depends(get_db),
):
    htp_test = get_test_or_404(test_id, db)

    if htp_test.test_status not in ["waiting_pdi_answers", "followup_needed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDI 답변을 저장할 수 있는 상태가 아닙니다.",
        )

    result = save_pdi_answers_service(
        htp_test=htp_test,
        answers=request.answers,
        db=db,
    )

    if not result["ok"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"존재하지 않는 질문 ID가 있습니다: {result['missing_ids']}",
        )

    db.commit()
    db.refresh(htp_test)

    return {
        "test_id": htp_test.id,
        "test_status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "saved_count": result["saved_count"],
        "need_followup": result["need_followup"],
        "followup_questions": result["followup_questions"],
        "message": "PDI 답변이 저장되었습니다. 리포트를 생성할 수 있습니다.",
    }


@router.post("/{test_id}/pdi/skip", summary="PDI 건너뛰기")
def skip_pdi(test_id: int, db: Session = Depends(get_db)):
    htp_test = get_test_or_404(test_id, db)

    if htp_test.test_status != "pdi_choice_pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDI를 건너뛸 수 있는 상태가 아닙니다.",
        )

    skip_pdi_service(htp_test)

    db.commit()
    db.refresh(htp_test)

    return {
        "test_id": htp_test.id,
        "test_status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "message": "PDI를 건너뛰었습니다. 리포트를 생성할 수 있습니다.",
    }


@router.post("/{test_id}/generate-report", summary="HTP 최종 리포트 생성")
def generate_report(test_id: int, db: Session = Depends(get_db)):
    htp_test = get_test_or_404(test_id, db)

    if htp_test.test_status != "ready_to_generate_report":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="리포트를 생성할 수 있는 상태가 아닙니다.",
        )

    if not htp_test.yolo_result_json or not htp_test.visual_features_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미지 분석 결과가 없어 리포트를 생성할 수 없습니다.",
        )

    pdi_interactions = (
        db.query(HtpPdiInteraction)
        .filter(HtpPdiInteraction.htp_test_id == htp_test.id)
        .order_by(HtpPdiInteraction.round_no, HtpPdiInteraction.sort_order)
        .all()
    )

    retrieved_knowledge = search_htp_knowledge_for_report(
        htp_test=htp_test,
        pdi_interactions=pdi_interactions,
    )

    report_json = generate_htp_report(
        htp_test=htp_test,
        pdi_interactions=pdi_interactions,
        retrieved_knowledge=retrieved_knowledge,
    )

    apply_report_to_test(
        htp_test=htp_test,
        report_json=report_json,
    )

    db.commit()
    db.refresh(htp_test)

    return {
        "test_id": htp_test.id,
        "test_status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "report_id": htp_test.id,
        "summary_text": htp_test.summary_text,
        "main_emotion": htp_test.main_emotion,
        "rag": report_json.get("rag"),
        "message": "HTP 리포트가 생성되었습니다.",
    }


@router.get("/{test_id}", summary="검사 상태 조회")
def get_test_status(test_id: int, db: Session = Depends(get_db)):
    htp_test = get_test_or_404(test_id, db)

    result_image_paths = {}
    if htp_test.yolo_result_json:
        result_image_paths = htp_test.yolo_result_json.get("result_image_paths", {})

    return {
        "test_id": htp_test.id,
        "child_id": htp_test.child_id,
        "status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "report_id": htp_test.id if htp_test.test_status == "completed" else None,
        "original_image_path": htp_test.original_image_path,
        "result_image_path": htp_test.result_image_path,
        "result_image_paths": result_image_paths,
        "yolo_result_json": htp_test.yolo_result_json,
        "visual_features_json": htp_test.visual_features_json,
        "summary_text": htp_test.summary_text,
        "main_emotion": htp_test.main_emotion,
        "created_at": htp_test.created_at,
        "updated_at": htp_test.updated_at,
    }