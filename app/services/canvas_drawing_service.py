import json
from dataclasses import asdict, dataclass

from pydantic import ValidationError

from app.schemas.tests import CanvasDrawingPayload

MAX_DRAWING_DATA_BYTES = 15 * 1024 * 1024
MAX_STROKES = 10_000
MAX_POINTS = 250_000


class CanvasDrawingValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CanvasDrawingStats:
    stroke_count: int
    point_count: int
    pressure_point_count: int
    pressure_available: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_payload(data: object) -> CanvasDrawingPayload:
    try:
        if hasattr(CanvasDrawingPayload, "model_validate"):
            return CanvasDrawingPayload.model_validate(data)
        return CanvasDrawingPayload.parse_obj(data)
    except ValidationError as exc:
        first_error = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(item) for item in first_error.get("loc", []))
        reason = first_error.get("msg", "입력 형식이 올바르지 않습니다.")
        message = f"{location}: {reason}" if location else reason
        raise CanvasDrawingValidationError("invalid_drawing_data", message) from exc


def parse_and_validate_canvas_drawing(
    drawing_data: str,
) -> tuple[CanvasDrawingPayload, CanvasDrawingStats]:
    if len(drawing_data.encode("utf-8")) > MAX_DRAWING_DATA_BYTES:
        raise CanvasDrawingValidationError(
            "drawing_data_too_large",
            f"drawing_data는 {MAX_DRAWING_DATA_BYTES // (1024 * 1024)}MB 이하여야 합니다.",
        )

    try:
        raw_payload = json.loads(drawing_data)
    except json.JSONDecodeError as exc:
        raise CanvasDrawingValidationError(
            "invalid_json",
            "drawing_data가 올바른 JSON 형식이 아닙니다.",
        ) from exc

    payload = _parse_payload(raw_payload)

    if not payload.strokes:
        raise CanvasDrawingValidationError(
            "empty_strokes",
            "최소 한 개의 stroke가 필요합니다.",
        )
    if len(payload.strokes) > MAX_STROKES:
        raise CanvasDrawingValidationError(
            "too_many_strokes",
            f"stroke는 최대 {MAX_STROKES}개까지 전송할 수 있습니다.",
        )

    point_count = 0
    pressure_point_count = 0

    for stroke_index, stroke in enumerate(payload.strokes):
        if not stroke.points:
            raise CanvasDrawingValidationError(
                "empty_stroke_points",
                f"strokes[{stroke_index}]에 최소 한 개의 point가 필요합니다.",
            )

        previous_t_ms = -1
        for point_index, point in enumerate(stroke.points):
            point_count += 1
            if point_count > MAX_POINTS:
                raise CanvasDrawingValidationError(
                    "too_many_points",
                    f"point는 전체 합계 최대 {MAX_POINTS}개까지 전송할 수 있습니다.",
                )
            if point.t_ms < previous_t_ms:
                raise CanvasDrawingValidationError(
                    "non_monotonic_time",
                    (
                        f"strokes[{stroke_index}].points[{point_index}].t_ms는 "
                        "앞 point보다 작을 수 없습니다."
                    ),
                )
            if point.t_ms > payload.duration_ms:
                raise CanvasDrawingValidationError(
                    "point_time_exceeds_duration",
                    (
                        f"strokes[{stroke_index}].points[{point_index}].t_ms는 "
                        "duration_ms보다 클 수 없습니다."
                    ),
                )
            previous_t_ms = point.t_ms

            if point.pressure is not None:
                pressure_point_count += 1

        pressures = [point.pressure for point in stroke.points]
        if stroke.pressure_source == "measured" and any(
            pressure is None for pressure in pressures
        ):
            raise CanvasDrawingValidationError(
                "missing_measured_pressure",
                (
                    f"strokes[{stroke_index}]의 pressure_source가 measured이면 "
                    "모든 point에 pressure가 필요합니다."
                ),
            )
        if stroke.pressure_source == "unavailable" and any(
            pressure is not None for pressure in pressures
        ):
            raise CanvasDrawingValidationError(
                "synthetic_pressure_not_allowed",
                (
                    f"strokes[{stroke_index}]의 pressure_source가 unavailable이면 "
                    "point의 pressure를 생략해야 합니다."
                ),
            )

    stats = CanvasDrawingStats(
        stroke_count=len(payload.strokes),
        point_count=point_count,
        pressure_point_count=pressure_point_count,
        pressure_available=pressure_point_count > 0,
    )
    return payload, stats


def canvas_payload_to_dict(payload: CanvasDrawingPayload) -> dict:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json", exclude_none=True)
    return payload.dict(exclude_none=True)
