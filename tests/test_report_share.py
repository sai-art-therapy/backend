import os
import tempfile
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.routers.reports import router as reports_router
from app.routers.shared_reports import (
    _extract_share_token,
    get_current_report_share,
    router,
    serialize_shared_report,
)
from app.services.report_share_service import (
    generate_share_token,
    hash_share_token,
    issue_report_share,
)


class _FakeQuery:
    def __init__(self, value=None, update_count=0):
        self.value = value
        self.update_count = update_count

    def join(self, *args):
        return self

    def filter(self, *args):
        return self

    def first(self):
        return self.value

    def update(self, *args, **kwargs):
        return self.update_count


class _FakeDb:
    def __init__(self, value=None):
        self.value = value
        self.added = None
        self.flushed = False
        self.committed = False

    def query(self, *models):
        return _FakeQuery(self.value, update_count=1)

    def add(self, value):
        self.added = value

    def flush(self):
        self.flushed = True

    def commit(self):
        self.committed = True


def _sample_report(**overrides):
    values = {
        "id": 10,
        "test_status": "completed",
        "test_date": datetime(2026, 9, 7, 12, 0, 0),
        "summary_text": "아이의 강점을 중심으로 살펴보세요.",
        "main_emotion": "안정",
        "report_json": {
            "summary": {
                "title": "마음 이야기",
                "one_line_summary": "안정적인 표현이 관찰됩니다.",
                "disclaimer": "전문 진단을 대체하지 않습니다.",
            },
            "tabs": {
                "house": {"interpretation": "집 해석"},
                "tree": {"interpretation": "나무 해석"},
                "person": {"interpretation": "사람 해석"},
            },
            "relationship_analysis": {"summary": "관계 해석"},
            "recommendations": ["아이의 이야기를 들어 주세요."],
            "safety_notice": "참고용 리포트입니다.",
        },
        "recommendations_json": [],
        "original_image_path": "uploads/htp/original/report.png",
        "result_image_path": "uploads/htp/result/report.png",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ReportShareTokenTest(unittest.TestCase):
    def test_generates_random_high_entropy_token_and_stores_only_hash(self):
        first = generate_share_token()
        second = generate_share_token()

        self.assertNotEqual(first, second)
        self.assertGreaterEqual(len(first), 40)
        self.assertEqual(len(hash_share_token(first)), 64)
        self.assertNotIn(first, hash_share_token(first))

    def test_issuing_share_revokes_previous_and_flushes_new_hash(self):
        db = _FakeDb()
        token, share = issue_report_share(db, report_id=10)

        self.assertTrue(db.flushed)
        self.assertIs(db.added, share)
        self.assertEqual(share.report_id, 10)
        self.assertEqual(share.token_hash, hash_share_token(token))
        self.assertNotEqual(share.token_hash, token)
        self.assertGreater(share.expires_at, datetime.utcnow())

    def test_extracts_only_share_authorization_scheme(self):
        self.assertEqual(_extract_share_token("Share abc123"), "abc123")
        self.assertEqual(_extract_share_token("share abc123"), "abc123")
        self.assertIsNone(_extract_share_token("Bearer abc123"))
        self.assertIsNone(_extract_share_token(None))

    @patch("app.routers.shared_reports.find_active_report_share")
    def test_share_dependency_passes_only_share_token_to_lookup(self, find_share):
        expected = SimpleNamespace(report_id=10)
        find_share.return_value = expected
        db = _FakeDb()

        actual = get_current_report_share("Share secret-token", db)

        self.assertIs(actual, expected)
        find_share.assert_called_once_with(db, "secret-token")


class ReportShareOwnerRouterTest(unittest.TestCase):
    def _client(self, report):
        db = _FakeDb(report)
        app = FastAPI()
        app.include_router(reports_router, prefix="/reports")
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=3)
        return TestClient(app), db

    @patch("app.routers.reports.issue_report_share")
    def test_owner_can_issue_share_for_completed_report(self, issue_share):
        expires_at = datetime(2026, 9, 10, 12, 0, 0)
        issue_share.return_value = (
            "opaque-token",
            SimpleNamespace(expires_at=expires_at),
        )
        client, db = self._client(_sample_report())

        response = client.post("/reports/10/shares")

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["share_token"], "opaque-token")
        self.assertEqual(response.json()["token_type"], "Share")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertTrue(db.committed)
        issue_share.assert_called_once_with(db, 10)

    @patch("app.routers.reports.issue_report_share")
    def test_incomplete_report_cannot_be_shared(self, issue_share):
        client, db = self._client(_sample_report(test_status="analyzing"))

        response = client.post("/reports/10/shares")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(db.committed)
        issue_share.assert_not_called()

    @patch("app.routers.reports.revoke_report_shares")
    def test_owner_can_revoke_report_share(self, revoke_shares):
        revoke_shares.return_value = 1
        client, db = self._client(_sample_report())

        response = client.delete("/reports/10/shares")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"revoked": True})
        self.assertTrue(db.committed)
        revoke_shares.assert_called_once_with(db, 10)


class SharedReportRouterTest(unittest.TestCase):
    def test_shared_payload_excludes_internal_ids_paths_and_raw_analysis(self):
        report = _sample_report()
        child = SimpleNamespace(name="민준", birth_year=2020, gender="male")
        share = SimpleNamespace(expires_at=datetime.utcnow() + timedelta(hours=1))

        payload = serialize_shared_report(report, child, share)
        shared_report = payload["report"]

        self.assertNotIn("report_id", shared_report)
        self.assertNotIn("child_id", shared_report["child"])
        self.assertNotIn("original_image_path", shared_report["images"])
        self.assertNotIn("analysis", shared_report)
        self.assertNotIn("raw_report", shared_report)
        self.assertEqual(
            shared_report["images"]["original_image_url"],
            "/shared-reports/images/original",
        )

    def test_shared_report_requires_share_authorization(self):
        app = FastAPI()
        app.include_router(router, prefix="/shared-reports")
        app.dependency_overrides[get_db] = lambda: _FakeDb()

        response = TestClient(app).get("/shared-reports")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["www-authenticate"], "Share")

    def test_serves_sanitized_shared_report_with_no_store_headers(self):
        report = _sample_report()
        child = SimpleNamespace(name="민준", birth_year=2020, gender="male")
        share = SimpleNamespace(
            report_id=10,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        app = FastAPI()
        app.include_router(router, prefix="/shared-reports")
        app.dependency_overrides[get_db] = lambda: _FakeDb((report, child))
        app.dependency_overrides[get_current_report_share] = lambda: share

        response = TestClient(app).get("/shared-reports")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertEqual(response.headers["vary"], "Authorization")
        self.assertEqual(response.json()["report"]["child"]["name"], "민준")

    def test_serves_shared_image_without_login_jwt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_directory = os.getcwd()
            os.chdir(temp_dir)
            try:
                image_path = "uploads/htp/original/report.png"
                os.makedirs("uploads/htp/original")
                with open(image_path, "wb") as image_file:
                    image_file.write(b"shared-private-image")

                report = _sample_report(original_image_path=image_path)
                share = SimpleNamespace(report_id=10)
                app = FastAPI()
                app.include_router(router, prefix="/shared-reports")
                app.dependency_overrides[get_db] = lambda: _FakeDb(report)
                app.dependency_overrides[get_current_report_share] = lambda: share
                response = TestClient(app).get(
                    "/shared-reports/images/original"
                )
            finally:
                os.chdir(previous_directory)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, b"shared-private-image")
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertEqual(response.headers["vary"], "Authorization")


if __name__ == "__main__":
    unittest.main()
