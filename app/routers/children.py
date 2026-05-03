from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ChildCreateRequest(BaseModel):
    name: str
    age: int
    gender: str


class ChildUpdateRequest(BaseModel):
    name: str | None = None
    age: int | None = None
    gender: str | None = None


@router.get("", summary="자녀 목록 조회")
def get_children():
    return [
        {
            "child_id": 1,
            "name": "김OO",
            "age": 7,
            "gender": "female"
        }
    ]


@router.post("", summary="자녀 추가")
def create_child(request: ChildCreateRequest):
    return {
        "child_id": 1,
        "name": request.name,
        "age": request.age,
        "gender": request.gender
    }


@router.patch("/{child_id}", summary="자녀 정보 수정")
def update_child(child_id: int, request: ChildUpdateRequest):
    return {
        "child_id": child_id,
        "message": "자녀 정보 수정 완료"
    }


@router.delete("/{child_id}", summary="자녀 삭제")
def delete_child(child_id: int):
    return {
        "child_id": child_id,
        "message": "자녀 삭제 완료"
    }