from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel
from typing import List

router = APIRouter()


class TestCreateRequest(BaseModel):
    child_id: int
    test_type: str = "HTP"


class AnswerItem(BaseModel):
    question_id: int
    answer: str


class AnswerSaveRequest(BaseModel):
    answers: List[AnswerItem]


@router.post("", summary="검사 시작")
def create_test(request: TestCreateRequest):
    return {
        "test_id": 1,
        "child_id": request.child_id,
        "status": "created"
    }


@router.post("/{test_id}/image", summary="그림 이미지 업로드")
def upload_test_image(test_id: int, file: UploadFile = File(...)):
    return {
        "test_id": test_id,
        "filename": file.filename,
        "message": "이미지 업로드 완료"
    }


@router.get("/{test_id}/questions", summary="그림 기반 추가 질문 조회")
def get_test_questions(test_id: int):
    return {
        "test_id": test_id,
        "questions": [
            {
                "question_id": 1,
                "question": "이 그림을 그릴 때 아이가 어떤 이야기를 했나요?"
            },
            {
                "question_id": 2,
                "question": "그림 속 사람은 어떤 기분이라고 했나요?"
            }
        ]
    }


@router.post("/{test_id}/answers", summary="추가 질문 답변 저장")
def save_test_answers(test_id: int, request: AnswerSaveRequest):
    return {
        "test_id": test_id,
        "saved_count": len(request.answers),
        "message": "답변 저장 완료"
    }


@router.post("/{test_id}/analyze", summary="AI 심리 분석 요청")
def analyze_test(test_id: int):
    return {
        "test_id": test_id,
        "status": "analyzing",
        "message": "AI 분석이 시작되었습니다."
    }


@router.get("/{test_id}", summary="검사 상태 조회")
def get_test_status(test_id: int):
    return {
        "test_id": test_id,
        "status": "completed",
        "report_id": 1
    }