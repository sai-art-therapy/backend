from typing import Literal

from pydantic import BaseModel, Field


class CanvasPoint(BaseModel):
    """A point in normalized canvas coordinates."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    t_ms: int = Field(ge=0)
    pressure: float | None = Field(default=None, ge=0.0, le=1.0)


class CanvasStroke(BaseModel):
    stroke_id: str | None = Field(default=None, max_length=100)
    pointer_type: Literal["pen", "touch", "mouse", "unknown"]
    pressure_source: Literal["measured", "unavailable"]
    brush_width_px: float | None = Field(default=None, gt=0.0, le=200.0)
    points: list[CanvasPoint]


class CanvasSize(BaseModel):
    width: int = Field(gt=0, le=10000)
    height: int = Field(gt=0, le=10000)


class CanvasDrawingPayload(BaseModel):
    schema_version: Literal[1] = 1
    canvas: CanvasSize
    duration_ms: int = Field(gt=0, le=86_400_000)
    strokes: list[CanvasStroke]


class CanvasDrawingUploadResponse(BaseModel):
    test_id: int
    drawing_id: int
    filename: str
    saved_path: str
    input_type: Literal["canvas"] = "canvas"
    test_status: str
    pdi_status: str
    next_action: Literal["analyze_image"] = "analyze_image"
    duration_ms: int
    drawing_time_minutes: int
    stroke_count: int
    point_count: int
    pressure_point_count: int
    pressure_available: bool
    message: str
