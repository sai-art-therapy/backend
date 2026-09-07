import os
import tempfile
import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.routers.reports import _report_image_url, router


class _FakeQuery:
    def __init__(self, value):
        self.value = value

    def filter(self, *args):
        return self

    def first(self):
        return self.value


class _FakeDb:
    def __init__(self, report):
        self.report = report

    def query(self, model):
        return _FakeQuery(self.report)


def _client(report):
    app = FastAPI()
    app.include_router(router, prefix="/reports")
    app.dependency_overrides[get_db] = lambda: _FakeDb(report)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=3)
    return TestClient(app)


class ReportImageRouterTest(unittest.TestCase):
    def test_serves_owned_image_with_private_cache_headers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_directory = os.getcwd()
            os.chdir(temp_dir)
            try:
                image_path = "uploads/htp/original/report.png"
                os.makedirs("uploads/htp/original")
                with open(image_path, "wb") as image_file:
                    image_file.write(b"private-report-image")

                report = SimpleNamespace(
                    id=10,
                    user_id=3,
                    original_image_path=image_path,
                    result_image_path=None,
                )
                response = _client(report).get("/reports/10/images/original")
            finally:
                os.chdir(previous_directory)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, b"private-report-image")
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.headers["cache-control"], "private, max-age=300")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_returns_not_found_when_report_is_not_owned(self):
        response = _client(None).get("/reports/10/images/original")
        self.assertEqual(response.status_code, 404)

    def test_does_not_serve_file_outside_upload_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_directory = os.getcwd()
            os.chdir(temp_dir)
            try:
                with open("private.png", "wb") as image_file:
                    image_file.write(b"must-not-be-served")
                report = SimpleNamespace(
                    id=10,
                    user_id=3,
                    original_image_path="private.png",
                    result_image_path=None,
                )
                response = _client(report).get("/reports/10/images/original")
            finally:
                os.chdir(previous_directory)

        self.assertEqual(response.status_code, 404)

    def test_rejects_unknown_image_kind(self):
        response = _client(None).get("/reports/10/images/thumbnail")
        self.assertEqual(response.status_code, 422)

    def test_report_response_url_is_only_present_for_existing_path_value(self):
        self.assertEqual(
            _report_image_url(10, "result", "uploads/htp/result/report.jpg"),
            "/reports/10/images/result",
        )
        self.assertIsNone(_report_image_url(10, "result", None))


if __name__ == "__main__":
    unittest.main()
