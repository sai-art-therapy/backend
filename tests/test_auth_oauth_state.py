import unittest
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException
from starlette.requests import Request

from app.routers.auth import OAUTH_STATE_COOKIE, google_callback, google_login


def _request_with_cookie(cookie_value: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/auth/google/callback",
            "query_string": b"",
            "headers": [
                ("cookie".encode(), f"{OAUTH_STATE_COOKIE}={cookie_value}".encode())
            ],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443),
        }
    )


class OAuthStateTest(unittest.TestCase):
    def test_login_sets_state_parameter_and_secure_cookie(self):
        response = google_login()
        query = parse_qs(urlparse(response.headers["location"]).query)
        state = query["state"][0]
        cookie = response.headers["set-cookie"]

        self.assertGreaterEqual(len(state), 32)
        self.assertIn(f"{OAUTH_STATE_COOKIE}={state}", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Max-Age=600", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertIn("Secure", cookie)

    def test_callback_rejects_mismatched_state_before_external_request(self):
        with self.assertRaises(HTTPException) as context:
            google_callback(
                request=_request_with_cookie("expected-state"),
                code="authorization-code",
                state="different-state",
                db=None,
            )

        self.assertEqual(context.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
