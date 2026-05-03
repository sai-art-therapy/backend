from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

router = APIRouter()


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup", summary="회원가입")
def signup(request: SignupRequest):
    return {
        "message": "회원가입 완료",
        "email": request.email
    }


@router.post("/login", summary="로그인")
def login(request: LoginRequest):
    return {
        "access_token": "sample_access_token",
        "token_type": "bearer"
    }


@router.post("/logout", summary="로그아웃")
def logout():
    return {
        "message": "로그아웃 완료"
    }