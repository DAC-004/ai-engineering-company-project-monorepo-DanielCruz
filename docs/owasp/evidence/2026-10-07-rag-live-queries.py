"""Synthetic knowledge checks against the running loopback API.

This client does not import the pipeline and does not patch retrieval or generation.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from datetime import UTC, datetime

QUESTIONS = (
    (
        "cancellation",
        "What notice does the appointment policy require before a cancellation?",
    ),
    (
        "reminder",
        "When is the last reminder sent before an appointment?",
    ),
    (
        "routine",
        "What is the average availability for a routine appointment?",
    ),
)
PHI_TERMS = (
    "medical record",
    "mrn",
    "date of birth",
    "nhs number",
    "national insurance",
    "insurance number",
    "lab result",
    "clinical note",
    "member identifier",
    "diagnosis",
)


def _post(question: str) -> tuple[int, str]:
    body = json.dumps({"question": question}).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:8000/knowledge/query",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=420) as response:
        payload = json.loads(response.read().decode("utf-8"))
        return response.status, str(payload.get("answer", ""))


def _ws_without_token() -> None:
    client = socket.create_connection(("127.0.0.1", 8000), timeout=10)
    request = (
        "GET /ws/chat/rag-live-check HTTP/1.1\r\n"
        "Host: 127.0.0.1:8000\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    client.sendall(request.encode("ascii"))
    client.settimeout(8)
    data = b""
    try:
        while len(data) < 8192:
            chunk = client.recv(1024)
            if not chunk:
                break
            data += chunk
    except TimeoutError:
        pass
    finally:
        client.close()
    status = data.split(b"\r\n", 1)[0].decode("ascii", "replace")
    print("WS_STATUS", status)
    marker = data.find(b"\x88")
    if marker >= 0 and marker + 3 < len(data):
        print("WS_CLOSE", int.from_bytes(data[marker + 2 : marker + 4], "big"))
    else:
        print("WS_CLOSE", "absent")


def main() -> None:
    _ws_without_token()
    for name, question in QUESTIONS:
        started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        print("QUESTION", name)
        print("ASKED", question)
        print("STARTED", started)
        try:
            status, answer = _post(question)
        except urllib.error.HTTPError as exc:
            print("HTTP_ERROR", exc.code)
            print("ENDED", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
            continue
        except Exception as exc:
            print("REQUEST_ERROR", type(exc).__name__)
            print("ENDED", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
            continue
        lowered = answer.lower()
        print("STATUS", status)
        print("ENDED", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
        print("ANSWER_CHARS", len(answer))
        print("HAS_24_HOUR", "24 hour" in lowered)
        print("HAS_2_HOUR", "2 hour" in lowered or "2h" in lowered)
        print("HAS_CANCELL", "cancell" in lowered)
        print("HAS_REMIND", "remind" in lowered)
        print("HAS_3_TO_5", "3 to 5" in lowered or "3-5" in lowered)
        matched = [term for term in PHI_TERMS if term in lowered]
        print("PHI_MATCHES", ",".join(matched) if matched else "none")
        print("ANSWER_TEXT")
        print(answer)
        print("END_ANSWER_TEXT")


if __name__ == "__main__":
    main()
