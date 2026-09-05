import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.services import htp_vlm_fallback_service


class HtpVlmFallbackServiceTest(unittest.TestCase):
    def test_http_server_error_does_not_retry_and_preserves_detections(self):
        import httpx
        from openai import OpenAI

        requests = []

        def unavailable(request):
            requests.append(request)
            return httpx.Response(500, json={"error": {"message": "temporary failure"}})

        detections = [{"label": "house", "confidence": 0.9,
                       "bbox": {"x1": 1, "y1": 1, "x2": 10, "y2": 10}}]
        with tempfile.TemporaryDirectory() as directory, OpenAI(
            api_key="test-only", http_client=httpx.Client(transport=httpx.MockTransport(unavailable))
        ) as client:
            path = Path(directory) / "drawing.png"
            Image.new("RGB", (20, 20), "white").save(path)
            with patch.object(htp_vlm_fallback_service, "client", client), patch.object(
                htp_vlm_fallback_service, "OPENAI_VLM_FALLBACK_ENABLED", True
            ):
                corrected, metadata = htp_vlm_fallback_service.apply_vlm_fallback(
                    str(path), detections, set(), {0}, {"house"}
                )
        self.assertEqual(len(requests), 1)
        self.assertIs(corrected, detections)
        self.assertIn("InternalServerError", metadata["error"])

    def test_disabled_fallback_returns_the_exact_yolo_result(self):
        detections = [
            {
                "label": "house",
                "confidence": 0.9,
                "bbox": {"x1": 1, "y1": 1, "x2": 10, "y2": 10},
            }
        ]

        with patch.object(
            htp_vlm_fallback_service,
            "OPENAI_VLM_FALLBACK_ENABLED",
            False,
        ):
            corrected, metadata = htp_vlm_fallback_service.apply_vlm_fallback(
                "unused.png",
                detections,
                protected_labels=set(),
                trigger_a_detection_indexes={0},
                selected_parent_types={"house"},
            )

        self.assertIs(corrected, detections)
        self.assertEqual(
            metadata,
            {
                "triggered": False,
                "verified_count": 0,
                "removed_count": 0,
                "added_count": 0,
                "error": None,
            },
        )

    def test_openai_failure_safely_returns_the_exact_yolo_result(self):
        detections = [
            {
                "label": "house",
                "confidence": 0.9,
                "bbox": {"x1": 1, "y1": 1, "x2": 10, "y2": 10},
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "drawing.png"
            Image.new("RGB", (20, 20), "white").save(image_path)

            with (
                patch.object(
                    htp_vlm_fallback_service,
                    "OPENAI_VLM_FALLBACK_ENABLED",
                    True,
                ),
                patch.object(
                    htp_vlm_fallback_service.client,
                    "with_options",
                    side_effect=RuntimeError("temporary API failure"),
                ),
            ):
                corrected, metadata = htp_vlm_fallback_service.apply_vlm_fallback(
                    str(image_path),
                    detections,
                    protected_labels=set(),
                    trigger_a_detection_indexes={0},
                    selected_parent_types={"house"},
                )

        self.assertIs(corrected, detections)
        self.assertTrue(metadata["triggered"])
        self.assertEqual(metadata["verified_count"], 0)
        self.assertIn("RuntimeError: temporary API failure", metadata["error"])


if __name__ == "__main__":
    unittest.main()
