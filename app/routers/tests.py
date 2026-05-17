from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.child import Child
from app.services.pdi_service import (
    create_mock_pdi_questions,
    format_pdi_questions,
    save_pdi_answers as save_pdi_answers_service,
    skip_pdi as skip_pdi_service,
)
from app.models.htp_test import HtpTest
from app.services.htp_analysis_service import (
    analyze_htp_image_mock,
    get_pdi_choice_payload,
)

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

    analysis_result = analyze_htp_image_mock(htp_test.original_image_path)

    result_image_path = analysis_result["result_image_path"]
    mock_yolo_result = analysis_result["yolo_result_json"]
    mock_visual_features = analysis_result["visual_features_json"]

    htp_test.test_status = "pdi_choice_pending"
    htp_test.pdi_status = "not_started"
    htp_test.result_image_path = result_image_path
    htp_test.yolo_result_json = mock_yolo_result
    htp_test.visual_features_json = mock_visual_features

    # 이전 mock 리포트가 남아있을 수 있으므로 초기화
    htp_test.summary_text = None
    htp_test.main_emotion = None
    htp_test.report_text = None
    htp_test.report_json = None
    htp_test.recommendations_json = None
    htp_test.pdi_summary_json = None

    db.commit()
    db.refresh(htp_test)

    return {
        "test_id": htp_test.id,
        "test_status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "result_image_path": htp_test.result_image_path,
        "display_detections": mock_yolo_result["display_detections"],
        "pdi_choice": get_pdi_choice_payload(),
        "message": "이미지 분석이 완료되었습니다. PDI 진행 여부를 선택해주세요.",
    }


@router.post("/{test_id}/pdi/start", summary="PDI 질문 생성")
def start_pdi(test_id: int, db: Session = Depends(get_db)):
    htp_test = get_test_or_404(test_id, db)

    if htp_test.test_status != "pdi_choice_pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDI를 시작할 수 있는 상태가 아닙니다.",
        )

    interactions = create_mock_pdi_questions(htp_test=htp_test, db=db)

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

    pdi_used = htp_test.pdi_status == "completed"
    analysis_mode = "with_pdi" if pdi_used else "without_pdi"
    confidence_level = "medium" if pdi_used else "low"

    pdi_evidence = [
        {
            "question": item.question_text,
            "answer": item.answer_text,
            "target_type": item.target_type,
        }
        for item in pdi_interactions
        if item.answer_text
    ]

    if pdi_used:
        one_line_summary = "아이의 그림 특징과 추가 답변을 함께 고려하여 조심스럽게 분석했습니다."
        pdi_notice = "PDI 답변이 리포트에 함께 반영되었습니다."
    else:
        one_line_summary = "아이의 추가 답변 없이 그림에서 관찰 가능한 특징을 중심으로 분석했습니다."
        pdi_notice = "PDI를 진행하지 않아 이미지 분석 결과 중심으로 작성되었습니다."

    mock_report_json = {
        "summary": {
            "title": "HTP 그림 분석 결과",
            "one_line_summary": one_line_summary,
            "main_emotion": "조심스러움",
            "risk_level": "관찰 필요",
            "analysis_mode": analysis_mode,
            "pdi_used": pdi_used,
            "confidence_level": confidence_level,
            "disclaimer": "본 리포트는 전문 진단이 아닌 참고용 안내입니다.",
        },
        "pdi": {
            "status": htp_test.pdi_status,
            "interactions_count": len(pdi_evidence),
            "summary": pdi_notice,
        },
        "visualization": {
            "image_path": htp_test.result_image_path,
            "display_bboxes": htp_test.yolo_result_json.get("display_detections", []),
        },
        "tabs": {
            "house": {
                "label": "집",
                "status": "보통",
                "observations": [
                    "집이 탐지되었습니다.",
                    "창문이 일부 표현되어 있으며, 문은 뚜렷하게 탐지되지 않았습니다.",
                ],
                "pdi_evidence": [
                    item for item in pdi_evidence if item["target_type"] == "house"
                ],
                "interpretation": (
                    "집은 가족관계와 생활 환경에 대한 인식을 살펴볼 때 참고할 수 있습니다. "
                    "문이 뚜렷하지 않은 점은 아이의 설명과 함께 확인하는 것이 좋습니다."
                ),
                "positive_note": "집의 전체 구조가 표현되어 있어 생활 환경에 대한 기본적인 표현은 확인됩니다.",
                "tags": ["집", "창문", "문미탐지", "가족관계"],
            },
            "tree": {
                "label": "나무",
                "status": "관찰 필요",
                "observations": [
                    "나무가 탐지되었습니다.",
                    "기둥과 수관은 표현되어 있으나 뿌리는 뚜렷하게 탐지되지 않았습니다.",
                ],
                "pdi_evidence": [
                    item for item in pdi_evidence if item["target_type"] == "tree"
                ],
                "interpretation": (
                    "나무는 자기상과 성장감을 참고하는 요소입니다. "
                    "뿌리 표현 부족은 연령과 발달단계를 함께 고려하여 조심스럽게 해석해야 합니다."
                ),
                "positive_note": "기둥과 수관이 표현되어 있어 기본적인 구조화 능력은 확인됩니다.",
                "tags": ["나무", "뿌리미탐지", "자기상"],
            },
            "person": {
                "label": "사람",
                "status": "관찰 필요",
                "observations": [
                    "사람이 비교적 작게 탐지되었습니다.",
                    "손과 발의 세부 표현은 약하게 나타납니다.",
                ],
                "pdi_evidence": [
                    item for item in pdi_evidence if item["target_type"] == "person"
                ],
                "interpretation": (
                    "사람 그림은 자기개념과 대인관계 인식을 참고하는 요소입니다. "
                    "작은 크기와 세부 표현 부족은 단정하지 않고 아이의 답변이나 생활 맥락과 함께 살펴보는 것이 좋습니다."
                ),
                "positive_note": "사람의 기본 구조는 표현되어 있어 자기표현의 기본 틀은 확인됩니다.",
                "tags": ["사람", "작은크기", "손발세부표현부족", "자기표상"],
            },
        },
        "relationship_analysis": {
            "observations": [
                "집, 나무, 사람은 한 화면 안에 함께 배치되어 있습니다.",
                "세 요소가 직접 겹치거나 강하게 밀착된 형태는 뚜렷하지 않습니다.",
            ],
            "interpretation": (
                "요소 간 거리는 가족 환경, 자기상, 대인관계 표상이 어떻게 함께 배치되는지를 "
                "참고하는 보조 정보입니다."
            ),
        },
        "recommendations": [
            {
                "title": "그림 속 이야기를 물어보기",
                "description": "아이에게 그림 속 집, 나무, 사람에 대해 편안하게 이야기할 기회를 주세요.",
            },
            {
                "title": "1~2주간 일상 관찰하기",
                "description": "최근 아이가 자기표현을 어려워하거나 혼자 있으려는 시간이 늘었는지 부드럽게 관찰해보세요.",
            },
            {
                "title": "전문 상담 고려",
                "description": "걱정되는 변화가 지속되면 아동 심리 전문가와 상담해보는 것을 권장합니다.",
            },
        ],
        "safety_notice": (
            "본 리포트는 HTP 그림 검사와 AI 분석을 바탕으로 한 참고용 안내이며, "
            "전문적인 심리 진단을 대체하지 않습니다."
        ),
    }

    mock_recommendations = mock_report_json["recommendations"]

    htp_test.test_status = "completed"
    htp_test.summary_text = mock_report_json["summary"]["one_line_summary"]
    htp_test.main_emotion = mock_report_json["summary"]["main_emotion"]
    htp_test.report_text = "개발 테스트용 HTP 분석 리포트입니다. 추후 GPT/RAG 결과로 교체 예정입니다."
    htp_test.report_json = mock_report_json
    htp_test.recommendations_json = mock_recommendations

    db.commit()
    db.refresh(htp_test)

    return {
        "test_id": htp_test.id,
        "test_status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "report_id": htp_test.id,
        "summary_text": htp_test.summary_text,
        "main_emotion": htp_test.main_emotion,
        "message": "HTP 리포트가 생성되었습니다.",
    }


@router.get("/{test_id}", summary="검사 상태 조회")
def get_test_status(test_id: int, db: Session = Depends(get_db)):
    htp_test = get_test_or_404(test_id, db)

    return {
        "test_id": htp_test.id,
        "child_id": htp_test.child_id,
        "status": htp_test.test_status,
        "pdi_status": htp_test.pdi_status,
        "report_id": htp_test.id if htp_test.test_status == "completed" else None,
        "original_image_path": htp_test.original_image_path,
        "result_image_path": htp_test.result_image_path,
        "summary_text": htp_test.summary_text,
        "main_emotion": htp_test.main_emotion,
        "created_at": htp_test.created_at,
        "updated_at": htp_test.updated_at,
    }