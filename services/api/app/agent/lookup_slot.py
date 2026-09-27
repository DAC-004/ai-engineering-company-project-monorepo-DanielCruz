"""One-slot wait for an in-process incident read.

The integrated incident service uses one unguarded TinyDB handle and has no
cancellation token. This module therefore allows one read at a time. It does
not use ``ThreadPoolExecutor``: that pool's atexit hook joins workers, so a
read that never returns would hold interpreter shutdown.

Clean shutdown is limited, not guaranteed. The worker is a daemon, so process
exit does not join it and does not wait for a hung read. That also means
TinyDB is not closed cleanly if a read is still inside the service. The hung
read cannot be stopped. The slot stays held, and later lookups fail immediately
with capacity, until that read returns and the worker releases the lock.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, TypeVar

INCIDENT_LOOKUP_TIMEOUT_SECONDS = 5

_T = TypeVar("_T")

_slot = threading.Lock()
_cell_lock = threading.Lock()
_worker_guard = threading.Lock()
_in_flight_lock = threading.Lock()
_wake = threading.Event()
_worker: threading.Thread | None = None
_cell: _Job | None = None
_in_flight = 0
_handoff_count = 0


@dataclass
class _Job:
    fn: Callable[[], object]
    done: threading.Event
    lock: threading.Lock
    result: object | None = None
    error: BaseException | None = None
    timed_out: bool = False


@dataclass(frozen=True)
class BoundedRead:
    """Result of one admission attempt. ``rows`` is set only on success."""

    failure: str | None = None
    rows: object | None = None
    error: BaseException | None = None


def in_flight_count() -> int:
    with _in_flight_lock:
        return _in_flight


def handoff_count() -> int:
    with _cell_lock:
        return _handoff_count


def worker_is_daemon() -> bool:
    with _worker_guard:
        return _worker is not None and _worker.daemon and _worker.is_alive()


def run_bounded_read(read: Callable[[], _T]) -> BoundedRead:
    """Run ``read`` on the single worker, or fail without queueing.

    The caller claims the slot with ``Lock.acquire(blocking=False)``. The
    loser does not publish a job and does not wait. The winner waits at most
    ``INCIDENT_LOOKUP_TIMEOUT_SECONDS`` and does not release the slot on
    timeout. The worker releases it only after ``read`` returns, and it drops
    a result the waiter already abandoned.
    """
    if not _slot.acquire(blocking=False):
        return BoundedRead(failure="capacity")
    _ensure_worker()
    job = _Job(fn=read, done=threading.Event(), lock=threading.Lock())
    try:
        _publish(job)
    except Exception:
        _slot.release()
        raise
    finished = job.done.wait(INCIDENT_LOOKUP_TIMEOUT_SECONDS)
    if not finished:
        with job.lock:
            job.timed_out = True
        return BoundedRead(failure="timeout")
    with job.lock:
        if job.error is not None:
            return BoundedRead(failure="error", error=job.error)
        return BoundedRead(rows=job.result)


def _ensure_worker() -> None:
    global _worker
    with _worker_guard:
        if _worker is not None and _worker.is_alive():
            return
        worker = threading.Thread(
            target=_worker_loop,
            name="incident-lookup-slot",
            daemon=True,
        )
        worker.start()
        _worker = worker


def _publish(job: _Job) -> None:
    """Hand one job to the idle worker through the single cell."""
    global _cell, _handoff_count
    with _cell_lock:
        if _cell is not None:
            raise RuntimeError("The incident lookup slot already has a job.")
        _cell = job
        _handoff_count += 1
    _wake.set()


def _take() -> _Job | None:
    global _cell
    with _cell_lock:
        job = _cell
        _cell = None
        return job


def _worker_loop() -> None:
    global _in_flight
    while True:
        job = _take()
        if job is None:
            _wake.wait()
            _wake.clear()
            continue
        result: object | None = None
        error: BaseException | None = None
        with _in_flight_lock:
            _in_flight += 1
        try:
            result = job.fn()
        except Exception as exc:
            error = exc
        finally:
            with _in_flight_lock:
                _in_flight -= 1
            with job.lock:
                if job.timed_out:
                    job.result = None
                    job.error = None
                else:
                    job.result = result
                    job.error = error
            job.done.set()
            _slot.release()
