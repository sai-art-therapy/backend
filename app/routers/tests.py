from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.child import Child
from app.models.htp_pdi import HtpPdiInteraction
from app.models.htp_test import HtpTest
from app.models.user import User
from app.services.htp_analysis_service import get_pdi_choice_payload
from app.services.htp_rag_service import search_htp_knowledge_for_report
from app.services.htp_report_service import apply_report_to_test, generate_htp_report
from app.services.pdi_service import (
    create_pdi_questions,
    skip_pdi as skip_pdi_service,
)
from app.services.yolo_service import analyze_htp_image_with_yolo

router = APIRouter()

UPLOAD_ROOT = Path("uploads")
HTP_ORIGINAL_DIR = UPLOAD_ROOT / "htp" / "original"
HTP_RESULT_DIR = UPLOAD_ROOT / "htp" / "result"


class TestCreateRequest(BaseModel):
    child_id: int
    consent_agreed: bool
    test_type: str = "HTP"


class PdiSingleAnswerRequest(BaseModel):
    question_id: int
    answer_text: str | None = None
    skip: bool = False
    
class PdiTimeRequest(BaseModel):
    drawing_time_minutes: int | None = None  # None이면 건너뛰기


def get_test_or_404(test_id: int, user_id: int, db: Session) -> HtpTest:
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


def apply_image_analysis_result_to_test(htp_test: HtpTest, analysis_result: dict) -> None:
    htp_test.test_status = "pdi_choice_pending"
    htp_test.pdi_status = "not_started"
    htp_test.result_image_path = analysis_result["result_image_path"]
    htp_test.yolo_result_json = analysis_result["yolo_result_json"]
    htp_test.visual_features_json = analysis_result["visual_features_json"]
    htp_test.summary_text = None
    htp_test.main_emotion = None
    htp_test.report_text = None
    htp_test.report_json = None
    htp_test.recommendations_json = None
    htp_test.pdi_summary_json = None


def build_image_analysis_response(htp_test: HtpTest, analysis_result: dict) -> dict:
    return {
        "test_id": htp_test.id,
        "test_status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "result_image_path": htp_test.result_image_path,
        "result_image_paths": analysis_result.get("result_image_paths", {}),
        "yolo_result_json": htp_test.yolo_result_json,
        "visual_features_json": htp_test.visual_features_json,
        "display_detections": analysis_result["display_detections"],
        "pdi_choice": get_pdi_choice_payload(),
        "message": "이미지 분석이 완료되었습니다. PDI 진행 여부를 선택해주세요.",
    }


@router.post("", summary="검사 시작", status_code=status.HTTP_201_CREATED)
def create_test(
    request: TestCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not request.consent_agreed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미지 분석 목적 사용 동의가 필요합니다.",
        )

    child = (
        db.query(Child)
        .filter(Child.id == request.child_id, Child.user_id == current_user.id)
        .first()
    )

    if child is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="자녀 정보를 찾을 수 없습니다.",
        )

    htp_test = HtpTest(
        user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
):
    htp_test = get_test_or_404(test_id, current_user.id, db)

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
def analyze_test_image(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    htp_test = get_test_or_404(test_id, current_user.id, db)

    if not htp_test.original_image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="분석할 이미지가 업로드되지 않았습니다.",
        )

    HTP_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    analysis_result = analyze_htp_image_with_yolo(htp_test.original_image_path)
    apply_image_analysis_result_to_test(htp_test=htp_test, analysis_result=analysis_result)

    db.commit()
    db.refresh(htp_test)

    return build_image_analysis_response(htp_test=htp_test, analysis_result=analysis_result)


@router.post("/{test_id}/pdi/time", summary="그리기 소요 시간 저장")
def save_drawing_time(
    test_id: int,
    request: PdiTimeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    htp_test = get_test_or_404(test_id, current_user.id, db)

    if htp_test.test_status != "pdi_choice_pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="소요 시간을 저장할 수 있는 상태가 아닙니다.",
        )

    htp_test.drawing_time_minutes = request.drawing_time_minutes
    db.commit()
    db.refresh(htp_test)

    return {
        "test_id": htp_test.id,
        "drawing_time_minutes": htp_test.drawing_time_minutes,
        "message": (
            f"{request.drawing_time_minutes}분으로 저장되었습니다."
            if request.drawing_time_minutes
            else "소요 시간을 건너뛰었습니다."
        ),
    }


@router.post("/{test_id}/pdi/start", summary="PDI 질문 생성")
def start_pdi(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    htp_test = get_test_or_404(test_id, current_user.id, db)

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
        "guide_message": (
            "아이의 답변을 고치거나 해석하지 말고, "
            "가능한 한 아이가 말한 표현 그대로 입력해주세요."
        ),
        "question_count": len(interactions),
        "questions": [                                    # 추가
        {
            "sort_order": i.sort_order,
            "question_text": i.question_text,
        }
        for i in interactions
        ],
        "message": "PDI 질문이 생성되었습니다. 첫 질문을 조회해주세요.",
    }


@router.get("/{test_id}/pdi/current", summary="현재 PDI 질문 조회")
def get_current_pdi_question(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    htp_test = get_test_or_404(test_id, current_user.id, db)

    if htp_test.test_status not in ["waiting_pdi_answers", "followup_needed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDI 질문을 조회할 수 있는 상태가 아닙니다.",
        )

    interaction = (
        db.query(HtpPdiInteraction)
        .filter(
            HtpPdiInteraction.htp_test_id == htp_test.id,
            HtpPdiInteraction.answered_at.is_(None),
        )
        .order_by(HtpPdiInteraction.round_no, HtpPdiInteraction.sort_order)
        .first()
    )

    if interaction is None:
        return {"completed": True, "message": "모든 질문이 완료되었습니다."}

    total_count = (
        db.query(HtpPdiInteraction)
        .filter(HtpPdiInteraction.htp_test_id == htp_test.id)
        .count()
    )

    return {
        "completed": False,
        "question": {
            "question_id": interaction.id,
            "round_no": interaction.round_no,
            "sort_order": interaction.sort_order,
            "current_step": interaction.sort_order,
            "total_count": total_count,
            "question_text": interaction.question_text,
            "question_type": interaction.question_type,
            "target_type": interaction.target_type,
        },
    }


@router.post("/{test_id}/pdi/answer", summary="PDI 단일 질문 답변 또는 건너뛰기")
def save_single_pdi_answer(
    test_id: int,
    request: PdiSingleAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    htp_test = get_test_or_404(test_id, current_user.id, db)

    if htp_test.test_status not in ["waiting_pdi_answers", "followup_needed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDI 답변을 저장할 수 있는 상태가 아닙니다.",
        )

    interaction = (
        db.query(HtpPdiInteraction)
        .filter(
            HtpPdiInteraction.id == request.question_id,
            HtpPdiInteraction.htp_test_id == htp_test.id,
        )
        .first()
    )

    if interaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="질문을 찾을 수 없습니다.",
        )

    # 건너뛰기: answer_text=None, 답변: answer_text 저장
    interaction.answer_text = None if request.skip else request.answer_text
    interaction.answered_at = datetime.utcnow()

    db.flush()

    next_question = (
        db.query(HtpPdiInteraction)
        .filter(
            HtpPdiInteraction.htp_test_id == htp_test.id,
            HtpPdiInteraction.answered_at.is_(None),
        )
        .order_by(HtpPdiInteraction.round_no, HtpPdiInteraction.sort_order)
        .first()
    )

    # 모든 질문 처리 완료
    if next_question is None:
        answered_count = (
            db.query(HtpPdiInteraction)
            .filter(
                HtpPdiInteraction.htp_test_id == htp_test.id,
                HtpPdiInteraction.answer_text.is_not(None),
            )
            .count()
        )
        htp_test.pdi_status = "completed"
        htp_test.test_status = "ready_to_generate_report"
        htp_test.pdi_summary_json = {
            "status": "completed",
            "answered_count": answered_count,
            "summary": "PDI 답변 저장 완료",
        }
        db.commit()
        return {"completed": True, "message": "모든 질문이 완료되었습니다."}

    total_count = (
        db.query(HtpPdiInteraction)
        .filter(HtpPdiInteraction.htp_test_id == htp_test.id)
        .count()
    )
    db.commit()

    return {
        "completed": False,
        "next_question": {
            "question_id": next_question.id,
            "round_no": next_question.round_no,
            "sort_order": next_question.sort_order,
            "current_step": next_question.sort_order,
            "total_count": total_count,
            "question_text": next_question.question_text,
            "question_type": next_question.question_type,
            "target_type": next_question.target_type,
        },
    }


@router.post("/{test_id}/pdi/skip", summary="PDI 전체 건너뛰기")
def skip_pdi(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    htp_test = get_test_or_404(test_id, current_user.id, db)

    if htp_test.test_status not in ["pdi_choice_pending", "waiting_pdi_answers"]:
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
        "message": "PDI를 건너뛰었습니다.",
    }


@router.post("/{test_id}/generate-report", summary="HTP 최종 리포트 생성")
def generate_report(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    htp_test = get_test_or_404(test_id, current_user.id, db)

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

    apply_report_to_test(htp_test=htp_test, report_json=report_json)

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
def get_test_status(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    htp_test = get_test_or_404(test_id, current_user.id, db)

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
        "summary_text": htp_test.summary_text,
        "main_emotion": htp_test.main_emotion,
        "created_at": htp_test.created_at,
        "updated_at": htp_test.updated_at,
    }
