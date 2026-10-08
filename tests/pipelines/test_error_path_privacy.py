"""Error-path privacy regressions for agent, knowledge, and global handlers.

Synthetic markers only. Formatter.format is the log check. getMessage() alone
is not enough. These tests do not prove every future failure path.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

MARKER = "SYNTH_ERR_PATH_714"
FORMATTER = logging.Formatter("%(name)s %(levelname)s %(message)s")
KNOWLEDGE_GENERIC = "The knowledge assistant could not generate an answer right now."
AGENT_GENERIC = "The knowledge assistant could not generate an answer right now."
KNOWLEDGE_BAD_REQUEST = "The knowledge request could not be processed."
UNEXPECTED = "An unexpected error occurred. Please try again."


class _FullCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[str, str, bool]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.rows.append(
            (record.name, FORMATTER.format(record), record.exc_info is not None)
        )


def _formatted_blob(capture: _FullCapture) -> str:
    return "\n".join(text for _name, text, _has_exc in capture.rows)


def _attach(logger_name: str) -> tuple[logging.Logger, _FullCapture, bool]:
    logger = logging.getLogger(logger_name)
    capture = _FullCapture()
    logger.addHandler(capture)
    logger.setLevel(logging.ERROR)
    previous = logger.propagate
    logger.propagate = False
    return logger, capture, previous


def _detach(logger: logging.Logger, capture: _FullCapture, previous: bool) -> None:
    logger.removeHandler(capture)
    logger.propagate = previous


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'app.db').as_posix()}")
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("SECRET_KEY", "error-path-privacy-test-key")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    from app.core.config import get_settings
    from app.db.database import reset_engine_for_tests
    from app.db.tinydb import reset_db_for_tests
    from app.main import app

    get_settings.cache_clear()
    reset_db_for_tests()
    reset_engine_for_tests()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    reset_engine_for_tests()
    reset_db_for_tests()
    get_settings.cache_clear()


def test_knowledge_unexpected_failure_omits_exception_text_from_formatted_logs(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.routers.knowledge as knowledge_router

    monkeypatch.setattr(
        knowledge_router,
        "pipeline_query",
        lambda _question: (_ for _ in ()).throw(RuntimeError(MARKER)),
    )
    logger, capture, previous = _attach("app.routers.knowledge")
    try:
        response = api_client.post(
            "/knowledge/query",
            json={"question": "How long does an internal referral take?"},
        )
    finally:
        _detach(logger, capture, previous)

    assert response.status_code == 502
    assert response.json()["detail"] == KNOWLEDGE_GENERIC
    assert MARKER not in response.text
    blob = _formatted_blob(capture)
    assert capture.rows
    assert all(not has_exc for _name, _text, has_exc in capture.rows)
    assert MARKER not in blob
    assert "Traceback (most recent call last)" not in blob


def test_knowledge_value_error_returns_a_fixed_detail(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.routers.knowledge as knowledge_router

    monkeypatch.setattr(
        knowledge_router,
        "pipeline_query",
        lambda _question: (_ for _ in ()).throw(ValueError(MARKER)),
    )
    response = api_client.post(
        "/knowledge/query",
        json={"question": "How long does an internal referral take?"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == KNOWLEDGE_BAD_REQUEST
    assert MARKER not in response.text


def test_agent_unexpected_failure_omits_exception_text_from_formatted_logs(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.routers.agent as agent_router

    monkeypatch.setattr(
        agent_router,
        "run_support_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(MARKER)),
    )
    logger, capture, previous = _attach("app.routers.agent")
    try:
        response = api_client.post(
            "/agent/query",
            json={"question": "How long does an internal referral take?"},
        )
    finally:
        _detach(logger, capture, previous)

    assert response.status_code == 502
    assert response.json()["detail"] == AGENT_GENERIC
    assert MARKER not in response.text
    blob = _formatted_blob(capture)
    assert capture.rows
    assert all(not has_exc for _name, _text, has_exc in capture.rows)
    assert MARKER not in blob
    assert "Traceback (most recent call last)" not in blob


def test_non_manager_validation_response_omits_request_input(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/knowledge/query",
        json={"question": [MARKER]},
    )
    assert response.status_code == 422
    body = response.json()
    assert MARKER not in response.text
    detail = body.get("detail")
    assert isinstance(detail, list)
    assert detail
    for item in detail:
        assert isinstance(item, dict)
        assert "input" not in item
        assert "ctx" not in item
        assert "type" in item
        assert "loc" in item
        assert "msg" in item
        assert MARKER not in str(item["msg"])
        assert MARKER not in str(item["loc"])


def _authenticate_supplier_request(api_client: TestClient) -> None:
    """Reach body validation. Anonymous supplier writes are 401 before this check."""
    from datetime import UTC, datetime

    from app.core.deps import get_current_user
    from app.schemas.user import UserInDB, UserRole

    api_client.app.dependency_overrides[get_current_user] = lambda: UserInDB(
        id="privacy-user",
        email="privacy@example.com",
        is_active=True,
        role=UserRole.user,
        created_at=datetime.now(UTC),
        hashed_password="not-used",
    )


def test_supplier_custom_validator_message_is_not_reflected(
    api_client: TestClient,
) -> None:
    """SupplierCreate.categories embeds rejected values in ValueError text."""
    _authenticate_supplier_request(api_client)
    response = api_client.post(
        "/suppliers",
        json={
            "name": "Synth Supplier",
            "country": "USA",
            "categories": [MARKER],
            "monthly_rate": 10.0,
            "currency": "USD",
            "status": "active",
        },
    )
    assert response.status_code == 422
    assert MARKER not in response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail
    assert detail[0]["type"] == "value_error"
    assert detail[0]["msg"] == "Invalid value."
    assert detail[0]["loc"] == ["body", "categories"]
    assert "input" not in detail[0]
    assert "ctx" not in detail[0]


def test_supplier_extra_field_key_is_redacted_from_loc(
    api_client: TestClient,
) -> None:
    """SupplierCreate forbids extras; the submitted key lands in loc."""
    _authenticate_supplier_request(api_client)
    response = api_client.post(
        "/suppliers",
        json={
            "name": "Synth Supplier",
            "country": "USA",
            "categories": ["medical_supplies"],
            "monthly_rate": 10.0,
            "currency": "USD",
            "status": "active",
            MARKER: "x",
        },
    )
    assert response.status_code == 422
    assert MARKER not in response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail
    assert detail[0]["type"] == "extra_forbidden"
    assert detail[0]["msg"] == "Unexpected field."
    assert detail[0]["loc"] == ["body", "*"]
    assert "input" not in detail[0]


def test_telemetry_validation_omits_input_and_submitted_keys(
    api_client: TestClient,
) -> None:
    """Telemetry validates manually; must still use public_validation_errors."""
    response = api_client.post(
        "/telemetry/events",
        json={
            "events": [
                {
                    "eventId": "e1",
                    "timestamp": "2026-10-07T00:00:00Z",
                    "sessionId": "s1",
                    "userId": None,
                    "event_type": "page_viewed",
                    "schemaVersion": "1",
                    "requestId": "r1",
                    "properties": {},
                    MARKER: "x",
                }
            ]
        },
    )
    assert response.status_code == 422
    assert MARKER not in response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail
    assert detail[0]["type"] == "extra_forbidden"
    assert detail[0]["msg"] == "Unexpected field."
    assert detail[0]["loc"] == ["events", 0, "*"]
    assert "input" not in detail[0]
    assert "ctx" not in detail[0]


def test_inventory_create_validation_omits_input_and_submitted_keys(
    api_client: TestClient,
) -> None:
    register = api_client.post(
        "/users",
        json={
            "email": "synth.errorpath.inventory@example.com",
            "password": "error-path-inventory-1",
        },
    )
    assert register.status_code in (200, 201)
    login = api_client.post(
        "/auth/login",
        data={
            "username": "synth.errorpath.inventory@example.com",
            "password": "error-path-inventory-1",
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    response = api_client.post(
        "/inventory/products",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Synth Supply",
            "sku": "SYNTH-SKU-1",
            "category": "ppe",
            "unit": "box",
            "country": "US",
            MARKER: "x",
        },
    )
    assert response.status_code == 422
    assert MARKER not in response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail
    assert detail[0]["type"] == "extra_forbidden"
    assert detail[0]["msg"] == "Unexpected field."
    assert detail[0]["loc"] == ["*"]
    assert "input" not in detail[0]


def test_public_validation_errors_redacts_custom_msg_and_dict_keys() -> None:
    from app.core.safe_errors import public_validation_errors

    custom_msg_shape = {
        "type": "value_error",
        "loc": ("body", "categories"),
        "msg": f"Value error, invalid categories: ['{MARKER}']; allowed: ['medical_supplies']",
        "input": [MARKER],
        "ctx": {"error": MARKER},
    }
    dict_key_shape = {
        "type": "int_parsing",
        "loc": ("body", "properties", MARKER),
        "msg": "Input should be a valid integer, unable to parse string as an integer",
        "input": "not-int",
    }
    sanitized = public_validation_errors([custom_msg_shape, dict_key_shape])
    assert sanitized == [
        {
            "type": "value_error",
            "loc": ["body", "categories"],
            "msg": "Invalid value.",
        },
        {
            "type": "int_parsing",
            "loc": ["body", "properties", "*"],
            "msg": "Expected an integer.",
        },
    ]
    assert MARKER not in str(sanitized)


def test_unhandled_exception_omits_exception_text_and_raw_url_path(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.main import app

    @app.get("/__error_path_privacy_probe/{token}")
    def _probe(token: str) -> dict[str, str]:
        raise RuntimeError(MARKER)

    logger, capture, previous = _attach("healthcore.api")
    try:
        response = api_client.get(f"/__error_path_privacy_probe/{MARKER}")
    finally:
        _detach(logger, capture, previous)
        app.router.routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/__error_path_privacy_probe/{token}"
        ]

    assert response.status_code == 500
    assert response.json()["message"] == UNEXPECTED
    assert MARKER not in response.text
    blob = _formatted_blob(capture)
    assert capture.rows
    assert all(not has_exc for _name, _text, has_exc in capture.rows)
    assert MARKER not in blob
    assert "Traceback (most recent call last)" not in blob
    assert "GET" in blob
    assert "/__error_path_privacy_probe/{token}" in blob
    assert f"/__error_path_privacy_probe/{MARKER}" not in blob


def test_safe_route_template_unmatched_when_no_route() -> None:
    from app.core.safe_errors import safe_route_template

    request = MagicMock()
    request.scope = {"route": None}
    assert safe_route_template(request) == "<unmatched>"

    request.scope = {}
    assert safe_route_template(request) == "<unmatched>"
