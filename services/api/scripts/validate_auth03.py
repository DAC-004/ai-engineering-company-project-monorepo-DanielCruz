"""AUTH-03 API validation against FastAPI TestClient (Resend mocked)."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

# Configure isolated settings before importing the app modules that cache Settings.
_tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
_tmp.close()
os.environ["SECRET_KEY"] = "validation-secret-key-32chars!!"
os.environ["TINYDB_PATH"] = _tmp.name
os.environ["PASSWORD_RESET_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["FRONTEND_BASE_URL"] = "http://localhost:3000"
os.environ["RESEND_API_KEY"] = "test-api-key"
os.environ["RESEND_FROM_EMAIL"] = "HealthCore <onboarding@resend.dev>"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import verify_password  # noqa: E402
from app.db.tinydb import password_reset_tokens_table, reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.services import user_service  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()


class Auth03ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        get_settings.cache_clear()
        reset_db_for_tests()
        Path(_tmp.name).write_text("{}", encoding="utf-8")
        self.client = TestClient(app)
        self.email = "reset.user@example.com"
        self.password = "old-password-1"
        register = self.client.post(
            "/users",
            json={"email": self.email, "password": self.password},
        )
        self.assertEqual(register.status_code, 201, register.text)

    def tearDown(self) -> None:
        reset_db_for_tests()

    def _login(self, password: str | None = None) -> str:
        response = self.client.post(
            "/auth/login",
            data={"username": self.email, "password": password or self.password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def test_forgot_password_unregistered_returns_200_without_leak(self) -> None:
        with patch(
            "app.services.email_service.send_password_reset_email"
        ) as send_email:
            response = self.client.post(
                "/auth/forgot-password",
                json={"email": "nobody@example.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["detail"],
            "If that address is registered, you'll receive a link shortly",
        )
        send_email.assert_not_called()

    def test_forgot_password_registered_sends_email_with_reset_link(self) -> None:
        with patch(
            "app.services.email_service.send_password_reset_email"
        ) as send_email:
            response = self.client.post(
                "/auth/forgot-password",
                json={"email": self.email},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["detail"],
            "If that address is registered, you'll receive a link shortly",
        )
        send_email.assert_called_once()
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["to_email"], self.email)
        self.assertIn("/reset-password?token=", kwargs["reset_url"])

    def test_reset_password_updates_hash_and_invalidates_token(self) -> None:
        captured: dict[str, str] = {}

        def capture_send(*, to_email: str, reset_url: str) -> None:
            captured["url"] = reset_url

        with patch(
            "app.services.email_service.send_password_reset_email",
            side_effect=capture_send,
        ):
            self.client.post("/auth/forgot-password", json={"email": self.email})

        token = captured["url"].split("token=", 1)[1]
        new_password = "new-password-9"
        reset = self.client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": new_password},
        )
        self.assertEqual(reset.status_code, 200, reset.text)

        user = user_service.get_user_by_email(self.email)
        assert user is not None
        self.assertTrue(verify_password(new_password, user.hashed_password))
        self.assertFalse(verify_password(self.password, user.hashed_password))

        reuse = self.client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "another-password-1"},
        )
        self.assertEqual(reuse.status_code, 400)

        login_old = self.client.post(
            "/auth/login",
            data={"username": self.email, "password": self.password},
        )
        self.assertEqual(login_old.status_code, 401)
        self.assertEqual(self._login(new_password)[:10], self._login(new_password)[:10])

    def test_reset_password_rejects_expired_token(self) -> None:
        captured: dict[str, str] = {}

        def capture_send(*, to_email: str, reset_url: str) -> None:
            captured["url"] = reset_url

        with patch(
            "app.services.email_service.send_password_reset_email",
            side_effect=capture_send,
        ):
            self.client.post("/auth/forgot-password", json={"email": self.email})

        token = captured["url"].split("token=", 1)[1]
        table = password_reset_tokens_table()
        row = table.all()[0]
        expired = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        table.update({"expires_at": expired}, doc_ids=[row.doc_id])

        response = self.client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "new-password-9"},
        )
        self.assertEqual(response.status_code, 400)

    def test_change_password_rejects_wrong_current(self) -> None:
        access = self._login()
        response = self.client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access}"},
            json={
                "current_password": "wrong-password",
                "new_password": "new-password-9",
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_change_password_success(self) -> None:
        access = self._login()
        new_password = "changed-password-1"
        response = self.client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access}"},
            json={
                "current_password": self.password,
                "new_password": new_password,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self._login(new_password) is not None, True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
