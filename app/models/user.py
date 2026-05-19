from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 앱 온보딩 정보
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    caregiver_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # 서비스 이용 및 개인정보 처리 통합 동의
    agreed_to_service: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    agreed_to_service_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    children = relationship("Child", back_populates="user", cascade="all, delete-orphan")
    htp_tests = relationship("HtpTest", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")