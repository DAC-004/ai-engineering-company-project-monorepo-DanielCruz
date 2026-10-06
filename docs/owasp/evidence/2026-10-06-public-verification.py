"""Timestamped public verification. Certificate verification uses the default trust store.

This script does not disable hostname or certificate checks. It does not request
a new certificate. The password and access token are not printed.
"""

from __future__ import annotations

import base64
import json
import os
import re
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
EXPECTED_BODY = "healthcore-acme-probe"


class _NoRedirect(urllib.request.HTTPErrorProcessor):
    def http_response(self, request, response):
        return response

    https_response = http_response


def _stamp(label: str) -> None:
    print(label, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


def _open(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "HealthCore-audit"})
    opener = urllib.request.build_opener(_NoRedirect)
    return opener.open(request, timeout=20)


def _request(path: str, *, method: str, body: bytes | None, content_type: str) -> tuple[int, bytes]:
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
        length = int.from_bytes(connection.recv(2), "big")
    elif length == 127:
        length = int.from_bytes(connection.recv(8), "big")
    payload = bytearray()
    while len(payload) < length:
        chunk = connection.recv(length - len(payload))
        if not chunk:
            break
        payload.extend(chunk)
    return bytes(payload)


def _certificate_check() -> ssl.SSLSocket:
    context = ssl.create_default_context()
    print("SSL_VERIFY_MODE", context.verify_mode)
    print("SSL_CHECK_HOSTNAME", context.check_hostname)
    raw = socket.create_connection((HOST, 443), timeout=20)
    connection = context.wrap_socket(raw, server_hostname=HOST)
    certificate = connection.getpeercert()
    sans = []
    for kind, value in certificate.get("subjectAltName", ()):
        sans.append(f"{kind}:{value}")
    print("CERT_SUBJECT", certificate.get("subject"))
    print("CERT_ISSUER", certificate.get("issuer"))
    print("CERT_SAN", ",".join(sans))
    print("CERT_NOT_BEFORE", certificate.get("notBefore"))
    print("CERT_NOT_AFTER", certificate.get("notAfter"))
    print("SAN_MATCHES_IP", f"IP Address:{HOST}" in sans)
    return connection


def _frontend(connection: ssl.SSLSocket) -> None:
    request = (
        "GET /login HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        "User-Agent: HealthCore-audit\r\n"
        "Connection: close\r\n\r\n"
    )
    connection.sendall(request.encode("ascii"))
    payload = b""
    while True:
        chunk = connection.recv(65536)
        if not chunk:
            break
        payload += chunk
    header, _, body = payload.partition(b"\r\n\r\n")
    status = header.split(b"\r\n", 1)[0].decode("ascii", "replace")
    print("FRONTEND_STATUS", status)
    html = body.decode("utf-8", "replace")
    scripts = re.findall(r'src="([^"]+\.js)"', html)
    print("FRONTEND_SCRIPT_COUNT", len(scripts))
    origin_hits = 0
    loopback_hits = 0
    telemetry_hits = 0
    for src in scripts:
        script_request = urllib.request.Request(
            f"https://{HOST}{src}",
            headers={"User-Agent": "HealthCore-audit"},
        )
        with urllib.request.urlopen(script_request, timeout=20) as response:
            text = response.read().decode("utf-8", "replace")
        if "https://150.136.171.59" in text:
            origin_hits += 1
        if "127.0.0.1:8000" in text or "http://localhost:8000" in text:
            loopback_hits += 1
        if "https://150.136.171.59/telemetry/events" in text:
            telemetry_hits += 1
    print("FRONTEND_ORIGIN_HITS", origin_hits)
    print("FRONTEND_LOOPBACK_HITS", loopback_hits)
    print("FRONTEND_TELEMETRY_HITS", telemetry_hits)


def _websocket() -> None:
    password = secrets.token_urlsafe(18)
    register_status, _body = _request(
        "/users",
        method="POST",
        body=json.dumps({"email": EMAIL, "password": password}).encode("utf-8"),
        content_type="application/json",
    )
    print("REGISTER_STATUS", register_status)
    login_status, login_payload = _request(
        "/auth/login",
        method="POST",
        body=urllib.parse.urlencode({"username": EMAIL, "password": password}).encode("utf-8"),
        content_type="application/x-www-form-urlencoded",
    )
    print("LOGIN_STATUS", login_status)
    token = ""
    if login_status == 200:
        token = str(json.loads(login_payload.decode("utf-8")).get("access_token", ""))
    print("TOKEN_PRESENT", bool(token))
    if not token:
        print("PUBLIC_WSS_FAILED")
        return
    context = ssl.create_default_context()
    raw = socket.create_connection((HOST, 443), timeout=20)
    connection = context.wrap_socket(raw, server_hostname=HOST)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    connection.sendall(
        (
            f"GET /ws/chat/{SESSION_ID} HTTP/1.1\r\n"
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
    status_line = response.split(b"\r\n", 1)[0].decode("ascii", "replace")
    print("WSS_STATUS_LINE", status_line)
    _send_text(connection, json.dumps({"event": "auth", "data": {"token": token}}))
    event = json.loads(_read_frame(connection).decode("utf-8"))
    data = event.get("data") if isinstance(event, dict) else None
    print("WSS_EVENT", event.get("event") if isinstance(event, dict) else "")
    print("WSS_SESSION", data.get("session_id") if isinstance(data, dict) else "")
    connection.close()


def main() -> int:
    _stamp("LOCAL_START")
    with _open(
        f"http://{HOST}/.well-known/acme-challenge/healthcore-probe"
    ) as response:
        body = response.read().decode("utf-8", "replace").strip()
        print("HTTP_CHALLENGE_STATUS", response.status)
        print("HTTP_CHALLENGE_BODY", body)
    with _open(f"http://{HOST}/") as response:
        print("HTTP_REDIRECT_STATUS", response.status)
        print("HTTP_REDIRECT_LOCATION", response.headers.get("Location"))
    _stamp("CERT_CHECK")
    connection = _certificate_check()
    _frontend(connection)
    connection.close()
    _stamp("WSS_CHECK")
    _websocket()
    _stamp("LOCAL_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
