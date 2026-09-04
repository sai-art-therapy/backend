from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class HtpCanvasDrawing(Base):
    __tablename__ = "htp_canvas_drawings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    htp_test_id: Mapped[int] = mapped_column(
        ForeignKey("htp_tests.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    canvas_width: Mapped[int] = mapped_column(Integer, nullable=False)
    canvas_height: Mapped[int] = mapped_column(Integer, nullable=False)
    rendered_width: Mapped[int] = mapped_column(Integer, nullable=False)
    rendered_height: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    stroke_count: Mapped[int] = mapped_column(Integer, nullable=False)
    point_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pressure_point_count: Mapped[int] = mapped_column(Integer, nullable=False)
    has_measured_pressure: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    drawing_data_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rendered_image_path: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    htp_test = relationship("HtpTest", back_populates="canvas_drawing")
