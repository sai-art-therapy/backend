import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.routers import health


class HealthRouterTest(unittest.TestCase):
    def test_liveness_only_reports_process_state(self):
        self.assertEqual(health.liveness(), {"status": "alive"})

    @patch("app.routers.health.get_readiness_checks")
    def test_readiness_succeeds_when_dependencies_are_ready(self, readiness_checks):
        readiness_checks.return_value = {
            "database": True,
            "models": True,
            "storage": True,
        }

        result = health.readiness()

        self.assertEqual(result["status"], "ready")
        self.assertTrue(all(result["checks"].values()))

    @patch("app.routers.health.get_readiness_checks")
    def test_readiness_returns_503_when_dependency_is_unavailable(
        self, readiness_checks
    ):
        checks = {"database": False, "models": True, "storage": True}
        readiness_checks.return_value = checks

        with self.assertRaises(HTTPException) as context:
            health.readiness()

        self.assertEqual(context.exception.status_code, 503)
        self.assertEqual(
            context.exception.detail,
            {"status": "not_ready", "checks": checks},
        )


if __name__ == "__main__":
    unittest.main()
