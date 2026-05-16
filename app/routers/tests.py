from datetime import datetime
from pathlib import Path
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.child import Child
from app.models.htp_test import HtpTest

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


class AnswerItem(BaseModel):
    question_id: int
    answer: str


class AnswerSaveRequest(BaseModel):
    answers: List[AnswerItem]


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
    )

    db.add(htp_test)
    db.commit()
    db.refresh(htp_test)

    return {
        "test_id": htp_test.id,
        "child_id": htp_test.child_id,
        "test_status": htp_test.test_status,
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
        "message": "이미지 업로드 완료",
    }


@router.get("/{test_id}/questions", summary="그림 기반 추가 질문 조회")
def get_test_questions(test_id: int, db: Session = Depends(get_db)):
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

    return {
        "test_id": test_id,
        "questions": [
            {
                "question_id": 1,
                "question": "이 그림을 그릴 때 아이가 어떤 이야기를 했나요?",
            },
            {
                "question_id": 2,
                "question": "그림 속 사람은 어떤 기분이라고 했나요?",
            },
            {
                "question_id": 3,
                "question": "그림에서 가장 마음에 드는 부분은 무엇이라고 했나요?",
            },
        ],
    }


@router.post("/{test_id}/answers", summary="추가 질문 답변 저장")
def save_test_answers(
    test_id: int,
    request: AnswerSaveRequest,
    db: Session = Depends(get_db),
):
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

    # TODO: 추후 test_answers 테이블을 만들면 실제 답변 저장으로 변경
    return {
        "test_id": test_id,
        "saved_count": len(request.answers),
        "message": "답변 저장 완료",
    }


@router.post("/{test_id}/analyze", summary="AI 심리 분석 요청")
def analyze_test(test_id: int, db: Session = Depends(get_db)):
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

    if not htp_test.original_image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="분석할 이미지가 업로드되지 않았습니다.",
        )

    HTP_RESULT_DIR.mkdir(parents=True, exist_ok=True)

    # TODO: 실제 YOLO/OpenCV 결과 이미지 생성 후 result_image_path에 저장
    # 현재는 개발 테스트용으로 원본 이미지 경로를 결과 경로처럼 사용
    result_image_path = htp_test.original_image_path

    mock_yolo_result = {
        "objects": [
            {
                "label": "house",
                "confidence": 0.92,
                "bbox": [10, 20, 100, 120],
            },
            {
                "label": "tree",
                "confidence": 0.88,
                "bbox": [140, 30, 220, 180],
            },
            {
                "label": "person",
                "confidence": 0.85,
                "bbox": [240, 50, 320, 220],
            },
        ]
    }

    mock_report_json = {
        "title": "아이의 마음 이야기",
        "summary": "전반적으로 안정적인 정서 기반을 갖추고 있으며, 자기표현과 가족 인식에서 긍정적인 특징이 관찰됩니다.",
        "elements": {
            "house": {
                "label": "집",
                "category": "정서・가족 인식",
                "status": "양호",
                "basis": "집 그림 기반",
                "description": "문과 창문이 적절한 크기로 표현되어 타인에게 열려 있는 태도를 보여줄 수 있습니다.",
                "tags": ["개방적 태도", "안정적 가족감", "감정 표현 점검"],
                "bbox": [10, 20, 100, 120],
                "image_path": result_image_path,
            },
            "tree": {
                "label": "나무",
                "category": "에너지・정서 안정감",
                "status": "양호",
                "basis": "나무 그림 기반",
                "description": "나무의 형태에서 성장감과 에너지가 관찰됩니다.",
                "tags": ["성장감", "에너지", "정서 안정"],
                "bbox": [140, 30, 220, 180],
                "image_path": result_image_path,
            },
            "person": {
                "label": "사람",
                "category": "자아상・자기표현",
                "status": "점검",
                "basis": "사람 그림 기반",
                "description": "사람 그림에서 자기표현 방식과 대인관계에 대한 단서를 살펴볼 수 있습니다.",
                "tags": ["자기표현", "자아상 점검", "대인관계"],
                "bbox": [240, 50, 320, 220],
                "image_path": result_image_path,
            },
        },
    }

    mock_recommendations = [
        {
            "title": "집에서 함께 그림 그리기",
            "description": "아이와 함께 가족 그림을 그리고 이야기를 나눠보세요. 자연스럽게 감정을 표현하는 데 도움이 됩니다.",
            "type": "home_activity",
        },
        {
            "title": "자연 속 놀이 활동 권장",
            "description": "흙 놀이, 모래 놀이처럼 안정감을 키우는 신체 활동이 도움이 됩니다.",
            "type": "outdoor_activity",
        },
        {
            "title": "전문 상담 고려",
            "description": "결과가 걱정되시거나 아이에게 지속적인 변화가 보인다면 아동 심리 전문가와 상담해보세요.",
            "type": "referral",
        },
    ]

    htp_test.test_status = "completed"
    htp_test.result_image_path = result_image_path
    htp_test.yolo_result_json = mock_yolo_result
    htp_test.summary_text = mock_report_json["summary"]
    htp_test.main_emotion = "stable"
    htp_test.report_text = "개발 테스트용 HTP 분석 리포트입니다."
    htp_test.report_json = mock_report_json
    htp_test.recommendations_json = mock_recommendations

    db.commit()
    db.refresh(htp_test)

    return {
        "test_id": htp_test.id,
        "status": htp_test.test_status,
        "report_id": htp_test.id,
        "summary_text": htp_test.summary_text,
        "main_emotion": htp_test.main_emotion,
        "message": "AI 분석이 완료되었습니다.",
    }


@router.get("/{test_id}", summary="검사 상태 조회")
def get_test_status(test_id: int, db: Session = Depends(get_db)):
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

    return {
        "test_id": htp_test.id,
        "child_id": htp_test.child_id,
        "status": htp_test.test_status,
        "report_id": htp_test.id if htp_test.test_status == "completed" else None,
        "original_image_path": htp_test.original_image_path,
        "result_image_path": htp_test.result_image_path,
        "summary_text": htp_test.summary_text,
        "main_emotion": htp_test.main_emotion,
        "created_at": htp_test.created_at,
        "updated_at": htp_test.updated_at,
    }