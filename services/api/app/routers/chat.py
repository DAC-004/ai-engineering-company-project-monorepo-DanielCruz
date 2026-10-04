"""Authenticated WebSocket chat for one compliance-assistant session.

The socket authenticates a backoffice JWT, then subscribes to that session's
in-memory channel. It does not call the model. The generation worker does.
"""

from __future__ import annotations

import asyncio
import logging
import re
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import JWTError, decode_access_token
from app.schemas.user import UserInDB
from app.services import user_service
from app.services.chat_channel import (
    get_chat_hub,
    request_interrupt,
    start_user_turn,
)

logger = logging.getLogger("healthcore.chat")

router = APIRouter(tags=["chat"])

_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_AUTH_TIMEOUT_SECONDS = 5.0


def authenticate_backoffice_token(token: str) -> UserInDB | None:
    """Return the active TinyDB user for a backoffice JWT, or None."""
    try:
        payload = decode_access_token(token)
    except JWTError:
        return None
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        return None
    user = user_service.get_user_by_id(user_id)
    if user is None or not user.is_active:
        return None
    return user


async def _reject(websocket: WebSocket, *, accepted: bool) -> None:
    """Close without sending a chat event. The token is not logged."""
    logger.info("Rejected chat socket before any chat event")
    # ``accepted`` distinguishes a pre-accept close from a post-accept close.
    # Both stages use the same policy code and neither one logs the token.
    _ = accepted
    try:
        await websocket.close(code=1008)
    except (WebSocketDisconnect, RuntimeError):
        return


async def _read_auth_user(websocket: WebSocket) -> UserInDB | None:
    """Read one auth frame. A chat event in that position is not accepted."""
    try:
        message = await asyncio.wait_for(websocket.receive_json(), timeout=_AUTH_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, WebSocketDisconnect, RuntimeError, ValueError):
        return None
    if not isinstance(message, dict) or message.get("event") != "auth":
        return None
    data = message.get("data")
    token = data.get("token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token:
        return None
    return authenticate_backoffice_token(token)


@router.websocket("/ws/chat/{session_id}")
async def chat_socket(websocket: WebSocket, session_id: str, token: str | None = None) -> None:
    """Connect a staff user to ``chat.<session_id>`` after the JWT is valid."""
    if _SESSION_ID.fullmatch(session_id) is None:
        await websocket.close(code=1008)
        return

    if token is not None:
        user = authenticate_backoffice_token(token)
        if user is None:
            await _reject(websocket, accepted=False)
            return
        await websocket.accept()
    else:
        await websocket.accept()
        user = await _read_auth_user(websocket)
        if user is None:
            await _reject(websocket, accepted=True)
            return

    hub = get_chat_hub()
    hub.bind_loop(asyncio.get_running_loop())
    session = hub.open_session(session_id, user.id)
    if session is None:
        await websocket.close(code=1008)
        return

    logger.info("Accepted chat socket session_id=%s", session_id)
    await websocket.send_json(hub.snapshot_event(session))
    queue = hub.subscribe(session_id)
    disconnected = asyncio.Event()
    receiver = asyncio.create_task(
        _receive_client_events(websocket, session_id, disconnected)
    )
    try:
        while not disconnected.is_set():
            incoming = asyncio.create_task(queue.get())
            stopped = asyncio.create_task(disconnected.wait())
            done, _pending = await asyncio.wait(
                {incoming, stopped},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if incoming not in done:
                incoming.cancel()
                break
            await websocket.send_json(incoming.result())
    except WebSocketDisconnect:
        return
    finally:
        disconnected.set()
        receiver.cancel()
        hub.unsubscribe(session_id, queue)


async def _receive_client_events(
    websocket: WebSocket,
    session_id: str,
    disconnected: asyncio.Event,
) -> None:
    """Apply inbound chat messages. Auth frames are ignored and not published."""
    try:
        while True:
            try:
                message = await websocket.receive_json()
            except (WebSocketDisconnect, RuntimeError):
                return
            if not isinstance(message, dict):
                continue
            event_name = message.get("event")
            data = message.get("data") if isinstance(message.get("data"), dict) else {}
            if event_name == "auth":
                continue
            if data.get("session_id") not in {None, session_id}:
                continue
            if event_name == "user_message":
                text = data.get("text")
                if isinstance(text, str):
                    start_user_turn(session_id, text)
            elif event_name == "interrupt_requested":
                new_input = data.get("new_input")
                if isinstance(new_input, str):
                    request_interrupt(session_id, new_input)
    finally:
        disconnected.set()
