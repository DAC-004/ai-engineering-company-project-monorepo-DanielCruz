"""Microsoft OIDC helpers. Tokens are used only to read oid/email, then discarded.

Identity claims are trusted only after PyJWT validates signature, RS256, issuer,
audience, timestamps, and the transaction nonce against tenant JWKS configured
by this process. Token-controlled key URLs (jku/x5u) are ignored.

Synthetic mode never calls login.microsoftonline.com. Tests and isolated
processes inject trusted JWKS; they still run the same validate_id_token path.
Live Entra success is a separate verification and is not implied by synthetic
results.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx
import jwt as pyjwt
from jose import JWTError, jwt
from jwt import InvalidTokenError, PyJWK

from app.core.config import get_settings

STATE_TOKEN_TYPE = "federated_oauth_state"
UNSUPPORTED_PROVIDER_DETAIL = "Unsupported identity provider"
REDIRECT_MISMATCH_DETAIL = "OAuth redirect_uri is not allowlisted"
STATE_MISMATCH_DETAIL = "OAuth state is invalid"
TENANT_MISMATCH_DETAIL = "Microsoft tenant is not allowed"
MICROSOFT_NOT_CONFIGURED_DETAIL = "Microsoft identity is not configured"
IDENTITY_TOKEN_INVALID_DETAIL = "Microsoft identity token is invalid"
ALLOWED_ID_TOKEN_ALGORITHMS = ("RS256",)


class FederatedOidcError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class MicrosoftIdentity:
    provider_user_id: str
    email: str | None
    tenant_id: str | None


def allowlisted_redirect_uri() -> str:
    return get_settings().oauth_redirect_uri


def assert_allowlisted_redirect_uri(redirect_uri: str) -> None:
    if redirect_uri != allowlisted_redirect_uri():
        raise FederatedOidcError(REDIRECT_MISMATCH_DETAIL)


def microsoft_issuer(tenant: str) -> str:
    return f"https://login.microsoftonline.com/{tenant}/v2.0"


def microsoft_jwks_url(tenant: str) -> str:
    return f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"


def encode_oauth_state(
    *,
    purpose: str,
    redirect_uri: str,
    user_id: str | None,
    jti: str,
    oidc_nonce: str,
) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=10)
    payload = {
        "typ": STATE_TOKEN_TYPE,
        "purpose": purpose,
        "redirect_uri": redirect_uri,
        "uid": user_id,
        "jti": jti,
        "oidc_nonce": oidc_nonce,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_oauth_state(state: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            state, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise FederatedOidcError(STATE_MISMATCH_DETAIL) from exc
    if payload.get("typ") != STATE_TOKEN_TYPE:
        raise FederatedOidcError(STATE_MISMATCH_DETAIL)
    if not isinstance(payload.get("jti"), str) or not payload["jti"]:
        raise FederatedOidcError(STATE_MISMATCH_DETAIL)
    if not isinstance(payload.get("oidc_nonce"), str) or not payload["oidc_nonce"]:
        raise FederatedOidcError(STATE_MISMATCH_DETAIL)
    return payload


def build_authorization_url(
    *,
    provider: str,
    purpose: str,
    redirect_uri: str,
    state: str,
    oidc_nonce: str,
) -> str:
    if provider != "microsoft":
        raise FederatedOidcError(UNSUPPORTED_PROVIDER_DETAIL)
    assert_allowlisted_redirect_uri(redirect_uri)
    settings = get_settings()
    if settings.federated_oidc_mode == "synthetic":
        query = urlencode(
            {
                "state": state,
                "redirect_uri": redirect_uri,
                "purpose": purpose,
                "nonce": oidc_nonce,
            }
        )
        return f"http://127.0.0.1/synthetic-oidc/microsoft?{query}"

    tenant = (settings.microsoft_tenant_id or "").strip()
    client_id = (settings.microsoft_client_id or "").strip()
    if not tenant or not client_id:
        raise FederatedOidcError(MICROSOFT_NOT_CONFIGURED_DETAIL, status_code=503)
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "scope": "openid profile email",
            "state": state,
            "nonce": oidc_nonce,
        }
    )
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?{query}"


def fetch_microsoft_jwks() -> dict:
    """Load tenant JWKS from process configuration, never from token-controlled URLs."""
    settings = get_settings()
    tenant = (settings.microsoft_tenant_id or "").strip()
    if not tenant:
        raise FederatedOidcError(MICROSOFT_NOT_CONFIGURED_DETAIL, status_code=503)
    if settings.federated_oidc_mode == "synthetic":
        # Process-configured JWKS only. Never follow token jku/x5u, and never
        # fall through to login.microsoftonline.com in synthetic mode.
        jwks_path = os.environ.get("FEDERATED_SYNTHETIC_JWKS_PATH", "").strip()
        if not jwks_path:
            raise FederatedOidcError(MICROSOFT_NOT_CONFIGURED_DETAIL, status_code=503)
        try:
            body = json.loads(Path(jwks_path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise FederatedOidcError(MICROSOFT_NOT_CONFIGURED_DETAIL, status_code=503) from exc
        if not isinstance(body, dict) or not isinstance(body.get("keys"), list):
            raise FederatedOidcError(MICROSOFT_NOT_CONFIGURED_DETAIL, status_code=503)
        return body
    response = httpx.get(microsoft_jwks_url(tenant), timeout=20.0)
    if response.status_code >= 400:
        raise FederatedOidcError(MICROSOFT_NOT_CONFIGURED_DETAIL, status_code=503)
    body = response.json()
    if not isinstance(body, dict) or not isinstance(body.get("keys"), list):
        raise FederatedOidcError(MICROSOFT_NOT_CONFIGURED_DETAIL, status_code=503)
    return body


def _signing_key_from_process_jwks(id_token: str) -> object:
    try:
        header = pyjwt.get_unverified_header(id_token)
    except InvalidTokenError as exc:
        raise FederatedOidcError(IDENTITY_TOKEN_INVALID_DETAIL) from exc
    if header.get("alg") not in ALLOWED_ID_TOKEN_ALGORITHMS:
        raise FederatedOidcError(IDENTITY_TOKEN_INVALID_DETAIL)
    if header.get("jku") or header.get("x5u"):
        raise FederatedOidcError(IDENTITY_TOKEN_INVALID_DETAIL)
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise FederatedOidcError(IDENTITY_TOKEN_INVALID_DETAIL)
    jwks = fetch_microsoft_jwks()
    for key_dict in jwks.get("keys", []):
        if not isinstance(key_dict, dict):
            continue
        if key_dict.get("kid") != kid:
            continue
        if key_dict.get("kty") != "RSA":
            continue
        try:
            return PyJWK.from_dict(key_dict).key
        except (InvalidTokenError, ValueError) as exc:
            raise FederatedOidcError(IDENTITY_TOKEN_INVALID_DETAIL) from exc
    raise FederatedOidcError(IDENTITY_TOKEN_INVALID_DETAIL)


def validate_id_token(id_token: str, *, expected_nonce: str) -> MicrosoftIdentity:
    """Validate a Microsoft id_token, then read oid/email. Never log the token."""
    if not isinstance(id_token, str) or not id_token.strip():
        raise FederatedOidcError(IDENTITY_TOKEN_INVALID_DETAIL)
    settings = get_settings()
    tenant = (settings.microsoft_tenant_id or "").strip()
    client_id = (settings.microsoft_client_id or "").strip()
    if not tenant or not client_id:
        raise FederatedOidcError(MICROSOFT_NOT_CONFIGURED_DETAIL, status_code=503)
    if not isinstance(expected_nonce, str) or not expected_nonce:
        raise FederatedOidcError(IDENTITY_TOKEN_INVALID_DETAIL)
    signing_key = _signing_key_from_process_jwks(id_token)
    issuer = microsoft_issuer(tenant)
    try:
        claims = pyjwt.decode(
            id_token,
            key=signing_key,
            algorithms=list(ALLOWED_ID_TOKEN_ALGORITHMS),
            audience=client_id,
            issuer=issuer,
            options={
                "require": ["exp", "iat", "iss", "aud"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except InvalidTokenError as exc:
        raise FederatedOidcError(IDENTITY_TOKEN_INVALID_DETAIL) from exc
    if claims.get("nonce") != expected_nonce:
        raise FederatedOidcError(IDENTITY_TOKEN_INVALID_DETAIL)
    tenant_id = claims.get("tid")
    if tenant_id != tenant:
        raise FederatedOidcError(TENANT_MISMATCH_DETAIL)
    provider_user_id = claims.get("oid") or claims.get("sub")
    if not isinstance(provider_user_id, str) or not provider_user_id:
        raise FederatedOidcError(IDENTITY_TOKEN_INVALID_DETAIL)
    email = claims.get("preferred_username") or claims.get("email")
    email_value = email if isinstance(email, str) else None
    return MicrosoftIdentity(
        provider_user_id=provider_user_id,
        email=email_value,
        tenant_id=tenant_id if isinstance(tenant_id, str) else None,
    )


def exchange_code_for_identity(
    *,
    provider: str,
    code: str,
    redirect_uri: str,
    expected_nonce: str,
) -> MicrosoftIdentity:
    if provider != "microsoft":
        raise FederatedOidcError(UNSUPPORTED_PROVIDER_DETAIL)
    assert_allowlisted_redirect_uri(redirect_uri)
    settings = get_settings()
    if settings.federated_oidc_mode == "synthetic":
        # Isolated tests pass a locally signed id_token as the code. Validation
        # still uses process JWKS, RS256, issuer, audience, time, and nonce.
        return validate_id_token(code, expected_nonce=expected_nonce)
    return _exchange_live_microsoft_code(code, redirect_uri, expected_nonce=expected_nonce)


def _exchange_live_microsoft_code(
    code: str, redirect_uri: str, *, expected_nonce: str
) -> MicrosoftIdentity:
    settings = get_settings()
    tenant = (settings.microsoft_tenant_id or "").strip()
    client_id = (settings.microsoft_client_id or "").strip()
    client_secret = (settings.microsoft_client_secret or "").strip()
    if not tenant or not client_id or not client_secret:
        raise FederatedOidcError(MICROSOFT_NOT_CONFIGURED_DETAIL, status_code=503)
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    response = httpx.post(
        token_url,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=20.0,
    )
    if response.status_code >= 400:
        raise FederatedOidcError("Microsoft authorization was rejected")
    body = response.json()
    id_token = body.get("id_token")
    if not isinstance(id_token, str) or not id_token:
        raise FederatedOidcError("Microsoft authorization was rejected")
    return validate_id_token(id_token, expected_nonce=expected_nonce)
