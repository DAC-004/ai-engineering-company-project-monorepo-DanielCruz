"""Microsoft staff federated authentication under /auth/federated."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.access.permissions import require_authenticated
from app.core.security import (
    AUTH_METHOD_CLAIM,
    AUTH_METHOD_MICROSOFT,
    AUTH_METHOD_PASSWORD,
    JWTError,
    decode_access_token,
)
from app.schemas.auth import Token
from app.schemas.federated import (
    FederatedCallbackRequest,
    FederatedStartRequest,
    FederatedStartResponse,
    FederatedStatusResponse,
)
from app.schemas.user import UserInDB
from app.services import federated_auth, user_service
from app.services.federated_auth import FederatedAuthError

router = APIRouter(prefix="/auth/federated", tags=["federated-auth"])
optional_bearer = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_KNOWN_AUTH_METHODS = frozenset({AUTH_METHOD_PASSWORD, AUTH_METHOD_MICROSOFT})


@dataclass(frozen=True)
class OptionalFederatedCaller:
    user: UserInDB | None
    auth_method: str | None


def _optional_caller(
    token: str | None = Depends(optional_bearer),
) -> OptionalFederatedCaller:
    if not token:
        return OptionalFederatedCaller(user=None, auth_method=None)
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id or not isinstance(user_id, str):
            return OptionalFederatedCaller(user=None, auth_method=None)
        raw_method = payload.get(AUTH_METHOD_CLAIM)
        auth_method = raw_method if raw_method in _KNOWN_AUTH_METHODS else None
    except JWTError:
        return OptionalFederatedCaller(user=None, auth_method=None)
    user = user_service.get_user_by_id(user_id)
    if user is None or not user.is_active:
        return OptionalFederatedCaller(user=None, auth_method=None)
    return OptionalFederatedCaller(user=user, auth_method=auth_method)


def _raise(exc: FederatedAuthError) -> None:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    raise HTTPException(
        status_code=exc.status_code, detail=exc.detail, headers=headers
    ) from exc


@router.post("/{provider}/start", response_model=FederatedStartResponse)
def start_federated(
    provider: str,
    payload: FederatedStartRequest,
    caller: OptionalFederatedCaller = Depends(_optional_caller),
) -> FederatedStartResponse:
    try:
        return federated_auth.start_authorization(
            provider=provider,
            purpose=payload.purpose,
            redirect_uri=payload.redirect_uri,
            current_user=caller.user,
            auth_method=caller.auth_method,
        )
    except FederatedAuthError as exc:
        _raise(exc)


@router.post("/{provider}/callback")
def complete_federated(
    provider: str,
    payload: FederatedCallbackRequest,
    caller: OptionalFederatedCaller = Depends(_optional_caller),
) -> Token | FederatedStatusResponse:
    try:
        return federated_auth.complete_callback(
            provider=provider,
            code=payload.code,
            state=payload.state,
            redirect_uri=payload.redirect_uri,
            tx_binding=payload.tx_binding,
            current_user=caller.user,
            auth_method=caller.auth_method,
        )
    except FederatedAuthError as exc:
        _raise(exc)


@router.get("/microsoft/status", response_model=FederatedStatusResponse)
def read_microsoft_status(
    current_user: UserInDB = Depends(require_authenticated),
) -> FederatedStatusResponse:
    return federated_auth.microsoft_status(current_user)


@router.delete("/microsoft", response_model=FederatedStatusResponse)
def unlink_microsoft(
    current_user: UserInDB = Depends(require_authenticated),
) -> FederatedStatusResponse:
    try:
        return federated_auth.unlink_microsoft(current_user)
    except FederatedAuthError as exc:
        _raise(exc)
