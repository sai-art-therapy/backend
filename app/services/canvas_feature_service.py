from math import sqrt


def _position_label(value: float) -> str:
    if value < 1 / 3:
        return "left"
    if value < 2 / 3:
        return "center"
    return "right"


def _vertical_position_label(value: float) -> str:
    if value < 1 / 3:
        return "top"
    if value < 2 / 3:
        return "middle"
    return "bottom"


def _standard_deviation(values: list[float], mean: float) -> float:
    if not values:
        return 0.0

    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return sqrt(variance)


def extract_canvas_features(drawing_data: dict | None) -> dict:
    if not drawing_data:
        return {
            "available": False,
            "reason": "canvas_data_not_available",
        }

    strokes = drawing_data.get("strokes", [])
    points = []
    measured_pressures = []

    for stroke in strokes:
        stroke_points = stroke.get("points", [])
        points.extend(stroke_points)

        if stroke.get("pressure_source") == "measured":
            measured_pressures.extend(
                point["pressure"]
                for point in stroke_points
                if point.get("pressure") is not None
            )

    if not points:
        return {
            "available": False,
            "reason": "drawing_points_not_available",
        }

    x_values = [point["x"] for point in points]
    y_values = [point["y"] for point in points]

    min_x = min(x_values)
    max_x = max(x_values)
    min_y = min(y_values)
    max_y = max(y_values)

    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    pressure_features = {
        "available": False,
        "reason": "measured_pressure_not_available",
    }

    if measured_pressures:
        pressure_mean = sum(measured_pressures) / len(measured_pressures)
        pressure_stddev = _standard_deviation(
            measured_pressures,
            pressure_mean,
        )

        pressure_features = {
            "available": True,
            "measured_point_count": len(measured_pressures),
            "mean": round(pressure_mean, 4),
            "min": round(min(measured_pressures), 4),
            "max": round(max(measured_pressures), 4),
            "stddev": round(pressure_stddev, 4),
        }

    duration_ms = drawing_data.get("duration_ms")

    return {
        "available": True,
        "duration": {
            "total_ms": duration_ms,
            "total_seconds": (
                round(duration_ms / 1000, 2)
                if duration_ms is not None
                else None
            ),
        },
        "stroke_count": len(strokes),
        "point_count": len(points),
        "pressure": pressure_features,
        "spatial": {
            "min_x": round(min_x, 4),
            "max_x": round(max_x, 4),
            "min_y": round(min_y, 4),
            "max_y": round(max_y, 4),
            "center_x": round(center_x, 4),
            "center_y": round(center_y, 4),
            "position": {
                "x": _position_label(center_x),
                "y": _vertical_position_label(center_y),
            },
            "occupied_area_ratio": round(
                (max_x - min_x) * (max_y - min_y),
                4,
            ),
        },
    }