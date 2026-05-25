from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.child import Child
from app.models.user import User

router = APIRouter()


class ChildCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)
    birth_year: int
    gender: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("자녀 이름을 입력해주세요.")
        return name

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        if value not in {"male", "female"}:
            raise ValueError("성별은 male 또는 female만 가능합니다.")
        return value


class ChildUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=20)
    birth_year: int | None = None
    gender: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value

        name = value.strip()
        if not name:
            raise ValueError("자녀 이름을 입력해주세요.")
        return name

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str | None) -> str | None:
        if value is None:
            return value

        if value not in {"male", "female"}:
            raise ValueError("성별은 male 또는 female만 가능합니다.")

        return value


def serialize_child(child: Child) -> dict:
    return {
        "child_id": child.id,
        "name": child.name,
        "birth_year": child.birth_year,
        "gender": child.gender,
        "created_at": child.created_at,
        "updated_at": child.updated_at,
    }


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

    return [serialize_child(child) for child in children]


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

    return serialize_child(child)


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

    response = serialize_child(child)
    response["message"] = "자녀 정보 수정 완료"

    return response


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