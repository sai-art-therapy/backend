from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.child import Child
from app.models.user import User

router = APIRouter()


class ChildCreateRequest(BaseModel):
    name: str
    birth_year: int
    gender: str


class ChildUpdateRequest(BaseModel):
    name: str | None = None
    birth_year: int | None = None
    gender: str | None = None


@router.get("", summary="자녀 목록 조회")
def get_children(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    children = (
        db.query(Child)
        .filter(Child.user_id == current_user.id)
        .order_by(Child.created_at.desc())
        .all()
    )

    return [
        {
            "child_id": child.id,
            "name": child.name,
            "birth_year": child.birth_year,
            "gender": child.gender,
            "created_at": child.created_at,
            "updated_at": child.updated_at,
        }
        for child in children
    ]


@router.post("", summary="자녀 추가", status_code=status.HTTP_201_CREATED)
def create_child(
    request: ChildCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    child = Child(
        user_id=current_user.id,
        name=request.name,
        birth_year=request.birth_year,
        gender=request.gender,
    )

    db.add(child)
    db.commit()
    db.refresh(child)

    return {
        "child_id": child.id,
        "name": child.name,
        "birth_year": child.birth_year,
        "gender": child.gender,
        "created_at": child.created_at,
        "updated_at": child.updated_at,
    }


@router.patch("/{child_id}", summary="자녀 정보 수정")
def update_child(
    child_id: int,
    request: ChildUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    child = (
        db.query(Child)
        .filter(Child.id == child_id, Child.user_id == current_user.id)
        .first()
    )

    if child is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="자녀 정보를 찾을 수 없습니다.",
        )

    if request.name is not None:
        child.name = request.name
    if request.birth_year is not None:
        child.birth_year = request.birth_year
    if request.gender is not None:
        child.gender = request.gender

    db.commit()
    db.refresh(child)

    return {
        "child_id": child.id,
        "name": child.name,
        "birth_year": child.birth_year,
        "gender": child.gender,
        "created_at": child.created_at,
        "updated_at": child.updated_at,
        "message": "자녀 정보 수정 완료",
    }


@router.delete("/{child_id}", summary="자녀 삭제")
def delete_child(
    child_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    child = (
        db.query(Child)
        .filter(Child.id == child_id, Child.user_id == current_user.id)
        .first()
    )

    if child is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="자녀 정보를 찾을 수 없습니다.",
        )

    db.delete(child)
    db.commit()

    return {
        "child_id": child_id,
        "message": "자녀 삭제 완료",
    }