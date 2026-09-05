import unittest

from app.services.canvas_feature_service import extract_canvas_features


class CanvasFeatureServiceTest(unittest.TestCase):
    def test_extracts_spatial_duration_and_measured_pressure_features(self):
        drawing_data = {
            "duration_ms": 2_500,
            "strokes": [
                {
                    "pressure_source": "measured",
                    "points": [
                        {"x": 0.1, "y": 0.2, "pressure": 0.2},
                        {"x": 0.7, "y": 0.8, "pressure": 0.8},
                    ],
                },
                {
                    "pressure_source": "unavailable",
                    "points": [
                        {"x": 0.4, "y": 0.5},
                    ],
                },
            ],
        }

        features = extract_canvas_features(drawing_data)

        self.assertTrue(features["available"])
        self.assertEqual(features["duration"]["total_seconds"], 2.5)
        self.assertEqual(features["stroke_count"], 2)
        self.assertEqual(features["point_count"], 3)
        self.assertEqual(features["pressure"]["measured_point_count"], 2)
        self.assertEqual(features["pressure"]["mean"], 0.5)
        self.assertEqual(features["pressure"]["stddev"], 0.3)
        self.assertEqual(features["spatial"]["position"], {"x": "center", "y": "middle"})
        self.assertEqual(features["spatial"]["occupied_area_ratio"], 0.36)

    def test_excludes_default_pressure_when_pressure_source_is_unavailable(self):
        drawing_data = {
            "duration_ms": 1_000,
            "strokes": [
                {
                    "pressure_source": "unavailable",
                    "points": [
                        {"x": 0.2, "y": 0.2, "pressure": 0.5},
                        {"x": 0.3, "y": 0.3, "pressure": 0.5},
                    ],
                }
            ],
        }

        features = extract_canvas_features(drawing_data)

        self.assertFalse(features["pressure"]["available"])
        self.assertEqual(
            features["pressure"]["reason"],
            "measured_pressure_not_available",
        )
        self.assertNotIn("mean", features["pressure"])

    def test_marks_missing_canvas_data_as_unavailable(self):
        self.assertEqual(
            extract_canvas_features(None),
            {"available": False, "reason": "canvas_data_not_available"},
        )


if __name__ == "__main__":
    unittest.main()
