import json
import unittest

from app.services.canvas_drawing_service import (
    CanvasDrawingValidationError,
    canvas_payload_to_dict,
    parse_and_validate_canvas_drawing,
)


def build_payload(*, pressure_source="unavailable", pressures=None):
    point_pressures = pressures if pressures is not None else [None, None]
    points = []
    for index, pressure in enumerate(point_pressures):
        point = {
            "x": 0.1 + index * 0.1,
            "y": 0.2 + index * 0.1,
            "t_ms": index * 16,
        }
        if pressure is not None:
            point["pressure"] = pressure
        points.append(point)

    return {
        "schema_version": 1,
        "canvas": {"width": 1024, "height": 768},
        "duration_ms": 1_000,
        "strokes": [
            {
                "stroke_id": "stroke-1",
                "pointer_type": "pen" if pressure_source == "measured" else "touch",
                "pressure_source": pressure_source,
                "brush_width_px": 4,
                "points": points,
            }
        ],
    }


class CanvasDrawingServiceTest(unittest.TestCase):
    def test_accepts_unavailable_pressure_when_pressure_is_omitted(self):
        payload, stats = parse_and_validate_canvas_drawing(
            json.dumps(build_payload())
        )

        self.assertEqual(payload.strokes[0].pressure_source, "unavailable")
        self.assertFalse(stats.pressure_available)
        self.assertEqual(stats.stroke_count, 1)
        self.assertEqual(stats.point_count, 2)
        self.assertEqual(stats.pressure_point_count, 0)

    def test_accepts_measured_pressure_for_every_point(self):
        payload, stats = parse_and_validate_canvas_drawing(
            json.dumps(
                build_payload(
                    pressure_source="measured",
                    pressures=[0.25, 0.75],
                )
            )
        )

        self.assertTrue(stats.pressure_available)
        self.assertEqual(stats.pressure_point_count, 2)
        self.assertEqual(canvas_payload_to_dict(payload)["strokes"][0]["points"][1]["pressure"], 0.75)

    def test_rejects_synthetic_pressure_when_pressure_is_unavailable(self):
        with self.assertRaises(CanvasDrawingValidationError) as context:
            parse_and_validate_canvas_drawing(
                json.dumps(build_payload(pressures=[0.5, 0.5]))
            )

        self.assertEqual(context.exception.code, "synthetic_pressure_not_allowed")

    def test_rejects_missing_pressure_when_marked_as_measured(self):
        with self.assertRaises(CanvasDrawingValidationError) as context:
            parse_and_validate_canvas_drawing(
                json.dumps(
                    build_payload(
                        pressure_source="measured",
                        pressures=[0.4, None],
                    )
                )
            )

        self.assertEqual(context.exception.code, "missing_measured_pressure")

    def test_rejects_non_monotonic_point_time(self):
        data = build_payload()
        data["strokes"][0]["points"][0]["t_ms"] = 20
        data["strokes"][0]["points"][1]["t_ms"] = 10

        with self.assertRaises(CanvasDrawingValidationError) as context:
            parse_and_validate_canvas_drawing(json.dumps(data))

        self.assertEqual(context.exception.code, "non_monotonic_time")

    def test_rejects_point_time_after_total_duration(self):
        data = build_payload()
        data["strokes"][0]["points"][1]["t_ms"] = 1_001

        with self.assertRaises(CanvasDrawingValidationError) as context:
            parse_and_validate_canvas_drawing(json.dumps(data))

        self.assertEqual(context.exception.code, "point_time_exceeds_duration")

    def test_rejects_out_of_range_coordinates_and_pressure(self):
        data = build_payload(
            pressure_source="measured",
            pressures=[0.4, 1.2],
        )
        data["strokes"][0]["points"][0]["x"] = -0.1

        with self.assertRaises(CanvasDrawingValidationError) as context:
            parse_and_validate_canvas_drawing(json.dumps(data))

        self.assertEqual(context.exception.code, "invalid_drawing_data")

    def test_rejects_empty_strokes(self):
        data = build_payload()
        data["strokes"] = []

        with self.assertRaises(CanvasDrawingValidationError) as context:
            parse_and_validate_canvas_drawing(json.dumps(data))

        self.assertEqual(context.exception.code, "empty_strokes")


if __name__ == "__main__":
    unittest.main()
