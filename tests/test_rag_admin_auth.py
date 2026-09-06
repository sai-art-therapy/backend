import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.routers.rag_admin import require_rag_admin


class RagAdminAuthTest(unittest.TestCase):
    @patch("app.routers.rag_admin.RAG_ADMIN_ENABLED", False)
    def test_disabled_admin_api_is_hidden(self):
        with self.assertRaises(HTTPException) as context:
            require_rag_admin("token")

        self.assertEqual(context.exception.status_code, 404)

    @patch("app.routers.rag_admin.RAG_ADMIN_TOKEN", "a" * 32)
    @patch("app.routers.rag_admin.RAG_ADMIN_ENABLED", True)
    def test_missing_admin_token_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            require_rag_admin(None)

        self.assertEqual(context.exception.status_code, 401)

    @patch("app.routers.rag_admin.RAG_ADMIN_TOKEN", "a" * 32)
    @patch("app.routers.rag_admin.RAG_ADMIN_ENABLED", True)
    def test_wrong_admin_token_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            require_rag_admin("b" * 32)

        self.assertEqual(context.exception.status_code, 403)

    @patch("app.routers.rag_admin.RAG_ADMIN_TOKEN", "a" * 32)
    @patch("app.routers.rag_admin.RAG_ADMIN_ENABLED", True)
    def test_matching_admin_token_is_accepted(self):
        self.assertIsNone(require_rag_admin("a" * 32))


if __name__ == "__main__":
    unittest.main()
