"""POST /auth/login — credential verification and JWT issuance."""

from __future__ import annotations

from jose import jwt

from tests.conftest import TEST_EMAIL, TEST_PASSWORD


def _login(client, *, username: str, password: str):
    return client.post("/auth/login", data={"username": username, "password": password})


def test_login_issues_jwt_with_user_sub_and_exp(client, seeded_user) -> None:
    response = _login(client, username=TEST_EMAIL, password=TEST_PASSWORD)

    assert response.status_code == 200
    token = response.json()["access_token"]
    assert token

    claims = jwt.get_unverified_claims(token)
    assert claims["sub"] == seeded_user.id
    assert "exp" in claims


def test_login_accepts_mixed_case_email(client, seeded_user) -> None:
    # create_user stores email.lower(); lookup also lowercases, so mixed-case login must succeed.
    response = _login(client, username="Alice@HealthCore.com", password=TEST_PASSWORD)

    assert response.status_code == 200
    claims = jwt.get_unverified_claims(response.json()["access_token"])
    assert claims["sub"] == seeded_user.id


def test_login_rejects_wrong_password(client, seeded_user) -> None:
    response = _login(client, username=TEST_EMAIL, password="WrongPass1!")

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
    assert "access_token" not in response.json()


def test_login_rejects_unknown_email(client, seeded_user) -> None:
    response = _login(client, username="nobody@healthcore.com", password=TEST_PASSWORD)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
    assert "access_token" not in response.json()


def test_login_rejects_inactive_user(client, inactive_user) -> None:
    response = _login(client, username=TEST_EMAIL, password=TEST_PASSWORD)

    assert response.status_code == 401
    assert response.json()["detail"] == "Inactive user"
    assert "access_token" not in response.json()
