from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class HtpPdiInteraction(Base):
    __tablename__ = "htp_pdi_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    htp_test_id: Mapped[int] = mapped_column(
        ForeignKey("htp_tests.id"),
        nullable=False,
        index=True,
    )

    # 질문 차수
    # 1: 최초 질문 묶음, 2: 추가 질문 묶음
    round_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # 같은 round 안에서 프론트에 보여줄 순서
    sort_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # house / tree / person / relationship / global
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # default_pdi / image_based / followup
    question_type: Mapped[str] = mapped_column(String(30), nullable=False)

    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # GPT가 이 질문을 생성한 이유
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 부모가 아이에게 물어보고 입력한 답변
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    htp_test = relationship("HtpTest", back_populates="pdi_interactions")
