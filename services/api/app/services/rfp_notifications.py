"""In-process SSE fan-out for a classified RFP that is still analyzing.

One API process keeps the buffer and the subscriber queues. A second process
would not see them. There is no broker and no ticket-list refetch.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import uuid
from collections import deque
from collections.abc import AsyncIterator

logger = logging.getLogger("healthcore.rfp_notifications")

BUFFER_LIMIT = 50
DEFAULT_KEEPALIVE_SECONDS = 15.0

# Tests shorten the idle wait. Production leaves the 15 second default.
keepalive_seconds = DEFAULT_KEEPALIVE_SECONDS
# Tests hold the subscribe lock between the snapshot and registration.
# Production leaves this unset.
during_subscribe = None
# Tests end the HTTP body after this many yielded chunks. Production is unlimited.
stop_after_chunks: int | None = None

_lock = threading.Lock()
_boot_id = uuid.uuid4().hex
_sequence = 0
_buffer: deque[tuple[str, str]] = deque(maxlen=BUFFER_LIMIT)
_subscribers: list[queue.Queue[str]] = []


def reset_for_tests() -> None:
    """Drop process-local frames so one test cannot replay another test's ticket."""
    global _boot_id, _sequence, keepalive_seconds, during_subscribe, stop_after_chunks
    with _lock:
        _boot_id = uuid.uuid4().hex
        _sequence = 0
        _buffer.clear()
        _subscribers.clear()
    keepalive_seconds = DEFAULT_KEEPALIVE_SECONDS
    during_subscribe = None
    stop_after_chunks = None


def _frame(event_id: str, payload: dict[str, str]) -> str:
    # Flat JSON. The event name is the SSE event field, not a nested object.
    data = json.dumps(payload, separators=(",", ":"))
    return f"id: {event_id}\nevent: rfp_ticket_created\ndata: {data}\n\n"


def publish_ticket_created(
    *,
    ticket_id: str,
    rfp_id: str,
    status: str,
    created_at: str,
) -> str:
    """Append one frame and copy it onto queues that are already registered."""
    global _sequence
    payload = {
        "ticket_id": ticket_id,
        "rfp_id": rfp_id,
        "status": status,
        "created_at": created_at,
    }
    with _lock:
        _sequence += 1
        event_id = f"{_boot_id}:{_sequence}"
        frame = _frame(event_id, payload)
        _buffer.append((event_id, frame))
        subscribers = list(_subscribers)
    logger.info(
        "event=rfp_ticket_created ticket_id=%s rfp_id=%s status=%s",
        ticket_id,
        rfp_id,
        status,
    )
    for subscriber in subscribers:
        subscriber.put(frame)
    return event_id


def _replay(last_event_id: str | None) -> tuple[list[str], bool]:
    """Return buffered frames and whether the cursor is outside this process.

    No id replays the whole buffer. A known id replays only later frames.
    A foreign boot id, or an id that has left the buffer, is a gap.
    """
    if not last_event_id:
        return [frame for _event_id, frame in _buffer], False
    event_ids = [event_id for event_id, _frame in _buffer]
    if last_event_id not in event_ids:
        return [], True
    cursor = event_ids.index(last_event_id)
    return [frame for _event_id, frame in list(_buffer)[cursor + 1 :]], False


def subscribe(last_event_id: str | None) -> tuple[list[str], bool, queue.Queue[str]]:
    """Copy the replay slice and register the live queue under one lock.

    A publish that arrives before this lock is in the snapshot. A publish that
    waits on the lock is in the queue. The two sets do not leave a gap.
    """
    subscriber: queue.Queue[str] = queue.Queue()
    with _lock:
        frames, gap = _replay(last_event_id)
        hook = during_subscribe
        if hook is not None:
            hook()
        _subscribers.append(subscriber)
    return frames, gap, subscriber


def unsubscribe(subscriber: queue.Queue[str]) -> None:
    with _lock:
        if subscriber in _subscribers:
            _subscribers.remove(subscriber)


async def event_stream(last_event_id: str | None) -> AsyncIterator[str]:
    """Write the replay, then live frames, with keepalive comments while idle.

    The queue wait runs off the event loop so an already yielded frame can
    reach the client before the next keepalive.
    """
    frames, gap, subscriber = subscribe(last_event_id)
    emitted = 0

    def _emit(chunk: str) -> str:
        nonlocal emitted
        emitted += 1
        return chunk

    try:
        if gap:
            yield _emit(": replay-gap\n\n")
            if stop_after_chunks is not None and emitted >= stop_after_chunks:
                return
        for frame in frames:
            yield _emit(frame)
            if stop_after_chunks is not None and emitted >= stop_after_chunks:
                return
        while stop_after_chunks is None or emitted < stop_after_chunks:
            try:
                frame = await asyncio.to_thread(subscriber.get, True, keepalive_seconds)
            except queue.Empty:
                yield _emit(": keepalive\n\n")
            else:
                yield _emit(frame)
            if stop_after_chunks is not None and emitted >= stop_after_chunks:
                return
    finally:
        unsubscribe(subscriber)
