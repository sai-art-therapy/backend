import os
import tempfile
import unittest
from io import BytesIO
from types import SimpleNamespace

from fastapi import HTTPException, UploadFile
from PIL import Image

from app.routers.tests import upload_test_image
from app.services.image_upload_service import PHOTO_MAX_IMAGE_BYTES


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
        self.did_rollback = False

    def query(self, model):
        return _FakeQuery(self.htp_test)

    def commit(self):
        return None

    def rollback(self):
        self.did_rollback = True

    def refresh(self, value):
        return None


def _build_test_record(test_status: str = "created"):
    return SimpleNamespace(
        id=10,
        user_id=3,
        test_status=test_status,
        pdi_status="not_started",
        original_image_path=None,
    )


def _upload(image_format: str, filename: str) -> UploadFile:
    buffer = BytesIO()
    Image.new("RGB", (80, 60), "white").save(buffer, format=image_format)
    buffer.seek(0)
    return UploadFile(filename=filename, file=buffer)


class ImageUploadRouterTest(unittest.TestCase):
    def test_saves_valid_upload_as_normalized_jpeg(self):
        db = _FakeDb(_build_test_record())

        with tempfile.TemporaryDirectory() as temp_dir:
            previous_directory = os.getcwd()
            os.chdir(temp_dir)
            try:
                result = upload_test_image(
                    test_id=10,
                    file=_upload("PNG", "camera-file.heic"),
                    db=db,
                    current_user=SimpleNamespace(id=3),
                )
                saved_path = result["saved_path"]
                self.assertTrue(saved_path.endswith(".jpg"))
                with Image.open(saved_path) as image:
                    self.assertEqual(image.format, "JPEG")
            finally:
                os.chdir(previous_directory)

        self.assertEqual(result["filename"], "camera-file.heic")
        self.assertEqual(result["test_status"], "image_uploaded")

    def test_rejects_oversized_upload(self):
        db = _FakeDb(_build_test_record())
        upload = UploadFile(
            filename="large.jpg",
            file=BytesIO(b"x" * (PHOTO_MAX_IMAGE_BYTES + 1)),
        )

        with self.assertRaises(HTTPException) as context:
            upload_test_image(
                test_id=10,
                file=upload,
                db=db,
                current_user=SimpleNamespace(id=3),
            )

        self.assertEqual(context.exception.status_code, 413)
        self.assertEqual(context.exception.detail["code"], "image_too_large")

    def test_rejects_upload_after_analysis_started(self):
        db = _FakeDb(_build_test_record("pdi_choice_pending"))

        with self.assertRaises(HTTPException) as context:
            upload_test_image(
                test_id=10,
                file=_upload("JPEG", "drawing.jpg"),
                db=db,
                current_user=SimpleNamespace(id=3),
            )

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.detail["code"], "image_not_replaceable")


if __name__ == "__main__":
    unittest.main()
