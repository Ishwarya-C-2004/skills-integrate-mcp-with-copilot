import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app


class AuthenticationTests(unittest.TestCase):
    def make_request(self, token=None):
        headers = []
        if token is not None:
            headers.append(
                (
                    b"cookie",
                    f"{app.SESSION_COOKIE_NAME}={token}".encode(),
                )
            )
        return app.Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": headers,
            }
        )

    def test_password_hash_verifies_only_the_original_password(self):
        password_hash = app.hash_password("teacher-password")

        self.assertTrue(app.verify_password("teacher-password", password_hash))
        self.assertFalse(app.verify_password("wrong-password", password_hash))
        self.assertFalse(app.verify_password("teacher-password", "invalid"))

    def test_login_sets_http_only_session_cookie(self):
        app.teachers["test-teacher"] = app.hash_password("teacher-password")
        self.addCleanup(app.teachers.pop, "test-teacher", None)

        response = app.login(
            app.LoginRequest(username="test-teacher", password="teacher-password")
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f"{app.SESSION_COOKIE_NAME}=",
            response.headers["set-cookie"],
        )
        self.assertIn("httponly", response.headers["set-cookie"].lower())

    def test_session_token_is_signed_and_expires(self):
        app.teachers["test-teacher"] = app.hash_password("password")
        self.addCleanup(app.teachers.pop, "test-teacher", None)

        token = app.create_session_token("test-teacher")
        self.assertEqual(app.get_session_username(token), "test-teacher")

        payload, signature = token.split(".", 1)
        tampered_token = f"{payload}x.{signature}"
        self.assertIsNone(app.get_session_username(tampered_token))

        with patch.object(
            app.time,
            "time",
            return_value=app.time.time() + app.SESSION_TTL_SECONDS,
        ):
            self.assertIsNone(app.get_session_username(token))

    def test_roster_mutations_reject_missing_session(self):
        request = self.make_request()
        with self.assertRaises(app.HTTPException) as exception:
            app.signup_for_activity("Chess Club", "new-student@mergington.edu", request)

        self.assertEqual(exception.exception.status_code, 401)

        with self.assertRaises(app.HTTPException) as exception:
            app.unregister_from_activity(
                "Chess Club", "michael@mergington.edu", request
            )

        self.assertEqual(exception.exception.status_code, 401)

    def test_teacher_session_allows_roster_mutations(self):
        app.teachers["test-teacher"] = app.hash_password("password")
        self.addCleanup(app.teachers.pop, "test-teacher", None)
        request = self.make_request(app.create_session_token("test-teacher"))
        email = "new-student@mergington.edu"

        self.assertEqual(
            app.signup_for_activity("Chess Club", email, request),
            {"message": f"Signed up {email} for Chess Club"},
        )
        participants = app.activities["Chess Club"]["participants"]
        self.addCleanup(
            lambda: participants.remove(email) if email in participants else None
        )
        self.assertEqual(
            app.unregister_from_activity("Chess Club", email, request),
            {"message": f"Unregistered {email} from Chess Club"},
        )


if __name__ == "__main__":
    unittest.main()
