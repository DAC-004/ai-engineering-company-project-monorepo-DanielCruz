"""Authenticated public WSS through completion, interrupt, and a refusal.



Synthetic account only. Prints event names, counts, identifiers, and booleans.

Does not print the access token, password, or full answer text.



Integrity uses the public protocol only: token_chunk sequence, message_id on

generation_completed / generation_interrupted, and assistant text from a later

session_snapshot. Server-only last_generation.stored_text is not a public event.

"""



from __future__ import annotations



import asyncio

import json

import secrets

import urllib.error

import urllib.parse

import urllib.request

import uuid

from datetime import UTC, datetime



import websockets

from websockets.exceptions import ConnectionClosed



HOST = "150.136.171.59"

EMAIL = f"audit.wss.stream.{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}@example.com"

POLICY_QUESTION = "What notice does the appointment policy require before a cancellation?"

REFUSAL_QUESTION = "staff asked about a medical record"

PHI_TERMS = (

    "medical record",

    "mrn",

    "date of birth",

    "nhs number",

    "national insurance",

)





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

        with urllib.request.urlopen(request, timeout=30) as response:

            return response.status, response.read()

    except urllib.error.HTTPError as exc:

        return exc.code, exc.read()





async def _collect_until(connection: object, terminal: str) -> list[dict]:

    events: list[dict] = []

    while True:

        raw = await asyncio.wait_for(connection.recv(), timeout=420)

        event = json.loads(raw)

        events.append(event)

        if event.get("event") == terminal:

            return events





async def _open(session_id: str, token: str):

    connection = await websockets.connect(

        f"wss://{HOST}/ws/chat/{session_id}",

        open_timeout=30,

        close_timeout=10,

        ping_interval=20,

        ping_timeout=20,

    )

    await connection.send(json.dumps({"event": "auth", "data": {"token": token}}))

    event = json.loads(await asyncio.wait_for(connection.recv(), timeout=30))

    if event.get("event") != "session_snapshot":

        await connection.close()

        raise RuntimeError(f"expected session_snapshot got {event.get('event')}")

    return connection, event





def _token_stream(events: list[dict]) -> tuple[list[str], list[int], str]:

    tokens: list[str] = []

    sequences: list[int] = []

    for item in events:

        if item.get("event") != "token_chunk":

            continue

        data = item.get("data") or {}

        tokens.append(str(data.get("token", "")))

        sequences.append(int(data.get("sequence")))

    return tokens, sequences, "".join(tokens)





def _sequences_contiguous(sequences: list[int]) -> bool:

    if not sequences:

        return False

    return sequences == list(range(1, len(sequences) + 1))





def _assistant_by_id(snapshot: dict, message_id: str) -> dict | None:

    messages = (snapshot.get("data") or {}).get("messages") or []

    for message in messages:

        if message.get("message_id") == message_id and message.get("role") == "assistant":

            return message

    return None





async def _snapshot_after(session_id: str, token: str) -> dict:

    connection, snapshot = await _open(session_id, token)

    await connection.close()

    return snapshot





async def _run(token: str) -> int:

    session_complete = f"asc-{uuid.uuid4().hex[:12]}"

    session_interrupt = f"asi-{uuid.uuid4().hex[:12]}"

    session_refusal = f"asr-{uuid.uuid4().hex[:12]}"

    print("SESSION_COMPLETE", session_complete)

    print("SESSION_INTERRUPT", session_interrupt)

    print("SESSION_REFUSAL", session_refusal)



    print("PHASE", "complete")

    connection, _ = await _open(session_complete, token)

    await connection.send(

        json.dumps(

            {

                "event": "user_message",

                "data": {"session_id": session_complete, "text": POLICY_QUESTION},

            }

        )

    )

    complete_events = await _collect_until(connection, "generation_completed")

    await connection.close()

    names = [item.get("event") for item in complete_events]

    tokens, sequences, assembled = _token_stream(complete_events)

    completed = complete_events[-1]

    complete_message_id = str((completed.get("data") or {}).get("message_id", ""))

    snapshot = await _snapshot_after(session_complete, token)

    assistant = _assistant_by_id(snapshot, complete_message_id)

    snapshot_text = "" if assistant is None else str(assistant.get("text", ""))

    stream_matches_snapshot = assistant is not None and assembled == snapshot_text

    sequences_ok = _sequences_contiguous(sequences)

    print("COMPLETE_EVENTS", ",".join(str(name) for name in names))

    print("COMPLETE_MESSAGE_ID", complete_message_id or "missing")

    print("COMPLETE_TOKEN_COUNT", len(tokens))

    print("COMPLETE_CHARS", len(assembled))

    print("COMPLETE_SEQUENCES_CONTIGUOUS", sequences_ok)

    print("COMPLETE_STREAM_EQUALS_SNAPSHOT", stream_matches_snapshot)

    print("COMPLETE_SNAPSHOT_CHARS", len(snapshot_text))

    print("COMPLETE_HAS_PRIVATE_PAY", "private-pay" in assembled.lower())

    print("COMPLETE_ENDS_WITH_COMPLETED", names[-1] == "generation_completed")

    print(

        "COMPLETE_PHI_MATCHES",

        ",".join(term for term in PHI_TERMS if term in assembled.lower()) or "none",

    )

    if not stream_matches_snapshot:

        print(

            "COMPLETE_INTEGRITY_LIMIT",

            "public protocol compared token_chunk assembly to session_snapshot "

            "assistant.text for generation_completed.message_id; mismatch or missing message",

        )



    print("PHASE", "interrupt")

    connection, _ = await _open(session_interrupt, token)

    await connection.send(

        json.dumps(

            {

                "event": "user_message",

                "data": {"session_id": session_interrupt, "text": POLICY_QUESTION},

            }

        )

    )

    first = await _collect_until(connection, "token_chunk")

    await connection.send(

        json.dumps(

            {

                "event": "interrupt_requested",

                "data": {

                    "session_id": session_interrupt,

                    "new_input": "When is the last reminder sent before an appointment?",

                },

            }

        )

    )

    rest = await _collect_until(connection, "generation_interrupted")

    follow = await _collect_until(connection, "generation_completed")

    await connection.close()

    interrupt_events = first + rest

    interrupt_names = [item.get("event") for item in interrupt_events]

    follow_names = [item.get("event") for item in follow]

    interrupted_message_id = str(

        ((rest[-1].get("data") or {}).get("message_id") if rest else "") or ""

    )

    follow_message_id = str(

        ((follow[-1].get("data") or {}).get("message_id") if follow else "") or ""

    )

    interrupt_tokens, interrupt_sequences, interrupt_assembled = _token_stream(

        interrupt_events

    )

    follow_tokens, follow_sequences, follow_assembled = _token_stream(follow)

    interrupt_snapshot = await _snapshot_after(session_interrupt, token)

    interrupted_assistant = _assistant_by_id(interrupt_snapshot, interrupted_message_id)

    follow_assistant = _assistant_by_id(interrupt_snapshot, follow_message_id)

    interrupt_snapshot_text = (

        "" if interrupted_assistant is None else str(interrupted_assistant.get("text", ""))

    )

    follow_snapshot_text = (

        "" if follow_assistant is None else str(follow_assistant.get("text", ""))

    )

    interrupt_status = (

        None if interrupted_assistant is None else interrupted_assistant.get("status")

    )

    interrupt_stream_matches = (

        interrupted_assistant is not None and interrupt_assembled == interrupt_snapshot_text

    )

    follow_stream_matches = (

        follow_assistant is not None and follow_assembled == follow_snapshot_text

    )

    distinct_generations = (

        bool(interrupted_message_id)

        and bool(follow_message_id)

        and interrupted_message_id != follow_message_id

    )

    print("INTERRUPT_EVENTS", ",".join(str(name) for name in interrupt_names))

    print("INTERRUPT_MESSAGE_ID", interrupted_message_id or "missing")

    print("INTERRUPT_HAS_INTERRUPTED", "generation_interrupted" in interrupt_names)

    print("INTERRUPT_SNAPSHOT_STATUS", interrupt_status or "missing")

    print("INTERRUPT_STREAM_EQUALS_SNAPSHOT", interrupt_stream_matches)

    print("INTERRUPT_SEQUENCES_CONTIGUOUS", _sequences_contiguous(interrupt_sequences))

    print("FOLLOW_MESSAGE_ID", follow_message_id or "missing")

    print("FOLLOW_EVENTS_TAIL", ",".join(str(name) for name in follow_names[-3:]))

    print("FOLLOW_TOKEN_COUNT", len(follow_tokens))

    print("FOLLOW_COMPLETED", follow_names[-1] == "generation_completed")

    print("FOLLOW_STREAM_EQUALS_SNAPSHOT", follow_stream_matches)

    print("FOLLOW_SEQUENCES_CONTIGUOUS", _sequences_contiguous(follow_sequences))

    print("INTERRUPT_FOLLOW_DISTINCT_MESSAGE_IDS", distinct_generations)

    print(

        "INTERRUPT_FOLLOW_TEXTS_DIFFER",

        interrupt_assembled != follow_assembled and bool(follow_assembled),

    )



    print("PHASE", "refusal")

    connection, _ = await _open(session_refusal, token)

    await connection.send(

        json.dumps(

            {

                "event": "user_message",

                "data": {"session_id": session_refusal, "text": REFUSAL_QUESTION},

            }

        )

    )

    refusal_events = await _collect_until(connection, "generation_completed")

    await connection.close()

    refusal_completed = refusal_events[-1]

    refusal_message_id = str((refusal_completed.get("data") or {}).get("message_id", ""))

    refusal_tokens, refusal_sequences, refusal_assembled = _token_stream(refusal_events)

    refusal_snapshot = await _snapshot_after(session_refusal, token)

    refusal_assistant = _assistant_by_id(refusal_snapshot, refusal_message_id)

    refusal_snapshot_text = (

        "" if refusal_assistant is None else str(refusal_assistant.get("text", ""))

    )

    refusal_stream_matches = (

        refusal_assistant is not None and refusal_assembled == refusal_snapshot_text

    )

    refusal_lower = refusal_assembled.lower()

    print("REFUSAL_MESSAGE_ID", refusal_message_id or "missing")

    print("REFUSAL_TOKEN_COUNT", len(refusal_tokens))

    print("REFUSAL_CHARS", len(refusal_assembled))

    print("REFUSAL_STREAM_EQUALS_SNAPSHOT", refusal_stream_matches)

    print(

        "REFUSAL_SEQUENCES_CONTIGUOUS",

        (not refusal_sequences) or _sequences_contiguous(refusal_sequences),

    )

    print("REFUSAL_HAS_CATEGORY", "medical record" in refusal_lower)

    print(

        "REFUSAL_PHI_MATCHES",

        ",".join(term for term in PHI_TERMS if term in refusal_lower) or "none",

    )

    if len(refusal_tokens) == 0:

        print(

            "REFUSAL_STREAM_LIMIT",

            "public stream had zero token_chunk events; category absence is for "

            "the streamed/snapshot text only, not an unpublished agent return string",

        )



    complete_ok = (

        names[-1] == "generation_completed"

        and bool(complete_message_id)

        and len(tokens) > 0

        and sequences_ok

        and stream_matches_snapshot

        and "private-pay" in assembled.lower()

    )

    interrupt_ok = (

        "generation_interrupted" in interrupt_names

        and interrupt_status == "interrupted"

        and interrupt_stream_matches

        and follow_names[-1] == "generation_completed"

        and len(follow_tokens) > 0

        and follow_stream_matches

        and _sequences_contiguous(follow_sequences)

        and distinct_generations

        and interrupt_assembled != follow_assembled

    )

    refusal_ok = (

        refusal_events[-1].get("event") == "generation_completed"

        and refusal_stream_matches

        and "medical record" not in refusal_lower

    )

    passed = complete_ok and interrupt_ok and refusal_ok

    print("COMPLETE_OK", complete_ok)

    print("INTERRUPT_OK", interrupt_ok)

    print("REFUSAL_OK", refusal_ok)

    print("PUBLIC_WSS_STREAM_PASSED" if passed else "PUBLIC_WSS_STREAM_FAILED")

    return 0 if passed else 1





def main() -> int:

    print("LOCAL", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))

    print("PROBE_EMAIL", EMAIL)

    password = secrets.token_urlsafe(18)

    register_status, _ = _request(

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

        return 1

    if register_status not in (200, 201) and register_status != 400:

        print("REGISTER_UNEXPECTED", register_status)

    try:

        return asyncio.run(_run(token))

    except ConnectionClosed as exc:

        print(

            "WSS_ERROR",

            type(exc).__name__,

            "code",

            getattr(exc, "code", ""),

            "reason",

            getattr(exc, "reason", ""),

        )

        return 1

    except (TimeoutError, RuntimeError, json.JSONDecodeError, TypeError, ValueError) as exc:

        print("WSS_ERROR", type(exc).__name__, str(exc)[:120])

        return 1





if __name__ == "__main__":

    raise SystemExit(main())
