"""Fixed-window limit for endpoints that invoke a language model.

The limit is per client address and endpoint. It stops a caller from looping
model calls. It does not log the request body.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_WINDOWS: dict[tuple[str, str], tuple[float, int]] = defaultdict(lambda: (0.0, 0))


def _limit() -> int:
    raw = os.environ.get("MODEL_RATE_LIMIT_REQUESTS", "30")
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 30
    return parsed if parsed > 0 else 30


def _window_seconds() -> float:
    raw = os.environ.get("MODEL_RATE_LIMIT_WINDOW_SECONDS", "60")
    try:
        parsed = float(raw)
    except ValueError:
        parsed = 60.0
    return parsed if parsed > 0 else 60.0


def reset_model_rate_limit() -> None:
    """Clear windows so one test process does not inherit another."""
    with _LOCK:
        _WINDOWS.clear()


def allow_model_call(endpoint: str, client_key: str, *, now: float | None = None) -> bool:
    """Return True when this caller is still inside the current window."""
    clock = time.monotonic() if now is None else now
    window = _window_seconds()
    maximum = _limit()
    key = (endpoint, client_key)
    with _LOCK:
        started, count = _WINDOWS.get(key, (clock, 0))
        if clock - started >= window:
            started, count = clock, 0
        if count >= maximum:
            _WINDOWS[key] = (started, count)
            return False
        _WINDOWS[key] = (started, count + 1)
        return True


def enforce_model_rate_limit(endpoint: str, request: Request) -> None:
    """Reject the call before the route invokes a model."""
    client = request.client.host if request.client is not None else "unknown"
    if allow_model_call(endpoint, client):
        logger.info("model_rate_limit endpoint=%s result=allowed", endpoint)
        return
    logger.info("model_rate_limit endpoint=%s result=blocked", endpoint)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Model request rate limit exceeded. Retry later.",
    )
