"""Isolated Microsoft federated auth. Synthetic OIDC is not actual-provider success."""

from __future__ import annotations

import federated_isolation  # noqa: F401  # federated-only process; must precede app imports

import json
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwt
from jwt.algorithms import RSAAlgorithm
from tinydb import Query

from app.access.permissions import INSUFFICIENT_DEPARTMENT_DETAIL
from app.core.security import (
    AUTH_METHOD_CLAIM,
    AUTH_METHOD_MICROSOFT,
    AUTH_METHOD_PASSWORD,
    create_access_token,
)
from app.db.tinydb import (
    federated_audit_table,
    federated_links_table,
    federated_oauth_tx_table,
    users_table,
)
from app.schemas.user import UserCreate, UserRole, UserUpdate
from app.services import federated_auth, internal_report_service, user_service
from app.services.federated_auth import (
    ALREADY_LINKED_ELSEWHERE_DETAIL,
    INACTIVE_DETAIL,
    LAST_METHOD_DETAIL,
    NOT_PROVISIONED_DETAIL,
    NOT_STAFF_DETAIL,
    NOT_TRADITIONAL_SESSION_DETAIL,
    UNLINKED_IDENTITY_DETAIL,
)
from app.services.federated_oidc import (
    FederatedOidcError,
    IDENTITY_TOKEN_INVALID_DETAIL,
    REDIRECT_MISMATCH_DETAIL,
    STATE_MISMATCH_DETAIL,
    TENANT_MISMATCH_DETAIL,
    UNSUPPORTED_PROVIDER_DETAIL,
    validate_id_token,
)
from app.services.platform_access_seed import ensure_roles_and_departments
from conftest import TEST_PASSWORD

REDIRECT = "http://localhost:3000/auth/callback/microsoft"
MARCUS_EMAIL = "marcus.clinical@healthcore.example"
PRIYA_EMAIL = "priya.access@healthcore.example"
MARCUS_OID = "ms-oid-marcus-001"
UNKNOWN_OID = "ms-oid-unknown-999"
SEED_PASSWORD = TEST_PASSWORD
STATE_SECRET = "test-secret-key-32chars!!!!"
CLIENT_ID = "test-client"
TENANT_ID = "test-tenant"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
PRIYA_OID = "ms-oid-priya-001"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = "federated-test-key"


def _public_jwk(public_key, kid: str) -> dict:
    body = json.loads(RSAAlgorithm.to_jwk(public_key))
    body["kid"] = kid
    body["use"] = "sig"
    body["alg"] = "RS256"
    return body


_TEST_JWKS = {"keys": [_public_jwk(_PRIVATE_KEY.public_key(), _KID)]}


@pytest.fixture(autouse=True)
def _inject_trusted_process_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.federated_oidc.fetch_microsoft_jwks",
        lambda: _TEST_JWKS,
    )


def _signed_id_token(
    oid: str,
    email: str,
    *,
    nonce: str,
    tenant: str = TENANT_ID,
    audience: str = CLIENT_ID,
    issuer: str | None = None,
    exp_delta: int = 300,
    nbf_delta: int = -30,
    iat_delta: int = -20,
    kid: str = _KID,
    private_key=_PRIVATE_KEY,
    extra_claims: dict | None = None,
    extra_headers: dict | None = None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "oid": oid,
        "sub": oid,
        "tid": tenant,
        "preferred_username": email,
        "email": email,
        "aud": audience,
        "iss": issuer if issuer is not None else ISSUER,
        "iat": now + timedelta(seconds=iat_delta),
        "nbf": now + timedelta(seconds=nbf_delta),
        "exp": now + timedelta(seconds=exp_delta),
        "nonce": nonce,
    }
    if extra_claims:
        payload.update(extra_claims)
    headers = {"kid": kid}
    if extra_headers:
        headers.update(extra_headers)
    return pyjwt.encode(payload, private_key, algorithm="RS256", headers=headers)


def _state_claims(state: str) -> dict:
    return jwt.decode(state, STATE_SECRET, algorithms=["HS256"])


def _nonce(started) -> str:
    return str(_state_claims(started.json()["state"])["oidc_nonce"])


def _set_user_flags(
    user_id: str,
    *,
    audience: str = "staff",
    provisioned_by_it: bool = True,
    has_password: bool = True,
) -> None:
    users_table().update(
        {
            "audience": audience,
            "provisioned_by_it": provisioned_by_it,
            "has_password": has_password,
        },
        Query().id == user_id,
    )


def _drop_user_field(user_id: str, field: str) -> None:
    def mutate(doc):
        doc.pop(field, None)
        return doc

    users_table().update(mutate, Query().id == user_id)


def _install_briefing_fixtures() -> dict[str, object]:
    ensure_roles_and_departments()
    marcus = user_service.create_user(
        UserCreate(email=MARCUS_EMAIL, password=SEED_PASSWORD, name="Dr. Marcus Reid"),
        role=UserRole.supervisor,
        department_id="clinical_operations",
    )
    priya = user_service.create_user(
        UserCreate(email=PRIYA_EMAIL, password=SEED_PASSWORD, name="Priya Nair"),
        role=UserRole.employee,
        department_id="patient_experience",
    )
    tom = user_service.create_user(
        UserCreate(email="tom.billing@healthcore.example", password=SEED_PASSWORD),
        role=UserRole.supervisor,
        department_id="revenue_cycle",
    )
    _set_user_flags(marcus.id)
    _set_user_flags(priya.id)
    _set_user_flags(tom.id)
    federated_links_table().insert(
        {
            "id": "fixture-marcus-link",
            "user_id": marcus.id,
            "provider": "microsoft",
            "provider_user_id": MARCUS_OID,
            "email_at_link_time": MARCUS_EMAIL,
            "linked_at": "2026-01-01T00:00:00+00:00",
            "provisioned_by_it": True,
        }
    )
    clinical_report = internal_report_service.create_report(
        department_id="clinical_operations",
        title="Austin North — documentation time spike",
        body="Average documentation minutes per encounter up 12% week over week. No patient identifiers.",
        created_by=marcus.id,
    )
    revenue_report = internal_report_service.create_report(
        department_id="revenue_cycle",
        title="US denial rate — coding mismatch cluster",
        body="14% denial rate driven by three CPT mismatch patterns. No member IDs in this note.",
        created_by=tom.id,
    )
    return {
        "marcus": marcus,
        "priya": priya,
        "tom": tom,
        "clinical_report": clinical_report,
        "revenue_report": revenue_report,
    }


def _password_headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": SEED_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _start(client: TestClient, *, provider: str, purpose: str, headers=None, redirect_uri: str = REDIRECT):
    return client.post(
        f"/auth/federated/{provider}/start",
        json={"purpose": purpose, "redirect_uri": redirect_uri},
        headers=headers,
    )


def _callback(
    client: TestClient,
    *,
    provider: str,
    code: str,
    state: str,
    tx_binding: str,
    headers=None,
    redirect_uri: str = REDIRECT,
):
    return client.post(
        f"/auth/federated/{provider}/callback",
        json={
            "code": code,
            "state": state,
            "redirect_uri": redirect_uri,
            "tx_binding": tx_binding,
        },
        headers=headers,
    )


def _complete_started(
    client: TestClient,
    started,
    *,
    oid: str,
    email: str,
    headers=None,
    **token_kwargs,
):
    body = started.json()
    code = _signed_id_token(oid, email, nonce=_nonce(started), **token_kwargs)
    return _callback(
        client,
        provider="microsoft",
        code=code,
        state=body["state"],
        tx_binding=body["tx_binding"],
        headers=headers,
    )


def test_authorized_staff_can_link_microsoft(client: TestClient) -> None:
    fixtures = _install_briefing_fixtures()
    headers = _password_headers(client, PRIYA_EMAIL)
    started = _start(client, provider="microsoft", purpose="link", headers=headers)
    assert started.status_code == 200, started.text
    assert started.json()["tx_binding"]
    completed = _complete_started(
        client,
        started,
        oid=PRIYA_OID,
        email=PRIYA_EMAIL,
        headers=headers,
    )
    assert completed.status_code == 200, completed.text
    body = completed.json()
    assert body["linked"] is True
    assert body["link"]["provider"] == "microsoft"
    assert body["link"]["provider_user_id"] == PRIYA_OID
    assert body["link"]["email_at_link_time"] == PRIYA_EMAIL
    assert body["link"]["provisioned_by_it"] is True
    events = [row for row in federated_auth.list_audit_events() if row["event"] == "federated_link"]
    assert events
    assert events[-1]["user_id"] == fixtures["priya"].id
    assert events[-1]["provider"] == "microsoft"
    assert events[-1]["provider_user_id"] == PRIYA_OID
    assert "timestamp" in events[-1]


def test_unauthenticated_patient_and_non_it_cannot_link(client: TestClient) -> None:
    _install_briefing_fixtures()
    unauthenticated = _start(client, provider="microsoft", purpose="link")
    assert unauthenticated.status_code == 401

    patient = user_service.create_user(
        UserCreate(email="patient.portal@healthcore.example", password=SEED_PASSWORD),
        role=UserRole.employee,
        department_id="patient_experience",
    )
    _set_user_flags(patient.id, audience="patient", provisioned_by_it=False)
    patient_headers = _password_headers(client, "patient.portal@healthcore.example")
    patient_start = _start(client, provider="microsoft", purpose="link", headers=patient_headers)
    assert patient_start.status_code == 403
    assert patient_start.json()["detail"] == NOT_STAFF_DETAIL

    unprovisioned = user_service.create_user(
        UserCreate(email="temp.staff@healthcore.example", password=SEED_PASSWORD),
        role=UserRole.employee,
        department_id="technology",
    )
    _set_user_flags(unprovisioned.id, provisioned_by_it=False)
    unprovisioned_headers = _password_headers(client, "temp.staff@healthcore.example")
    blocked = _start(client, provider="microsoft", purpose="link", headers=unprovisioned_headers)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == NOT_PROVISIONED_DETAIL


def test_missing_false_and_malformed_eligibility_rejected(client: TestClient) -> None:
    fixtures = _install_briefing_fixtures()
    priya_id = fixtures["priya"].id

    _drop_user_field(priya_id, "audience")
    missing_audience = _start(
        client, provider="microsoft", purpose="link", headers=_password_headers(client, PRIYA_EMAIL)
    )
    assert missing_audience.status_code == 403
    assert missing_audience.json()["detail"] == NOT_STAFF_DETAIL

    _set_user_flags(priya_id, audience="contractor")
    unknown_audience = _start(
        client, provider="microsoft", purpose="link", headers=_password_headers(client, PRIYA_EMAIL)
    )
    assert unknown_audience.status_code == 403
    assert unknown_audience.json()["detail"] == NOT_STAFF_DETAIL

    _set_user_flags(priya_id, audience="staff", provisioned_by_it=True)
    _drop_user_field(priya_id, "provisioned_by_it")
    missing_provisioning = _start(
        client, provider="microsoft", purpose="link", headers=_password_headers(client, PRIYA_EMAIL)
    )
    assert missing_provisioning.status_code == 403
    assert missing_provisioning.json()["detail"] == NOT_PROVISIONED_DETAIL

    users_table().update({"provisioned_by_it": "true"}, Query().id == priya_id)
    malformed_provisioning = _start(
        client, provider="microsoft", purpose="link", headers=_password_headers(client, PRIYA_EMAIL)
    )
    assert malformed_provisioning.status_code == 403
    assert malformed_provisioning.json()["detail"] == NOT_PROVISIONED_DETAIL

    _set_user_flags(priya_id, audience="staff", provisioned_by_it=True)
    eligible = _start(
        client, provider="microsoft", purpose="link", headers=_password_headers(client, PRIYA_EMAIL)
    )
    assert eligible.status_code == 200, eligible.text


def test_traditional_session_required_to_link(client: TestClient) -> None:
    fixtures = _install_briefing_fixtures()
    password_headers = _password_headers(client, PRIYA_EMAIL)
    password_token = password_headers["Authorization"].removeprefix("Bearer ")
    password_claims = jwt.decode(password_token, STATE_SECRET, algorithms=["HS256"])
    assert password_claims[AUTH_METHOD_CLAIM] == AUTH_METHOD_PASSWORD
    started = _start(client, provider="microsoft", purpose="link", headers=password_headers)
    linked = _complete_started(
        client, started, oid=PRIYA_OID, email=PRIYA_EMAIL, headers=password_headers
    )
    assert linked.status_code == 200, linked.text

    federated_start = _start(client, provider="microsoft", purpose="login")
    federated_login = _complete_started(
        client, federated_start, oid=PRIYA_OID, email=PRIYA_EMAIL
    )
    assert federated_login.status_code == 200, federated_login.text
    federated_token = federated_login.json()["access_token"]
    federated_claims = jwt.decode(federated_token, STATE_SECRET, algorithms=["HS256"])
    assert federated_claims[AUTH_METHOD_CLAIM] == AUTH_METHOD_MICROSOFT
    federated_headers = {"Authorization": f"Bearer {federated_token}"}
    me = client.get("/auth/me", headers=federated_headers)
    assert me.status_code == 200
    blocked_start = _start(
        client, provider="microsoft", purpose="link", headers=federated_headers
    )
    assert blocked_start.status_code == 403
    assert blocked_start.json()["detail"] == NOT_TRADITIONAL_SESSION_DETAIL

    unknown_headers = {
        "Authorization": f"Bearer {create_access_token(subject=fixtures['priya'].id)}"
    }
    unknown_me = client.get("/auth/me", headers=unknown_headers)
    assert unknown_me.status_code == 200
    unknown_start = _start(
        client, provider="microsoft", purpose="link", headers=unknown_headers
    )
    assert unknown_start.status_code == 403
    assert unknown_start.json()["detail"] == NOT_TRADITIONAL_SESSION_DETAIL

    started_traditional = _start(
        client, provider="microsoft", purpose="link", headers=password_headers
    )
    completed_with_federated = _complete_started(
        client,
        started_traditional,
        oid="ms-oid-priya-other",
        email=PRIYA_EMAIL,
        headers=federated_headers,
    )
    assert completed_with_federated.status_code == 403
    assert completed_with_federated.json()["detail"] == NOT_TRADITIONAL_SESSION_DETAIL


def test_duplicate_microsoft_identity_is_not_reassigned(client: TestClient) -> None:
    fixtures = _install_briefing_fixtures()
    headers = _password_headers(client, PRIYA_EMAIL)
    started = _start(client, provider="microsoft", purpose="link", headers=headers)
    completed = _complete_started(
        client, started, oid=MARCUS_OID, email=PRIYA_EMAIL, headers=headers
    )
    assert completed.status_code == 409
    assert completed.json()["detail"] == ALREADY_LINKED_ELSEWHERE_DETAIL
    link = federated_links_table().get(Query().provider_user_id == MARCUS_OID)
    assert link["user_id"] == fixtures["marcus"].id
    priya_link = federated_links_table().get(Query().user_id == fixtures["priya"].id)
    assert priya_link is None


def test_linked_microsoft_login_matches_password_session_and_department_rules(
    client: TestClient,
) -> None:
    fixtures = _install_briefing_fixtures()
    started = _start(client, provider="microsoft", purpose="login")
    assert started.status_code == 200, started.text
    completed = _complete_started(client, started, oid=MARCUS_OID, email=MARCUS_EMAIL)
    assert completed.status_code == 200, completed.text
    token = completed.json()["access_token"]
    claims = jwt.decode(token, STATE_SECRET, algorithms=["HS256"])
    assert claims["sub"] == fixtures["marcus"].id
    assert "exp" in claims
    assert claims[AUTH_METHOD_CLAIM] == AUTH_METHOD_MICROSOFT
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "supervisor"
    assert me.json()["department_id"] == "clinical_operations"
    own = client.get(
        f"/internal-reports/{fixtures['clinical_report'].id}",
        headers=headers,
    )
    other = client.get(
        f"/internal-reports/{fixtures['revenue_report'].id}",
        headers=headers,
    )
    assert own.status_code == 200
    assert other.status_code == 403
    assert other.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL
    success = [
        row
        for row in federated_auth.list_audit_events()
        if row["event"] == "federated_login_success"
    ]
    assert success[-1]["user_id"] == fixtures["marcus"].id
    assert success[-1]["provider_user_id"] == MARCUS_OID


def test_unknown_microsoft_identity_rejected_creates_zero_users(client: TestClient) -> None:
    _install_briefing_fixtures()
    before = federated_auth.user_count()
    started = _start(client, provider="microsoft", purpose="login")
    completed = _complete_started(
        client, started, oid=UNKNOWN_OID, email="unknown.staff@healthcore.example"
    )
    assert completed.status_code == 401
    assert completed.json()["detail"] == UNLINKED_IDENTITY_DETAIL
    assert federated_auth.user_count() == before
    rejected = [
        row
        for row in federated_auth.list_audit_events()
        if row["event"] == "federated_login_rejected"
    ]
    assert rejected
    assert rejected[-1]["user_id"] is None
    assert rejected[-1]["provider"] == "microsoft"
    assert rejected[-1]["provider_user_id"] == UNKNOWN_OID
    assert "timestamp" in rejected[-1]
    assert users_table().get(Query().email == "unknown.staff@healthcore.example") is None


def test_inactive_linked_user_login_is_rejected_and_audited(client: TestClient) -> None:
    fixtures = _install_briefing_fixtures()
    updated = user_service.update_user(fixtures["marcus"].id, UserUpdate(is_active=False))
    assert updated is not None
    assert updated.is_active is False
    before = federated_auth.user_count()
    started = _start(client, provider="microsoft", purpose="login")
    completed = _complete_started(client, started, oid=MARCUS_OID, email=MARCUS_EMAIL)
    assert completed.status_code == 401
    assert completed.json()["detail"] == INACTIVE_DETAIL
    assert federated_auth.user_count() == before
    rejected = [
        row
        for row in federated_auth.list_audit_events()
        if row["event"] == "federated_login_rejected"
    ]
    assert rejected
    assert rejected[-1]["user_id"] == fixtures["marcus"].id
    assert rejected[-1]["provider"] == "microsoft"
    assert rejected[-1]["provider_user_id"] == MARCUS_OID
    assert "timestamp" in rejected[-1]
    serialized = str(rejected[-1])
    assert "id_token" not in serialized
    assert "access_token" not in serialized


def test_oauth_transaction_binding_rejects_foreign_tampered_expired_and_replay(
    client: TestClient,
) -> None:
    fixtures = _install_briefing_fixtures()
    headers = _password_headers(client, PRIYA_EMAIL)
    other_headers = _password_headers(client, MARCUS_EMAIL)

    started = _start(client, provider="microsoft", purpose="login")
    foreign = _callback(
        client,
        provider="microsoft",
        code=_signed_id_token(MARCUS_OID, MARCUS_EMAIL, nonce=_nonce(started)),
        state=started.json()["state"],
        tx_binding="foreign-browser-binding",
    )
    assert foreign.status_code == 400
    assert foreign.json()["detail"] == "OAuth state is invalid"

    started_tamper = _start(client, provider="microsoft", purpose="login")
    tampered_state = started_tamper.json()["state"][:-4] + "abcd"
    tampered = _callback(
        client,
        provider="microsoft",
        code=_signed_id_token(MARCUS_OID, MARCUS_EMAIL, nonce=_nonce(started_tamper)),
        state=tampered_state,
        tx_binding=started_tamper.json()["tx_binding"],
    )
    assert tampered.status_code == 400
    assert tampered.json()["detail"] == STATE_MISMATCH_DETAIL

    started_expired = _start(client, provider="microsoft", purpose="login")
    jti = _state_claims(started_expired.json()["state"])["jti"]
    federated_oauth_tx_table().update(
        {"exp": (datetime.now(UTC) - timedelta(seconds=5)).isoformat()},
        Query().jti == jti,
    )
    expired = _complete_started(
        client, started_expired, oid=MARCUS_OID, email=MARCUS_EMAIL
    )
    assert expired.status_code == 400
    assert expired.json()["detail"] == "OAuth state is invalid"
    assert federated_links_table().get(Query().provider_user_id == MARCUS_OID)["user_id"] == fixtures["marcus"].id

    started_replay = _start(client, provider="microsoft", purpose="login")
    first = _complete_started(client, started_replay, oid=MARCUS_OID, email=MARCUS_EMAIL)
    assert first.status_code == 200, first.text
    replay = _complete_started(client, started_replay, oid=MARCUS_OID, email=MARCUS_EMAIL)
    assert replay.status_code == 400
    assert replay.json()["detail"] == "OAuth state is invalid"

    priya_start = _start(client, provider="microsoft", purpose="link", headers=headers)
    foreign_user = _complete_started(
        client,
        priya_start,
        oid=PRIYA_OID,
        email=PRIYA_EMAIL,
        headers=other_headers,
    )
    assert foreign_user.status_code == 400
    assert foreign_user.json()["detail"] == "OAuth state is invalid"
    assert federated_links_table().get(Query().user_id == fixtures["priya"].id) is None


def test_signed_oidc_token_validation_cases() -> None:
    valid_nonce = "nonce-valid"
    valid = _signed_id_token(MARCUS_OID, MARCUS_EMAIL, nonce=valid_nonce)
    identity = validate_id_token(valid, expected_nonce=valid_nonce)
    assert identity.provider_user_id == MARCUS_OID
    assert identity.email == MARCUS_EMAIL

    bad_sig = _signed_id_token(
        MARCUS_OID, MARCUS_EMAIL, nonce=valid_nonce, private_key=_OTHER_KEY
    )
    with pytest.raises(FederatedOidcError) as bad_sig_exc:
        validate_id_token(bad_sig, expected_nonce=valid_nonce)
    assert bad_sig_exc.value.detail == IDENTITY_TOKEN_INVALID_DETAIL

    bad_iss = _signed_id_token(
        MARCUS_OID,
        MARCUS_EMAIL,
        nonce=valid_nonce,
        issuer="https://login.microsoftonline.com/other-tenant/v2.0",
    )
    with pytest.raises(FederatedOidcError) as bad_iss_exc:
        validate_id_token(bad_iss, expected_nonce=valid_nonce)
    assert bad_iss_exc.value.detail == IDENTITY_TOKEN_INVALID_DETAIL

    bad_aud = _signed_id_token(
        MARCUS_OID, MARCUS_EMAIL, nonce=valid_nonce, audience="other-client"
    )
    with pytest.raises(FederatedOidcError) as bad_aud_exc:
        validate_id_token(bad_aud, expected_nonce=valid_nonce)
    assert bad_aud_exc.value.detail == IDENTITY_TOKEN_INVALID_DETAIL

    bad_time = _signed_id_token(
        MARCUS_OID, MARCUS_EMAIL, nonce=valid_nonce, exp_delta=-60
    )
    with pytest.raises(FederatedOidcError) as bad_time_exc:
        validate_id_token(bad_time, expected_nonce=valid_nonce)
    assert bad_time_exc.value.detail == IDENTITY_TOKEN_INVALID_DETAIL

    bad_nonce = _signed_id_token(MARCUS_OID, MARCUS_EMAIL, nonce="other-nonce")
    with pytest.raises(FederatedOidcError) as bad_nonce_exc:
        validate_id_token(bad_nonce, expected_nonce=valid_nonce)
    assert bad_nonce_exc.value.detail == IDENTITY_TOKEN_INVALID_DETAIL

    jku_token = _signed_id_token(
        MARCUS_OID,
        MARCUS_EMAIL,
        nonce=valid_nonce,
        extra_headers={"jku": "https://attacker.example/jwks"},
    )
    with pytest.raises(FederatedOidcError) as jku_exc:
        validate_id_token(jku_token, expected_nonce=valid_nonce)
    assert jku_exc.value.detail == IDENTITY_TOKEN_INVALID_DETAIL

    other_tid = _signed_id_token(
        MARCUS_OID, MARCUS_EMAIL, nonce=valid_nonce, tenant="other-tenant"
    )
    with pytest.raises(FederatedOidcError) as tid_exc:
        validate_id_token(other_tid, expected_nonce=valid_nonce)
    assert tid_exc.value.detail == TENANT_MISMATCH_DETAIL


def test_last_method_unlink_refused_and_password_holder_may_unlink(
    client: TestClient,
) -> None:
    fixtures = _install_briefing_fixtures()
    _set_user_flags(fixtures["marcus"].id, has_password=False)
    marcus_headers = _password_headers(client, MARCUS_EMAIL)
    refused = client.delete("/auth/federated/microsoft", headers=marcus_headers)
    assert refused.status_code == 409
    assert refused.json()["detail"] == LAST_METHOD_DETAIL
    assert federated_links_table().get(Query().user_id == fixtures["marcus"].id) is not None

    priya_headers = _password_headers(client, PRIYA_EMAIL)
    started = _start(client, provider="microsoft", purpose="link", headers=priya_headers)
    linked = _complete_started(
        client,
        started,
        oid="ms-oid-priya-002",
        email=PRIYA_EMAIL,
        headers=priya_headers,
    )
    assert linked.status_code == 200
    status_before = client.get("/auth/federated/microsoft/status", headers=priya_headers)
    assert status_before.json()["can_unlink"] is True
    unlinked = client.delete("/auth/federated/microsoft", headers=priya_headers)
    assert unlinked.status_code == 200, unlinked.text
    assert unlinked.json()["linked"] is False
    unlink_events = [
        row for row in federated_auth.list_audit_events() if row["event"] == "federated_unlink"
    ]
    assert unlink_events[-1]["user_id"] == fixtures["priya"].id


def test_state_redirect_tenant_and_unsupported_provider_rejected(client: TestClient) -> None:
    _install_briefing_fixtures()
    headers = _password_headers(client, PRIYA_EMAIL)
    google = _start(client, provider="google", purpose="login")
    assert google.status_code == 400
    assert google.json()["detail"] == UNSUPPORTED_PROVIDER_DETAIL

    bad_redirect = _start(
        client,
        provider="microsoft",
        purpose="login",
        redirect_uri="https://evil.example/callback",
    )
    assert bad_redirect.status_code == 400
    assert bad_redirect.json()["detail"] == REDIRECT_MISMATCH_DETAIL

    started = _start(client, provider="microsoft", purpose="login")
    mismatched_state = _callback(
        client,
        provider="microsoft",
        code=_signed_id_token(MARCUS_OID, MARCUS_EMAIL, nonce=_nonce(started)),
        state="not-a-valid-state",
        tx_binding=started.json()["tx_binding"],
    )
    assert mismatched_state.status_code == 400
    assert mismatched_state.json()["detail"] == STATE_MISMATCH_DETAIL

    wrong_tenant = _complete_started(
        client, started, oid=MARCUS_OID, email=MARCUS_EMAIL, tenant="other-tenant"
    )
    assert wrong_tenant.status_code == 400
    assert wrong_tenant.json()["detail"] == TENANT_MISMATCH_DETAIL

    link_started = _start(client, provider="microsoft", purpose="link", headers=headers)
    wrong_uri = _callback(
        client,
        provider="microsoft",
        code=_signed_id_token(
            "ms-oid-priya-003", PRIYA_EMAIL, nonce=_nonce(link_started)
        ),
        state=link_started.json()["state"],
        tx_binding=link_started.json()["tx_binding"],
        headers=headers,
        redirect_uri="http://localhost:3000/auth/callback/other",
    )
    assert wrong_uri.status_code == 400


def test_audit_records_required_fields_and_omits_secrets(client: TestClient) -> None:
    _install_briefing_fixtures()
    started = _start(client, provider="microsoft", purpose="login")
    _complete_started(
        client, started, oid=UNKNOWN_OID, email="unknown.staff@healthcore.example"
    )
    for row in federated_audit_table().all():
        assert "timestamp" in row
        assert "event" in row
        assert "provider" in row
        assert "provider_user_id" in row
        assert "user_id" in row
        serialized = str(row)
        assert "test-secret" not in serialized
        assert "access_token" not in row
        assert "refresh_token" not in row
        assert "id_token" not in row
        assert "hashed_password" not in row
        assert "code" not in row
        assert "tx_binding" not in row
        assert "state" not in row


@pytest.mark.parametrize(
    "case, reason",
    [
        ("invalid_state", "invalid_state"),
        ("expired_state", "invalid_state"),
        ("foreign_binding", "invalid_transaction"),
        ("expired_transaction", "invalid_transaction"),
        ("replayed_transaction", "invalid_transaction"),
        ("redirect_mismatch", "invalid_transaction"),
        ("nonce_mismatch", "identity_rejected"),
        ("tenant_mismatch", "identity_rejected"),
        ("signature_mismatch", "identity_rejected"),
        ("audience_mismatch", "identity_rejected"),
        ("issuer_mismatch", "identity_rejected"),
        ("expired_identity", "identity_rejected"),
        ("unsupported_provider", "identity_rejected"),
        ("start_provider", "authorization_start_rejected"),
        ("start_redirect", "authorization_start_rejected"),
    ],
)
def test_early_login_rejections_are_sanitized_and_audited_once(
    client: TestClient, case: str, reason: str,
) -> None:
    _install_briefing_fixtures()
    started = _start(client, provider="microsoft", purpose="login")
    body = started.json()
    claims = _state_claims(body["state"])
    kwargs = {}
    if case == "nonce_mismatch":
        kwargs["nonce"] = "untrusted-nonce-sentinel"
    if case == "tenant_mismatch":
        kwargs["tenant"] = "untrusted-tenant-sentinel"
    if case == "signature_mismatch":
        kwargs["private_key"] = _OTHER_KEY
    if case == "audience_mismatch":
        kwargs["audience"] = "untrusted-audience-sentinel"
    if case == "issuer_mismatch":
        kwargs["issuer"] = "https://untrusted-issuer-sentinel.example"
    if case == "expired_identity":
        kwargs["exp_delta"] = -60
    code = _signed_id_token(
        "untrusted-oid-sentinel", "untrusted-email-sentinel@example.test",
        **({"nonce": _nonce(started)} | kwargs),
    )
    state = body["state"]
    binding = body["tx_binding"]
    redirect = REDIRECT
    provider = "microsoft"
    if case == "invalid_state":
        state = "untrusted-state-sentinel"
    if case == "expired_state":
        claims["exp"] = datetime.now(UTC) - timedelta(seconds=60)
        state = jwt.encode(claims, STATE_SECRET, algorithm="HS256")
    if case == "foreign_binding":
        binding = "untrusted-binding-sentinel"
    if case == "expired_transaction":
        federated_oauth_tx_table().update(
            {"exp": (datetime.now(UTC) - timedelta(seconds=60)).isoformat()},
            Query().jti == claims["jti"],
        )
    if case == "replayed_transaction":
        first = _complete_started(client, started, oid=MARCUS_OID, email=MARCUS_EMAIL)
        assert first.status_code == 200
    if case == "redirect_mismatch":
        redirect = "https://untrusted-redirect-sentinel.example/callback"
    if case == "unsupported_provider":
        provider = "untrusted-provider-sentinel"
    before = len(federated_auth.list_audit_events())
    users_before = federated_auth.user_count()
    links_before = [dict(row) for row in federated_links_table().all()]
    if case.startswith("start_"):
        response = _start(
            client,
            provider="untrusted-provider-sentinel" if case == "start_provider" else "microsoft",
            purpose="login",
            redirect_uri="https://untrusted-redirect-sentinel.example" if case == "start_redirect" else REDIRECT,
        )
    else:
        response = _callback(client, provider=provider, code=code, state=state,
                             tx_binding=binding, redirect_uri=redirect)
    assert response.status_code == 400
    assert "access_token" not in response.json()
    events = federated_auth.list_audit_events()[before:]
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "federated_login_rejected"
    assert event["reason"] == reason
    assert event["provider"] == ("unsupported" if case in {"unsupported_provider", "start_provider"} else "microsoft")
    assert event["provider_user_id"] is None
    assert event["user_id"] is None
    assert set(event) == {"id", "timestamp", "event", "provider", "provider_user_id", "user_id", "reason"}
    assert datetime.fromisoformat(event["timestamp"])
    serialized = json.dumps(event)
    for value in [code, state, binding, claims["oidc_nonce"], claims["jti"], STATE_SECRET, CLIENT_ID, TENANT_ID, REDIRECT]:
        assert value not in serialized
    assert "untrusted-" not in serialized
    assert federated_auth.user_count() == users_before
    assert [dict(row) for row in federated_links_table().all()] == links_before
