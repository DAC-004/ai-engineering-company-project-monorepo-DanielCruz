"""Bounded public checks for the final audit. Tokens and passwords are not printed."""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import socket
import sys
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HOST = "150.136.171.59"
EMAIL_A = "audit.final1.20261006@example.com"
EMAIL_B = "audit.final2.20261006@example.com"
SESSION_ID = "auditfinal1"
NEEDLES = ("patient name", "diagnosis", "medication", "mrn", "social security", "date of birth")


class _NoRedirect(urllib.request.HTTPErrorProcessor):
    def http_response(self, request, response):
        return response

    https_response = http_response


def _stamp(label: str) -> None:
    print(label, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


def _request(
    path: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    content_type: str | None = None,
    token: str | None = None,
    timeout: int = 20,
) -> tuple[int, bytes]:
    headers = {"User-Agent": "HealthCore-audit"}
    if content_type:
        headers["Content-Type"] = content_type
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"https://{HOST}{path}",
        data=body,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
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
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(length.to_bytes(2, "big"))
    else:
        header.append(0x80 | 127)
        header.extend(length.to_bytes(8, "big"))
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    connection.sendall(bytes(header) + mask + masked)


def _read_event(connection: ssl.SSLSocket) -> tuple[str, str]:
    header = connection.recv(2)
    if len(header) < 2:
        return "short", ""
    opcode = header[0] & 0x0F
    length = header[1] & 0x7F
    if length == 126:
        length = int.from_bytes(connection.recv(2), "big")
    elif length == 127:
        length = int.from_bytes(connection.recv(8), "big")
    payload = bytearray()
    while len(payload) < length:
        chunk = connection.recv(length - len(payload))
        if not chunk:
            break
        payload.extend(chunk)
    if opcode == 8:
        code = int.from_bytes(payload[:2], "big") if len(payload) >= 2 else 0
        return "close", str(code)
    if opcode != 1:
        return f"opcode-{opcode}", ""
    event = json.loads(payload.decode("utf-8"))
    name = event.get("event") if isinstance(event, dict) else ""
    return "text", str(name)


def _socket_for(path: str) -> ssl.SSLSocket:
    context = ssl.create_default_context()
    raw = socket.create_connection((HOST, 443), timeout=20)
    connection = context.wrap_socket(raw, server_hostname=HOST)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    connection.sendall(
        (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {HOST}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
    )
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = connection.recv(4096)
        if not chunk:
            break
        response += chunk
    print("WSS_STATUS", response.split(b"\r\n", 1)[0].decode("ascii", "replace"))
    return connection


def _register(email: str, password: str) -> tuple[int, str]:
    status, body = _request(
        "/users",
        method="POST",
        body=json.dumps({"email": email, "password": password, "name": "Audit Final"}).encode("utf-8"),
        content_type="application/json",
    )
    user_id = ""
    if status in {200, 201}:
        user_id = str(json.loads(body.decode("utf-8")).get("id", ""))
    return status, user_id


def _login(email: str, password: str) -> tuple[int, str]:
    status, body = _request(
        "/auth/login",
        method="POST",
        body=urllib.parse.urlencode({"username": email, "password": password}).encode("utf-8"),
        content_type="application/x-www-form-urlencoded",
    )
    token = ""
    if status == 200:
        token = str(json.loads(body.decode("utf-8")).get("access_token", ""))
    return status, token


def _wss_retest() -> int:
    """Retest only the chat denial path after correcting client frame lengths."""
    _stamp("WSS_RETEST_START")
    password_a = secrets.token_urlsafe(18)
    password_b = secrets.token_urlsafe(18)
    status_a, id_a = _register(EMAIL_A, password_a)
    status_b, id_b = _register(EMAIL_B, password_b)
    print("REREGISTER_A", status_a, "ID_PRESENT", bool(id_a))
    print("REREGISTER_B", status_b, "ID_PRESENT", bool(id_b))
    login_a, token_a = _login(EMAIL_A, password_a)
    login_b, token_b = _login(EMAIL_B, password_b)
    print("RELOGIN_A", login_a, "TOKEN_A", bool(token_a))
    print("RELOGIN_B", login_b, "TOKEN_B", bool(token_b))
    try:
        if token_a:
            first = _socket_for(f"/ws/chat/{SESSION_ID}")
            _send_text(first, json.dumps({"event": "auth", "data": {"token": token_a}}))
            kind, name = _read_event(first)
            print("OWNER_FRAME", kind, name)
            first.close()
        if token_b:
            second = _socket_for(f"/ws/chat/{SESSION_ID}")
            _send_text(second, json.dumps({"event": "auth", "data": {"token": token_b}}))
            kind, name = _read_event(second)
            print("OTHER_USER_FRAME", kind, name)
            second.close()
    finally:
        if id_a and token_a:
            deleted, _body = _request(f"/users/{id_a}", method="DELETE", token=token_a)
            print("DELETE_A", deleted)
        if id_b and token_b:
            deleted, _body = _request(f"/users/{id_b}", method="DELETE", token=token_b)
            print("DELETE_B", deleted)
    _stamp("WSS_RETEST_END")
    return 0


def main() -> int:
    _stamp("START")
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(urllib.request.Request(f"http://{HOST}/", headers={"User-Agent": "HealthCore-audit"}), timeout=20) as response:
        print("HTTP_REDIRECT_STATUS", response.status)
        print("HTTP_REDIRECT_IS_HTTPS", str(response.headers.get("Location", "")).startswith("https://"))
    context = ssl.create_default_context()
    raw = socket.create_connection((HOST, 443), timeout=20)
    tls = context.wrap_socket(raw, server_hostname=HOST)
    certificate = tls.getpeercert()
    sans = [f"{kind}:{value}" for kind, value in certificate.get("subjectAltName", ())]
    print("CERT_VERIFY", context.verify_mode)
    print("CERT_SAN_MATCH", f"IP Address:{HOST}" in sans)
    print("CERT_NOT_AFTER", certificate.get("notAfter"))
    tls.sendall(
        f"GET /login HTTP/1.1\r\nHost: {HOST}\r\nUser-Agent: HealthCore-audit\r\nConnection: close\r\n\r\n".encode("ascii")
    )
    payload = b""
    while True:
        chunk = tls.recv(65536)
        if not chunk:
            break
        payload += chunk
    tls.close()
    _header, _, body = payload.partition(b"\r\n\r\n")
    print("LOGIN_PAGE", _header.split(b"\r\n", 1)[0].decode("ascii", "replace"))
    scripts = re.findall(r'src="([^"]+\.js)"', body.decode("utf-8", "replace"))
    origin_hits = 0
    loopback_hits = 0
    for src in scripts:
        with urllib.request.urlopen(
            urllib.request.Request(f"https://{HOST}{src}", headers={"User-Agent": "HealthCore-audit"}),
            timeout=20,
        ) as response:
            text = response.read().decode("utf-8", "replace")
        origin_hits += "https://150.136.171.59" in text
        loopback_hits += "127.0.0.1:8000" in text or "http://localhost:8000" in text
    print("SCRIPT_COUNT", len(scripts))
    print("ORIGIN_HITS", origin_hits)
    print("LOOPBACK_HITS", loopback_hits)
    anon_status, _anon_body = _request("/inventory/products")
    print("ANON_INVENTORY", anon_status)
    password_a = secrets.token_urlsafe(18)
    password_b = secrets.token_urlsafe(18)
    status_a, id_a = _register(EMAIL_A, password_a)
    status_b, id_b = _register(EMAIL_B, password_b)
    print("REGISTER_A", status_a, "ID_PRESENT", bool(id_a))
    print("REGISTER_B", status_b, "ID_PRESENT", bool(id_b))
    login_a, token_a = _login(EMAIL_A, password_a)
    login_b, token_b = _login(EMAIL_B, password_b)
    print("LOGIN_A", login_a, "TOKEN_A", bool(token_a))
    print("LOGIN_B", login_b, "TOKEN_B", bool(token_b))
    try:
        if token_a:
            first = _socket_for(f"/ws/chat/{SESSION_ID}")
            _send_text(first, json.dumps({"event": "auth", "data": {"token": token_a}}))
            kind, name = _read_event(first)
            print("OWNER_FRAME", kind, name)
            first.close()
        if token_b:
            second = _socket_for(f"/ws/chat/{SESSION_ID}")
            _send_text(second, json.dumps({"event": "auth", "data": {"token": token_b}}))
            kind, name = _read_event(second)
            print("OTHER_USER_FRAME", kind, name)
            second.close()
        knowledge_status, knowledge_body = _request(
            "/knowledge/query",
            method="POST",
            body=json.dumps({"question": "Which policy document covers appointment cancellation?"}).encode("utf-8"),
            content_type="application/json",
            timeout=180,
        )
        answer = ""
        if knowledge_status == 200:
            answer = str(json.loads(knowledge_body.decode("utf-8")).get("answer", ""))
        print("KNOWLEDGE_STATUS", knowledge_status)
        print("KNOWLEDGE_ANSWER_CHARS", len(answer))
        print("KNOWLEDGE_CLINICAL", any(needle in answer.lower() for needle in NEEDLES))
    finally:
        if id_a and token_a:
            deleted, _body = _request(f"/users/{id_a}", method="DELETE", token=token_a)
            print("DELETE_A", deleted)
        if id_b and token_b:
            deleted, _body = _request(f"/users/{id_b}", method="DELETE", token=token_b)
            print("DELETE_B", deleted)
    _stamp("END")
    return 0


if __name__ == "__main__":
    raise SystemExit(_wss_retest() if len(sys.argv) > 1 and sys.argv[1] == "retest" else main())
