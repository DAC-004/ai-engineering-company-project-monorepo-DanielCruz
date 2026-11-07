"""Staff Microsoft link and login. Federated login never creates a User row.

Linking is a profile action on an already-provisioned staff account.
Login looks up provider + provider_user_id only. Email_at_link_time is a snapshot.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from tinydb import Query

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
    identity_mutation_lock,
    users_table,
)
from app.schemas.auth import Token
from app.schemas.federated import (
    FederatedLinkPublic,
    FederatedStartResponse,
    FederatedStatusResponse,
    MICROSOFT_PROVIDER,
)
from app.schemas.user import UserInDB
from app.services.federated_oidc import (
    FederatedOidcError,
    MicrosoftIdentity,
    build_authorization_url,
    decode_oauth_state,
    encode_oauth_state,
    exchange_code_for_identity,
)
from app.services import user_service

LAST_METHOD_DETAIL = "Cannot unlink the last remaining access method"
NOT_STAFF_DETAIL = "Federated authentication is not available for this account"
NOT_PROVISIONED_DETAIL = "Microsoft can be linked only after IT provisions this account"
NOT_TRADITIONAL_SESSION_DETAIL = (
    "Microsoft can be linked only from a traditional sign-in"
)
ALREADY_LINKED_ELSEWHERE_DETAIL = "That Microsoft identity is already linked"
UNSUPPORTED_PURPOSE_DETAIL = "Unsupported federated purpose"
UNLINKED_IDENTITY_DETAIL = "This Microsoft account is not linked to a HealthCore user"
INACTIVE_DETAIL = "Inactive user"
NOT_LINKED_DETAIL = "Microsoft is not linked"
SECRET_FIELD_NAMES = frozenset(
    {
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "MICROSOFT_CLIENT_SECRET",
        "hashed_password",
        "password",
        "code",
        "tx_binding",
        "state",
    }
)


class FederatedAuthError(Exception):
    def __init__(self, detail: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def start_authorization(
    *,
    provider: str,
    purpose: str,
    redirect_uri: str,
    current_user: UserInDB | None,
    auth_method: str | None,
) -> FederatedStartResponse:
    if purpose not in {"link", "login"}:
        raise FederatedAuthError(UNSUPPORTED_PURPOSE_DETAIL, 400)
    user_id = None
    if purpose == "link":
        if current_user is None:
            raise FederatedAuthError("Not authenticated", 401)
        _assert_traditional_session(auth_method)
        _assert_can_link(current_user)
        user_id = current_user.id
    jti = uuid4().hex
    oidc_nonce = uuid4().hex
    tx_binding = secrets.token_urlsafe(32)
    expire = datetime.now(UTC) + timedelta(minutes=10)
    try:
        state = encode_oauth_state(
            purpose=purpose,
            redirect_uri=redirect_uri,
            user_id=user_id,
            jti=jti,
            oidc_nonce=oidc_nonce,
        )
        authorization_url = build_authorization_url(
            provider=provider,
            purpose=purpose,
            redirect_uri=redirect_uri,
            state=state,
            oidc_nonce=oidc_nonce,
        )
    except FederatedOidcError as exc:
        if purpose == "login":
            _record_early_rejection(
                provider=provider, purpose=purpose, reason="authorization_start_rejected"
            )
        raise FederatedAuthError(exc.detail, exc.status_code) from exc
    _store_oauth_transaction(
        jti=jti,
        tx_binding=tx_binding,
        purpose=purpose,
        user_id=user_id,
        redirect_uri=redirect_uri,
        oidc_nonce=oidc_nonce,
        expire=expire,
    )
    return FederatedStartResponse(
        authorization_url=authorization_url,
        state=state,
        tx_binding=tx_binding,
    )


def complete_callback(
    *,
    provider: str,
    code: str,
    state: str,
    redirect_uri: str,
    tx_binding: str,
    current_user: UserInDB | None,
    auth_method: str | None,
) -> Token | FederatedStatusResponse:
    try:
        payload = decode_oauth_state(state)
    except FederatedOidcError as exc:
        # An invalid state cannot establish a purpose or caller identity.
        _record_early_rejection(provider=provider, purpose=None, reason="invalid_state")
        raise FederatedAuthError(exc.detail, exc.status_code) from exc

    purpose = payload.get("purpose")
    current_user_id = current_user.id if current_user is not None else None
    try:
        _consume_oauth_transaction(
            payload=payload,
            tx_binding=tx_binding,
            redirect_uri=redirect_uri,
            current_user_id=current_user_id,
        )
    except FederatedAuthError:
        _record_early_rejection(
            provider=provider, purpose=purpose, reason="invalid_transaction"
        )
        raise
    try:
        identity = exchange_code_for_identity(
            provider=provider,
            code=code,
            redirect_uri=redirect_uri,
            expected_nonce=str(payload["oidc_nonce"]),
        )
    except FederatedOidcError as exc:
        _record_early_rejection(
            provider=provider, purpose=purpose, reason="identity_rejected"
        )
        raise FederatedAuthError(exc.detail, exc.status_code) from exc

    if purpose == "link":
        return _complete_link(
            provider=provider,
            identity=identity,
            state_user_id=payload.get("uid"),
            current_user=current_user,
            auth_method=auth_method,
        )
    if purpose == "login":
        return _complete_login(provider=provider, identity=identity)
    _record_early_rejection(
        provider=provider, purpose=purpose, reason="unsupported_purpose"
    )
    raise FederatedAuthError(UNSUPPORTED_PURPOSE_DETAIL, 400)


def microsoft_status(current_user: UserInDB) -> FederatedStatusResponse:
    link = _link_for_user(current_user.id)
    has_password = _user_has_password(current_user.id)
    can_unlink = link is not None and _access_method_count(current_user.id) > 1
    reason = None if can_unlink or link is None else LAST_METHOD_DETAIL
    public = _to_public(link) if link else None
    return FederatedStatusResponse(
        linked=link is not None,
        link=public,
        has_password=has_password,
        can_unlink=can_unlink,
        unlink_blocked_reason=reason,
    )


def unlink_microsoft(current_user: UserInDB) -> FederatedStatusResponse:
    with identity_mutation_lock():
        link = _link_for_user(current_user.id)
        if link is None:
            raise FederatedAuthError(NOT_LINKED_DETAIL, 404)
        if _access_method_count(current_user.id) <= 1:
            raise FederatedAuthError(LAST_METHOD_DETAIL, 409)
        federated_links_table().remove(
            (Query().user_id == current_user.id)
            & (Query().provider == MICROSOFT_PROVIDER)
        )
        _record_audit(
            event="federated_unlink",
            user_id=current_user.id,
            provider=MICROSOFT_PROVIDER,
            provider_user_id=str(link["provider_user_id"]),
        )
    return microsoft_status(current_user)


def list_audit_events() -> list[dict]:
    return [dict(row) for row in federated_audit_table().all()]


def user_count() -> int:
    return len(users_table().all())


def _complete_link(
    *,
    provider: str,
    identity: MicrosoftIdentity,
    state_user_id: object,
    current_user: UserInDB | None,
    auth_method: str | None,
) -> FederatedStatusResponse:
    if current_user is None:
        raise FederatedAuthError("Not authenticated", 401)
    _assert_traditional_session(auth_method)
    if state_user_id != current_user.id:
        raise FederatedAuthError("OAuth state is invalid", 400)
    _assert_can_link(current_user)

    with identity_mutation_lock():
        existing = _link_by_identity(provider, identity.provider_user_id)
        if existing is not None and existing["user_id"] != current_user.id:
            raise FederatedAuthError(ALREADY_LINKED_ELSEWHERE_DETAIL, 409)
        own = _link_for_user(current_user.id)
        if own is not None and own["provider_user_id"] != identity.provider_user_id:
            raise FederatedAuthError(ALREADY_LINKED_ELSEWHERE_DETAIL, 409)
        if own is None:
            federated_links_table().insert(
                {
                    "id": str(uuid4()),
                    "user_id": current_user.id,
                    "provider": provider,
                    "provider_user_id": identity.provider_user_id,
                    "email_at_link_time": identity.email,
                    "linked_at": datetime.now(UTC).isoformat(),
                    "provisioned_by_it": True,
                }
            )
            _record_audit(
                event="federated_link",
                user_id=current_user.id,
                provider=provider,
                provider_user_id=identity.provider_user_id,
            )
    return microsoft_status(current_user)


def _complete_login(*, provider: str, identity: MicrosoftIdentity) -> Token:
    # Lookup is provider + oid only. A matching email must not create or bind a user.
    link = _link_by_identity(provider, identity.provider_user_id)
    if link is None:
        _record_audit(
            event="federated_login_rejected",
            user_id=None,
            provider=provider,
            provider_user_id=identity.provider_user_id,
        )
        raise FederatedAuthError(UNLINKED_IDENTITY_DETAIL, 401)
    user = user_service.get_user_by_id(str(link["user_id"]))
    if user is None or _audience(user.id) != "staff":
        _record_audit(
            event="federated_login_rejected",
            user_id=str(link["user_id"]) if link.get("user_id") else None,
            provider=provider,
            provider_user_id=identity.provider_user_id,
        )
        raise FederatedAuthError(UNLINKED_IDENTITY_DETAIL, 401)
    if not user.is_active:
        _record_audit(
            event="federated_login_rejected",
            user_id=user.id,
            provider=provider,
            provider_user_id=identity.provider_user_id,
        )
        raise FederatedAuthError(INACTIVE_DETAIL, 401)
    _record_audit(
        event="federated_login_success",
        user_id=user.id,
        provider=provider,
        provider_user_id=identity.provider_user_id,
    )
    return Token(
        access_token=create_access_token(
            subject=user.id,
            extra_claims={AUTH_METHOD_CLAIM: AUTH_METHOD_MICROSOFT},
        )
    )


def _assert_traditional_session(auth_method: str | None) -> None:
    if auth_method != AUTH_METHOD_PASSWORD:
        raise FederatedAuthError(NOT_TRADITIONAL_SESSION_DETAIL, 403)


def _assert_can_link(current_user: UserInDB) -> None:
    if _audience(current_user.id) != "staff":
        raise FederatedAuthError(NOT_STAFF_DETAIL, 403)
    if not _provisioned_by_it(current_user.id):
        raise FederatedAuthError(NOT_PROVISIONED_DETAIL, 403)


def _raw_user(user_id: str) -> dict | None:
    row = users_table().get(Query().id == user_id)
    return dict(row) if row else None


def _audience(user_id: str) -> str | None:
    row = _raw_user(user_id) or {}
    value = row.get("audience")
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized in {"staff", "patient"}:
        return normalized
    return None


def _provisioned_by_it(user_id: str) -> bool:
    # Missing, false, and non-boolean values cannot establish IT provisioning.
    row = _raw_user(user_id) or {}
    return row.get("provisioned_by_it") is True


def _user_has_password(user_id: str) -> bool:
    row = _raw_user(user_id) or {}
    if "has_password" in row:
        return row["has_password"] is True
    return bool(row.get("hashed_password"))


def _access_method_count(user_id: str) -> int:
    password_methods = 1 if _user_has_password(user_id) else 0
    links = len(federated_links_table().search(Query().user_id == user_id))
    return password_methods + links


def _link_for_user(user_id: str):
    return federated_links_table().get(Query().user_id == user_id)


def _link_by_identity(provider: str, provider_user_id: str):
    Link = Query()
    return federated_links_table().get(
        (Link.provider == provider) & (Link.provider_user_id == provider_user_id)
    )


def _to_public(link) -> FederatedLinkPublic:
    linked_at = link.get("linked_at")
    parsed = None
    if isinstance(linked_at, str):
        parsed = datetime.fromisoformat(linked_at)
    return FederatedLinkPublic(
        provider=str(link["provider"]),
        provider_user_id=str(link["provider_user_id"]),
        email_at_link_time=link.get("email_at_link_time"),
        linked_at=parsed,
        provisioned_by_it=link.get("provisioned_by_it") is True,
    )


def _hash_tx_binding(tx_binding: str) -> str:
    return hashlib.sha256(tx_binding.encode("utf-8")).hexdigest()


def _store_oauth_transaction(
    *,
    jti: str,
    tx_binding: str,
    purpose: str,
    user_id: str | None,
    redirect_uri: str,
    oidc_nonce: str,
    expire: datetime,
) -> None:
    federated_oauth_tx_table().insert(
        {
            "jti": jti,
            "binding_hash": _hash_tx_binding(tx_binding),
            "purpose": purpose,
            "user_id": user_id,
            "redirect_uri": redirect_uri,
            "oidc_nonce": oidc_nonce,
            "exp": expire.isoformat(),
            "consumed": False,
        }
    )


def _consume_oauth_transaction(
    *,
    payload: dict,
    tx_binding: str,
    redirect_uri: str,
    current_user_id: str | None,
) -> None:
    # Binding secret stays off the redirect URL. Foreign browsers and replays
    # cannot complete the transaction even with a copied state JWT.
    if payload.get("redirect_uri") != redirect_uri:
        raise FederatedAuthError("OAuth state is invalid", 400)
    if not isinstance(tx_binding, str) or not tx_binding.strip():
        raise FederatedAuthError("OAuth state is invalid", 400)
    jti = payload.get("jti")
    with identity_mutation_lock():
        row = federated_oauth_tx_table().get(Query().jti == jti)
        if row is None:
            raise FederatedAuthError("OAuth state is invalid", 400)
        if row.get("consumed") is True:
            raise FederatedAuthError("OAuth state is invalid", 400)
        try:
            expire_at = datetime.fromisoformat(str(row["exp"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise FederatedAuthError("OAuth state is invalid", 400) from exc
        if datetime.now(UTC) >= expire_at:
            raise FederatedAuthError("OAuth state is invalid", 400)
        expected_hash = str(row.get("binding_hash") or "")
        if not hmac.compare_digest(expected_hash, _hash_tx_binding(tx_binding)):
            raise FederatedAuthError("OAuth state is invalid", 400)
        if row.get("purpose") != payload.get("purpose"):
            raise FederatedAuthError("OAuth state is invalid", 400)
        if row.get("oidc_nonce") != payload.get("oidc_nonce"):
            raise FederatedAuthError("OAuth state is invalid", 400)
        if row.get("purpose") == "link":
            if (
                row.get("user_id") != current_user_id
                or payload.get("uid") != current_user_id
            ):
                raise FederatedAuthError("OAuth state is invalid", 400)
        federated_oauth_tx_table().update({"consumed": True}, Query().jti == jti)


def _record_early_rejection(*, provider: str, purpose: object, reason: str) -> None:
    # Never attribute pre-validation failures to an unverified oid, user, or
    # caller-supplied provider. Only fixed categories reach the audit store.
    _record_audit(
        event="federated_link_rejected" if purpose == "link" else "federated_login_rejected",
        user_id=None,
        provider=MICROSOFT_PROVIDER if provider == MICROSOFT_PROVIDER else "unsupported",
        provider_user_id=None,
        reason=reason,
    )


def _record_audit(
    *,
    event: str,
    user_id: str | None,
    provider: str,
    provider_user_id: str | None,
    reason: str | None = None,
) -> None:
    record = {
        "id": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        "user_id": user_id,
        "provider": provider,
        "provider_user_id": provider_user_id,
    }
    if reason is not None:
        record["reason"] = reason
    for forbidden in SECRET_FIELD_NAMES:
        record.pop(forbidden, None)
    federated_audit_table().insert(record)
