import asyncio
import json
import os
import tempfile
import unittest
from io import BytesIO
from types import SimpleNamespace

from fastapi import UploadFile
from PIL import Image

from app.models.htp_canvas_drawing import HtpCanvasDrawing
from app.models.htp_test import HtpTest
from app.routers.drawings import upload_canvas_drawing


class _FakeQuery:
    def __init__(self, value):
        self.value = value

    def filter(self, *args):
        return self

    def first(self):
        return self.value


class _FakeDb:
    def __init__(self, htp_test):
        self.htp_test = htp_test
        self.canvas_drawing = None
        self.did_rollback = False

    def query(self, model):
        value = self.htp_test if model is HtpTest else self.canvas_drawing
        return _FakeQuery(value)

    def add(self, value):
        self.canvas_drawing = value

    def commit(self):
        return None

    def rollback(self):
        self.did_rollback = True

    def refresh(self, value):
        if isinstance(value, HtpCanvasDrawing) and value.id is None:
            value.id = 77


def _build_test_record():
    return SimpleNamespace(
        id=10,
        user_id=3,
        test_status="created",
        pdi_status="not_started",
        drawing_time_minutes=None,
        original_image_path=None,
        result_image_path=None,
        yolo_result_json=None,
        visual_features_json=None,
        pdi_summary_json=None,
        summary_text=None,
        main_emotion=None,
        report_text=None,
        report_json=None,
        recommendations_json=None,
    )


def _build_png_upload():
    image_buffer = BytesIO()
    Image.new("RGB", (64, 48), "white").save(image_buffer, format="PNG")
    image_buffer.seek(0)
    return UploadFile(filename="drawing.png", file=image_buffer)


class CanvasDrawingRouterTest(unittest.TestCase):
    def test_uploads_canvas_image_and_unavailable_pressure_data(self):
        htp_test = _build_test_record()
        db = _FakeDb(htp_test)
        payload = {
            "schema_version": 1,
            "canvas": {"width": 64, "height": 48},
            "duration_ms": 65_000,
            "strokes": [
                {
                    "pointer_type": "touch",
                    "pressure_source": "unavailable",
                    "points": [
                        {"x": 0.1, "y": 0.2, "t_ms": 0},
                        {"x": 0.3, "y": 0.4, "t_ms": 16},
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            previous_directory = os.getcwd()
            os.chdir(temp_dir)
            try:
                result = asyncio.run(
                    upload_canvas_drawing(
                        test_id=10,
                        drawing_data=json.dumps(payload),
                        file=_build_png_upload(),
                        db=db,
                        current_user=SimpleNamespace(id=3),
                    )
                )
                self.assertTrue(os.path.exists(result["saved_path"]))
            finally:
                os.chdir(previous_directory)

        self.assertEqual(result["drawing_id"], 77)
        self.assertEqual(result["test_status"], "image_uploaded")
        self.assertEqual(result["next_action"], "analyze_image")
        self.assertEqual(result["drawing_time_minutes"], 1)
        self.assertFalse(result["pressure_available"])
        self.assertEqual(db.canvas_drawing.rendered_width, 64)
        self.assertEqual(db.canvas_drawing.rendered_height, 48)
        self.assertFalse(db.canvas_drawing.has_measured_pressure)


if __name__ == "__main__":
    unittest.main()
