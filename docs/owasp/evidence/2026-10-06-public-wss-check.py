"""Public authenticated WebSocket check.

The generated password and access token stay in process memory. This script
prints status codes and the socket event name only.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HOST = "150.136.171.59"
EMAIL = "audit.wss.20261006@example.com"
SESSION_ID = "auditprobe1"


def _request(
    path: str,
    *,
    method: str,
    body: bytes | None,
    content_type: str,
) -> tuple[int, bytes]:
    request = urllib.request.Request(
        f"https://{HOST}{path}",
        data=body,
        method=method,
        headers={"User-Agent": "HealthCore-audit", "Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _send_text(connection: ssl.SSLSocket, text: str) -> None:
    payload = text.encode("utf-8")
    mask = os.urandom(4)
    header = bytearray([0x81])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    else:
        header.append(0x80 | 126)
        header.extend(length.to_bytes(2, "big"))
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    connection.sendall(bytes(header) + mask + masked)


def _read_frame(connection: ssl.SSLSocket) -> bytes:
    header = connection.recv(2)
    if len(header) < 2:
        raise RuntimeError("short websocket header")
    length = header[1] & 0x7F
    if length == 126:
        extended = connection.recv(2)
        length = int.from_bytes(extended, "big")
    elif length == 127:
        extended = connection.recv(8)
        length = int.from_bytes(extended, "big")
    payload = bytearray()
    while len(payload) < length:
        chunk = connection.recv(length - len(payload))
        if not chunk:
            break
        payload.extend(chunk)
    return bytes(payload)


def main() -> int:
    print("LOCAL", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    password = secrets.token_urlsafe(18)
    register_status, _register_body = _request(
        "/users",
        method="POST",
        body=json.dumps({"email": EMAIL, "password": password}).encode("utf-8"),
        content_type="application/json",
    )
    print("REGISTER_STATUS", register_status)
    login_body = urllib.parse.urlencode(
        {"username": EMAIL, "password": password}
    ).encode("utf-8")
    login_status, login_payload = _request(
        "/auth/login",
        method="POST",
        body=login_body,
        content_type="application/x-www-form-urlencoded",
    )
    print("LOGIN_STATUS", login_status)
    token = ""
    if login_status == 200:
        parsed = json.loads(login_payload.decode("utf-8"))
        token = str(parsed.get("access_token", ""))
    print("TOKEN_PRESENT", bool(token))
    if not token:
        return 1

    context = ssl.create_default_context()
    raw = socket.create_connection((HOST, 443), timeout=20)
    connection = context.wrap_socket(raw, server_hostname=HOST)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    handshake = (
        f"GET /ws/chat/{SESSION_ID} HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    connection.sendall(handshake.encode("ascii"))
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = connection.recv(4096)
        if not chunk:
            break
        response += chunk
    status_line = response.split(b"\r\n", 1)[0].decode("ascii", "replace")
    print("WSS_STATUS_LINE", status_line)
    if b" 101 " not in response.split(b"\r\n", 1)[0]:
        connection.close()
        return 1
    _send_text(
        connection,
        json.dumps({"event": "auth", "data": {"token": token}}),
    )
    frame = _read_frame(connection)
    event = json.loads(frame.decode("utf-8"))
    data = event.get("data") if isinstance(event, dict) else None
    session_id = data.get("session_id") if isinstance(data, dict) else ""
    messages = data.get("messages") if isinstance(data, dict) else None
    print("WSS_EVENT", event.get("event") if isinstance(event, dict) else "")
    print("WSS_SESSION", session_id)
    print("WSS_MESSAGE_COUNT", len(messages) if isinstance(messages, list) else -1)
    connection.close()
    passed = (
        register_status in (200, 201)
        and login_status == 200
        and event.get("event") == "session_snapshot"
        and session_id == SESSION_ID
    )
    print("PUBLIC_WSS_PASSED" if passed else "PUBLIC_WSS_FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
