from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class HtpTest(Base):
    __tablename__ = "htp_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"), nullable=False, index=True)

    # 검사 상태 및 날짜
    test_status: Mapped[str] = mapped_column(String(30), default="created", nullable=False)
    test_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # 검사 이미지 분석 목적 동의
    consent_agreed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_agreed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 이미지 경로
    original_image_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_image_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # AI 분석 결과
    yolo_result_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # YOLO/OpenCV 기반 정량 특징
    visual_features_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # PDI 진행 상태 및 요약
    # not_started / accepted / completed / skipped
    pdi_status: Mapped[str] = mapped_column(String(30), default="not_started", nullable=False)
    pdi_summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # 그리기 소요 시간 (분)
    drawing_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 리포트 화면용 데이터
    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    main_emotion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    report_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    recommendations_json: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = relationship("User", back_populates="htp_tests")
    child = relationship("Child", back_populates="htp_tests")
    chat_sessions = relationship("ChatSession", back_populates="htp_test")

    pdi_interactions = relationship(
        "HtpPdiInteraction",
        back_populates="htp_test",
        cascade="all, delete-orphan",
    )
