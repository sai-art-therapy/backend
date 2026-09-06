import asyncio
import json
import os
import tempfile
import unittest
from io import BytesIO
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.htp_canvas_drawing import HtpCanvasDrawing
from app.models.htp_test import HtpTest
from app.routers.drawings import router, upload_canvas_drawing


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


def _build_json_upload(payload):
    return UploadFile(
        filename="drawing.json",
        file=BytesIO(json.dumps(payload).encode("utf-8")),
    )


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
                        drawing_data=_build_json_upload(payload),
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

    def test_accepts_drawing_data_file_larger_than_one_megabyte(self):
        db = _FakeDb(_build_test_record())
        app = FastAPI()
        app.include_router(router, prefix="/tests")
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=3)

        points = [
            {"x": 0.1 + (index % 10) / 100, "y": 0.2, "t_ms": index * 40}
            for index in range(30_000)
        ]
        payload = {
            "schema_version": 1,
            "canvas": {"width": 1024, "height": 768},
            "duration_ms": 1_200_000,
            "strokes": [
                {
                    "pointer_type": "touch",
                    "pressure_source": "unavailable",
                    "points": points,
                }
            ],
        }
        drawing_data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.assertGreater(len(drawing_data), 1024 * 1024)

        image_buffer = BytesIO()
        Image.new("RGB", (1024, 768), "white").save(image_buffer, format="PNG")

        with tempfile.TemporaryDirectory() as temp_dir:
            previous_directory = os.getcwd()
            os.chdir(temp_dir)
            try:
                response = TestClient(app).post(
                    "/tests/10/drawing",
                    files={
                        "file": (
                            "drawing.png",
                            image_buffer.getvalue(),
                            "image/png",
                        ),
                        "drawing_data": (
                            "drawing.json",
                            drawing_data,
                            "application/json",
                        ),
                    },
                )
            finally:
                os.chdir(previous_directory)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["point_count"], 30_000)

    def test_rejects_canvas_metadata_and_image_size_mismatch(self):
        db = _FakeDb(_build_test_record())
        payload = {
            "schema_version": 1,
            "canvas": {"width": 128, "height": 96},
            "duration_ms": 1_000,
            "strokes": [
                {
                    "pointer_type": "mouse",
                    "pressure_source": "unavailable",
                    "points": [{"x": 0.1, "y": 0.2, "t_ms": 0}],
                }
            ],
        }

        with self.assertRaises(HTTPException) as context:
            asyncio.run(
                upload_canvas_drawing(
                    test_id=10,
                    drawing_data=_build_json_upload(payload),
                    file=_build_png_upload(),
                    db=db,
                    current_user=SimpleNamespace(id=3),
                )
            )

        self.assertEqual(context.exception.status_code, 422)
        self.assertEqual(
            context.exception.detail["code"],
            "canvas_image_size_mismatch",
        )


if __name__ == "__main__":
    unittest.main()
