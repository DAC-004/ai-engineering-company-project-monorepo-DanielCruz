"""Durable encrypted password-reset outbox; broker messages contain only UUIDs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, MultiFernet
from app.core.config import get_settings

MAX_ATTEMPTS = 3
LEASE_SECONDS = 120


def outbox_path():
    return Path(get_settings().tinydb_path).resolve().parent / "email-outbox.sqlite3"


def cipher():
    # Encrypt only with the active key; decrypt with the same bounded overlap
    # used by JWT verification so queued resets survive planned key rotation.
    settings = get_settings()
    secrets = [settings.secret_key] + [key.strip() for key in settings.jwt_previous_secret_keys.split(",") if key.strip()]
    keys = [
        Fernet(base64.urlsafe_b64encode(hmac.new(secret.encode(), b"healthcore/email-outbox/v1", hashlib.sha256).digest()))
        for secret in secrets[:4]
    ]
    return MultiFernet(keys)


@contextmanager
def connection():
    path = outbox_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(
        "CREATE TABLE IF NOT EXISTS email_jobs (id TEXT PRIMARY KEY, ciphertext BLOB, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, available REAL NOT NULL, lease REAL, expires REAL NOT NULL, provider_id TEXT, error_code TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS email_dead_letters (id TEXT PRIMARY KEY, attempts INTEGER NOT NULL, error_code TEXT NOT NULL, failed_at REAL NOT NULL)"
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()


def create_job(*, user_id, to_email, reset_url):
    job_id = str(uuid4())
    encrypted = cipher().encrypt(
        json.dumps({"user_id": user_id, "to_email": to_email, "reset_url": reset_url}).encode()
    )
    now = time.time()
    with connection() as db:
        db.execute(
            "INSERT INTO email_jobs(id,ciphertext,state,available,expires) VALUES(?,?,?,?,?)",
            (
                job_id,
                encrypted,
                "pending",
                now,
                now + min(get_settings().password_reset_token_expire_minutes * 60, 23 * 3600),
            ),
        )
        db.commit()
    return job_id


def public_status(job_id):
    job_id = str(UUID(job_id))
    with connection() as db:
        row = db.execute(
            "SELECT id,state,attempts,available,expires,error_code FROM email_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def dead_letters():
    with connection() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT id,attempts,error_code,failed_at FROM email_dead_letters ORDER BY failed_at DESC LIMIT 100"
            )
        ]


def pending_jobs():
    now = time.time()
    with connection() as db:
        return [
            row[0]
            for row in db.execute(
                "SELECT id FROM email_jobs WHERE (state='pending' AND available<=?) OR (state='in_progress' AND lease<=?) ORDER BY available LIMIT 100",
                (now, now),
            )
        ]


def _terminal(db, job_id, attempts, code, now):
    db.execute(
        "UPDATE email_jobs SET state='failed',ciphertext=NULL,lease=NULL,error_code=? WHERE id=?",
        (code, job_id),
    )
    db.execute(
        "INSERT OR IGNORE INTO email_dead_letters VALUES(?,?,?,?)", (job_id, attempts, code, now)
    )


def claim(job_id):
    job_id = str(UUID(job_id))
    now = time.time()
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM email_jobs WHERE id=?", (job_id,)).fetchone()
        if not row or row["state"] in {"completed", "failed"}:
            db.commit()
            return None
        if row["expires"] <= now or row["attempts"] >= MAX_ATTEMPTS:
            _terminal(db, job_id, row["attempts"], "expired_or_exhausted", now)
            db.commit()
            return None
        if row["state"] == "in_progress" and row["lease"] > now or row["available"] > now:
            db.commit()
            return None
        db.execute(
            "UPDATE email_jobs SET state='in_progress',attempts=attempts+1,lease=? WHERE id=?",
            (now + LEASE_SECONDS, job_id),
        )
        db.commit()
    try:
        payload = json.loads(cipher().decrypt(row["ciphertext"]))
    except Exception:
        fail(job_id, "configuration_or_payload_error", permanent=True)
        return None
    return payload


def complete(job_id, provider_id):
    with connection() as db:
        db.execute(
            "UPDATE email_jobs SET state='completed',ciphertext=NULL,lease=NULL,provider_id=?,error_code=NULL WHERE id=? AND state='in_progress'",
            (provider_id, job_id),
        )
        db.commit()


def fail(job_id, code="provider_unavailable", *, permanent=False):
    now = time.time()
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT attempts FROM email_jobs WHERE id=? AND state='in_progress'", (job_id,)
        ).fetchone()
        if not row:
            db.commit()
            return None
        attempts = row["attempts"]
        if permanent or attempts >= MAX_ATTEMPTS:
            _terminal(db, job_id, attempts, code, now)
            delay = None
        else:
            delay = 2**attempts
            db.execute(
                "UPDATE email_jobs SET state='pending',available=?,lease=NULL,error_code=? WHERE id=?",
                (now + delay, code, job_id),
            )
        db.commit()
    return delay


def enqueue_reset_email(*, user_id, to_email, reset_url):
    job_id = create_job(user_id=user_id, to_email=to_email, reset_url=reset_url)
    from app.email_tasks import deliver_reset_email

    try:
        deliver_reset_email.apply_async(args=[job_id], task_id=job_id, queue="email")
    except Exception:
        # Durable pending row is reconciled by the independent periodic dispatcher.
        # Do not copy broker errors or the reset URL into logs.
        import logging

        logging.getLogger(__name__).warning("email_publish_pending operation=%s", job_id)
    return job_id
