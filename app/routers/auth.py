from datetime import datetime
import os
import re
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
from app.core.dependencies import get_current_user
from app.core.jwt import create_access_token
from app.db.session import get_db
from app.models.child import Child
from app.models.user import User

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Google 로그인 성공 후 최종적으로 이동할 프론트 주소
# 로컬 예: http://localhost:5173/auth/callback
# 배포 예: https://프론트도메인/auth/callback
FRONTEND_AUTH_CALLBACK_URL = os.getenv(
    "FRONTEND_AUTH_CALLBACK_URL",
    "http://localhost:5173/auth/callback",
)


# =========================
# Legacy email auth schemas
# 현재 프론트에서는 사용하지 않음
# Swagger에서는 숨김 처리
# =========================

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# =========================
# Onboarding schemas
# =========================

class TermsAgreementRequest(BaseModel):
    is_over_14: bool
    agreed_to_terms: bool
    agreed_to_privacy: bool


class NicknameUpdateRequest(BaseModel):
    nickname: str


# =========================
# Helper functions
# =========================

def validate_nickname(nickname: str) -> None:
    """
    닉네임 조건:
    - 2~10자
    - 한글/영어/숫자만 허용
    """
    if not re.fullmatch(r"[가-힣a-zA-Z0-9]{2,10}", nickname):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="닉네임은 2~10자 한글/영어/숫자만 가능합니다.",
        )


def get_onboarding_status(user: User, db: Session) -> dict:
    terms_completed = bool(user.agreed_to_service)
    nickname_completed = bool(user.nickname)

    child_exists = (
        db.query(Child)
        .filter(Child.user_id == user.id)
        .first()
        is not None
    )
    child_completed = bool(child_exists)

    if not terms_completed:
        next_step = "terms"
    elif not nickname_completed:
        next_step = "nickname"
    elif not child_completed:
        next_step = "child"
    else:
        next_step = "done"

    return {
        "terms_completed": terms_completed,
        "nickname_completed": nickname_completed,
        "child_completed": child_completed,
        "onboarding_completed": next_step == "done",
        "next_step": next_step,
    }


def make_auth_response(user: User, db: Session) -> dict:
    token = create_access_token(user.id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "nickname": user.nickname,
            "provider": user.provider,
        },
        "onboarding": get_onboarding_status(user, db),
    }


def make_frontend_redirect_url(auth_response: dict) -> str:
    """
    Google callback에서 JSON을 브라우저에 보여주지 않고
    프론트 callback 페이지로 token과 next_step을 전달한다.
    """
    onboarding = auth_response["onboarding"]

    params = {
        "access_token": auth_response["access_token"],
        "token_type": auth_response["token_type"],
        "next_step": onboarding["next_step"],
        "onboarding_completed": str(onboarding["onboarding_completed"]).lower(),
    }

    return f"{FRONTEND_AUTH_CALLBACK_URL}?{urlencode(params)}"


# =========================
# Legacy email auth
# 현재 프론트 화면에서는 사용하지 않으므로 Swagger에서 숨김
# =========================

@router.post("/signup", summary="회원가입", include_in_schema=False)
def signup(request: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 사용 중인 이메일입니다.",
        )

    hashed_password = pwd_context.hash(request.password)

    user = User(
        email=request.email,
        name=request.name,
        hashed_password=hashed_password,
        provider="email",
        agreed_to_service=True,
        agreed_to_service_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return make_auth_response(user, db)


@router.post("/login", summary="로그인", include_in_schema=False)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    if user is None or user.hashed_password is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    if not pwd_context.verify(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    return make_auth_response(user, db)


@router.post("/logout", summary="로그아웃")
def logout():
    return {"message": "로그아웃 완료"}


# =========================
# Google OAuth
# =========================

@router.get("/google", summary="구글 로그인 시작")
def google_login():
    """
    프론트에서 Google 로그인 버튼 클릭 시 이 주소로 이동.
    이후 Google 로그인 화면으로 redirect된다.
    """
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }

    google_login_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    return RedirectResponse(url=google_login_url)


@router.get("/google/callback", summary="구글 로그인 콜백")
def google_callback(code: str, db: Session = Depends(get_db)):
    """
    Google 로그인 성공 후 Google이 호출하는 백엔드 콜백.

    흐름:
    1. Google이 code를 백엔드에 전달
    2. 백엔드가 code로 Google access_token 발급
    3. Google 사용자 정보 조회
    4. 우리 DB에서 user 조회 또는 생성
    5. 우리 서비스 JWT 발급
    6. JSON을 보여주지 않고 프론트 callback 페이지로 redirect
    """

    # 1. code → Google access_token 교환
    token_response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )

    token_data = token_response.json()
    google_access_token = token_data.get("access_token")

    if not google_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="구글 인증에 실패했습니다.",
        )

    # 2. Google access_token → 사용자 정보 조회
    userinfo_response = httpx.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {google_access_token}"},
    )

    userinfo = userinfo_response.json()

    google_id = userinfo.get("id")
    email = userinfo.get("email")
    name = userinfo.get("name", "")

    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="구글 사용자 정보를 가져올 수 없습니다.",
        )

    # 3. 기존 유저 조회
    user = db.query(User).filter(User.provider_id == google_id).first()

    if user is None:
        user = db.query(User).filter(User.email == email).first()

    # 4. 없으면 새 유저 생성
    if user is None:
        user = User(
            email=email,
            name=name,
            provider="google",
            provider_id=google_id,
            # 약관 동의는 온보딩 화면에서 따로 받기 때문에 여기서는 False
            agreed_to_service=False,
            agreed_to_service_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

    else:
        user.provider = "google"
        user.provider_id = google_id
        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

    # 5. 우리 서비스 JWT 발급 + 온보딩 상태 계산
    auth_response = make_auth_response(user, db)

    # 6. 브라우저에 JSON을 보여주지 않고 프론트 callback 페이지로 이동
    redirect_url = make_frontend_redirect_url(auth_response)

    return RedirectResponse(url=redirect_url)


# =========================
# Onboarding APIs
# =========================

@router.patch("/onboarding/terms", summary="약관 동의 저장")
def update_terms_agreement(
    request: TermsAgreementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not (
        request.is_over_14
        and request.agreed_to_terms
        and request.agreed_to_privacy
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="필수 약관에 모두 동의해야 합니다.",
        )

    current_user.agreed_to_service = True
    current_user.agreed_to_service_at = datetime.utcnow()
    current_user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(current_user)

    return {
        "message": "약관 동의가 저장되었습니다.",
        "onboarding": get_onboarding_status(current_user, db),
    }


@router.get("/nickname/check", summary="닉네임 중복 확인")
def check_nickname(
    nickname: str = Query(..., description="확인할 닉네임"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_nickname(nickname)

    existing_user = (
        db.query(User)
        .filter(User.nickname == nickname, User.id != current_user.id)
        .first()
    )

    if existing_user:
        return {
            "available": False,
            "message": "이미 사용 중인 닉네임입니다.",
        }

    return {
        "available": True,
        "message": "사용 가능한 닉네임입니다.",
    }


@router.patch("/onboarding/nickname", summary="닉네임 저장")
def update_nickname(
    request: NicknameUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_nickname(request.nickname)

    existing_user = (
        db.query(User)
        .filter(User.nickname == request.nickname, User.id != current_user.id)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 사용 중인 닉네임입니다.",
        )

    current_user.nickname = request.nickname
    current_user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(current_user)

    return {
        "message": "닉네임이 저장되었습니다.",
        "onboarding": get_onboarding_status(current_user, db),
    }


@router.get("/me", summary="내 로그인 정보 조회")
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "user": {
            "user_id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "nickname": current_user.nickname,
            "provider": current_user.provider,
        },
        "onboarding": get_onboarding_status(current_user, db),
    }