"""Process-safe IP throttles for auth/recovery and critical write requests."""

from __future__ import annotations
import hashlib
import math
import os
import sqlite3
import time
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.config import get_settings


def budget(path, method):
    if method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    limits = {
        "/auth/login": 10,
        "/auth/forgot-password": 5,
        "/auth/reset-password": 10,
        "/auth/change-password": 10,
    }
    if path in limits:
        return path, limits[path]
    if path == "/telemetry/events":
        return "telemetry", 600
    return "critical_write", 60


def take(client, group, maximum, now=None):
    now = time.time() if now is None else now
    window = int(now // 60)
    key = hashlib.sha256((client + "|" + group).encode()).hexdigest()
    configured = os.environ.get("SECURITY_RATE_LIMIT_DB_PATH", "").strip()
    path = (
        Path(configured).resolve()
        if configured
        else Path(get_settings().tinydb_path).resolve().parent / "rate-limits.sqlite3"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=5) as db:
        db.execute("PRAGMA busy_timeout=5000")
        db.execute(
            "CREATE TABLE IF NOT EXISTS limits (key TEXT, window INTEGER, used INTEGER NOT NULL, PRIMARY KEY(key,window))"
        )
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM limits WHERE window < ?", (window - 1,))
        row = db.execute(
            "SELECT used FROM limits WHERE key=? AND window=?", (key, window)
        ).fetchone()
        used = row[0] if row else 0
        if used >= maximum:
            return False, max(1, math.ceil((window + 1) * 60 - now))
        db.execute(
            "INSERT INTO limits VALUES(?,?,1) ON CONFLICT(key,window) DO UPDATE SET used=used+1",
            (key, window),
        )
    return True, 0


class SensitiveRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        selected = budget(request.url.path, request.method)
        if selected is not None:
            # Forwarded headers are untrusted. Configure trusted proxy handling
            # in the ASGI server; never let an arbitrary X-Forwarded-For bypass us.
            client = request.client.host if request.client else "unknown"
            try:
                from starlette.concurrency import run_in_threadpool

                allowed, retry = await run_in_threadpool(take, client, *selected)
            except (sqlite3.Error, OSError):
                return JSONResponse({"detail": "Security control unavailable"}, status_code=503)
            if not allowed:
                return JSONResponse(
                    {"detail": "Too many requests; try again later"},
                    status_code=429,
                    headers={"Retry-After": str(retry)},
                )
        return await call_next(request)
