"""SQLite close/draft/outbox store with CAS on version, hash, and nonce."""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agents.financial_close.privacy import assert_clean_mapping

JOB_LEASE_SECONDS = 30
RUN_LEASE_SECONDS = 30


class PeriodRunBusy(ValueError):
    def __init__(self, reason: str, draft_id: str | None = None) -> None:
        super().__init__(reason)
        self.draft_id = draft_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS closes (
  period TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  catch_up INTEGER NOT NULL,
  facts_digest TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
  draft_id TEXT PRIMARY KEY,
  period TEXT NOT NULL,
  version INTEGER NOT NULL,
  content_sha256 TEXT NOT NULL,
  approval_nonce TEXT NOT NULL,
  state TEXT NOT NULL,
  report_json TEXT NOT NULL,
  comments TEXT,
  parent_version INTEGER,
  UNIQUE(period, version)
);
CREATE TABLE IF NOT EXISTS run_claims (
  period TEXT NOT NULL,
  facts_digest TEXT NOT NULL,
  owner TEXT NOT NULL,
  lease_until TEXT NOT NULL,
  draft_id TEXT,
  PRIMARY KEY (period, facts_digest)
);
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  notice_key TEXT NOT NULL UNIQUE,
  period TEXT NOT NULL,
  version INTEGER NOT NULL,
  recipient_email TEXT NOT NULL,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  celery_task_id TEXT,
  actor_email TEXT NOT NULL,
  state TEXT NOT NULL,
  result_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  period TEXT,
  owner TEXT
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  action TEXT NOT NULL,
  details_json TEXT NOT NULL
);
"""


class StaleDraftError(ValueError):
    pass


class CloseStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(outbox)")}
        if columns and "notice_key" not in columns:
            conn.execute("ALTER TABLE outbox RENAME TO outbox_legacy")
            conn.executescript(
                """
                CREATE TABLE outbox (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  notice_key TEXT NOT NULL UNIQUE,
                  period TEXT NOT NULL,
                  version INTEGER NOT NULL,
                  recipient_email TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )
            for row in conn.execute("SELECT * FROM outbox_legacy"):
                notice_key = f"{row['kind']}:{row['period']}:{row['version']}:{row['recipient_email']}:legacy-{row['id']}"
                conn.execute(
                    """
                    INSERT INTO outbox(notice_key, period, version, recipient_email, kind, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        notice_key,
                        row["period"],
                        row["version"],
                        row["recipient_email"],
                        row["kind"],
                        row["payload_json"],
                        row["created_at"],
                    ),
                )
            conn.execute("DROP TABLE outbox_legacy")
            conn.commit()
        job_tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "jobs" not in job_tables:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                  job_id TEXT PRIMARY KEY,
                  celery_task_id TEXT,
                  actor_email TEXT NOT NULL,
                  state TEXT NOT NULL,
                  result_json TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  period TEXT,
                  owner TEXT,
                  lease_until TEXT
                );
                """
            )
            conn.commit()
        job_cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        if job_cols and "period" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN period TEXT")
        if job_cols and "owner" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN owner TEXT")
        if job_cols and "lease_until" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN lease_until TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS drafts_period_version ON drafts(period, version)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_claims (
              period TEXT NOT NULL,
              facts_digest TEXT NOT NULL,
              owner TEXT NOT NULL,
              lease_until TEXT NOT NULL,
              draft_id TEXT,
              PRIMARY KEY (period, facts_digest)
            )
            """
        )
        conn.commit()

    def save_close(self, period: str, status: str, catch_up: bool, facts_digest: str, created_at: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO closes(period, status, catch_up, facts_digest, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(period) DO UPDATE SET
                  status=excluded.status,
                  catch_up=excluded.catch_up,
                  facts_digest=excluded.facts_digest
                """,
                (period, status, int(catch_up), facts_digest, created_at),
            )
            conn.commit()

    def get_close(self, period: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM closes WHERE period=?", (period,)).fetchone()
            return dict(row) if row else None

    def save_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        assert_clean_mapping({key: value for key, value in draft.items() if key != "report"})
        assert_clean_mapping(draft["report"])
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO drafts(
                  draft_id, period, version, content_sha256, approval_nonce, state, report_json, comments, parent_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft["draft_id"],
                    draft["period"],
                    int(draft["version"]),
                    draft["content_sha256"],
                    draft["approval_nonce"],
                    draft["state"],
                    json.dumps(draft["report"]),
                    draft.get("comments"),
                    draft.get("parent_version"),
                ),
            )
            conn.commit()
        return draft

    def reject_and_insert_successor(self, parent_id: str, successor: dict[str, Any], *, comments: str) -> dict[str, Any]:
        assert_clean_mapping({key: value for key, value in successor.items() if key != "report"})
        assert_clean_mapping(successor["report"])
        created = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            parent = conn.execute("SELECT * FROM drafts WHERE draft_id=?", (parent_id,)).fetchone()
            if parent is None:
                conn.commit()
                raise KeyError("unknown_draft")
            if parent["state"] not in {"awaiting_tom", "rejected"}:
                conn.commit()
                raise StaleDraftError("concurrent_terminal_state")
            existing = conn.execute(
                "SELECT * FROM drafts WHERE period=? AND parent_version=? AND state!='rejected' ORDER BY version DESC",
                (parent["period"], int(parent["version"])),
            ).fetchone()
            if existing is not None:
                conn.commit()
                return self._draft_from_row(existing)
            row = conn.execute("SELECT MAX(version) AS highest FROM drafts WHERE period=?", (parent["period"],)).fetchone()
            version = int(row["highest"] or 0) + 1
            successor["version"] = version
            successor["parent_version"] = int(parent["version"])
            import secrets as nonce_secrets

            conn.execute(
                """
                UPDATE drafts SET state='rejected', comments=?, approval_nonce=?
                WHERE draft_id=?
                """,
                (comments, nonce_secrets.token_hex(16), parent_id),
            )
            conn.execute(
                """
                INSERT INTO drafts(
                  draft_id, period, version, content_sha256, approval_nonce, state, report_json, comments, parent_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    successor["draft_id"],
                    successor["period"],
                    version,
                    successor["content_sha256"],
                    successor["approval_nonce"],
                    successor["state"],
                    json.dumps(successor["report"]),
                    successor.get("comments"),
                    successor["parent_version"],
                ),
            )
            conn.execute(
                """
                INSERT INTO closes(period, status, catch_up, facts_digest, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(period) DO UPDATE SET
                  status=excluded.status,
                  catch_up=excluded.catch_up,
                  facts_digest=excluded.facts_digest
                """,
                (
                    successor["period"],
                    "awaiting_tom",
                    int(bool(successor["report"].get("catch_up"))),
                    successor["report"]["facts_digest"],
                    created,
                ),
            )
            conn.execute(
                "UPDATE run_claims SET draft_id=? WHERE period=? AND facts_digest=?",
                (successor["draft_id"], successor["period"], successor["report"]["facts_digest"]),
            )
            conn.commit()
        return successor

    def get_draft(self, draft_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
            return self._draft_from_row(row) if row else None

    def list_drafts(self, period: str | None = None) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            if period:
                rows = conn.execute(
                    "SELECT * FROM drafts WHERE period=? ORDER BY version",
                    (period,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM drafts ORDER BY period, version").fetchall()
            return [self._draft_from_row(row) for row in rows]

    def cas_update_draft(
        self,
        draft_id: str,
        *,
        expected_nonce: str,
        expected_version: int,
        expected_hash: str,
        updater,
    ) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
            if row is None:
                raise KeyError("unknown_draft")
            current = self._draft_from_row(row)
            if int(current["version"]) != expected_version:
                raise StaleDraftError("stale_draft_version")
            if current["content_sha256"] != expected_hash:
                raise StaleDraftError("stale_draft_hash")
            if current["approval_nonce"] != expected_nonce:
                raise StaleDraftError("stale_or_replayed_nonce")
            updated = updater(dict(current))
            assert_clean_mapping({key: value for key, value in updated.items() if key != "report"})
            assert_clean_mapping(updated["report"])
            conn.execute(
                """
                UPDATE drafts SET version=?, content_sha256=?, approval_nonce=?, state=?,
                  report_json=?, comments=?, parent_version=?
                WHERE draft_id=?
                """,
                (
                    int(updated["version"]),
                    updated["content_sha256"],
                    updated["approval_nonce"],
                    updated["state"],
                    json.dumps(updated["report"]),
                    updated.get("comments"),
                    updated.get("parent_version"),
                    draft_id,
                ),
            )
            conn.commit()
            return updated

    def _insert_outbox(self, conn: sqlite3.Connection, item: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO outbox(notice_key, period, version, recipient_email, kind, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["notice_key"],
                item["period"],
                int(item["version"]),
                item["recipient_email"],
                item["kind"],
                json.dumps(item.get("payload", {})),
                item["created_at"],
            ),
        )

    def approve_and_enqueue(
        self,
        draft_id: str,
        *,
        expected_nonce: str,
        expected_version: int,
        expected_hash: str,
        facts_digest: str,
        notices: list[dict[str, Any]],
        catch_up: bool,
    ) -> dict[str, Any]:
        created = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT * FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
                if row is None:
                    raise KeyError("unknown_draft")
                current = self._draft_from_row(row)
                if int(current["version"]) != expected_version:
                    raise StaleDraftError("stale_draft_version")
                if current["content_sha256"] != expected_hash:
                    raise StaleDraftError("stale_draft_hash")
                if current["state"] == "approved":
                    for item in notices:
                        self._insert_outbox(conn, item)
                    conn.commit()
                    return current
                if current["state"] != "awaiting_tom":
                    raise StaleDraftError("concurrent_terminal_state")
                if current["approval_nonce"] != expected_nonce:
                    raise StaleDraftError("stale_or_replayed_nonce")
                if current["report"].get("facts_digest") != facts_digest:
                    raise StaleDraftError("stale_source_digest")
                current["state"] = "approved"
                current["approval_nonce"] = secrets.token_hex(16)
                conn.execute(
                    """
                    UPDATE drafts SET approval_nonce=?, state=? WHERE draft_id=?
                    """,
                    (current["approval_nonce"], current["state"], draft_id),
                )
                for item in notices:
                    self._insert_outbox(conn, item)
                conn.execute(
                    """
                    INSERT INTO closes(period, status, catch_up, facts_digest, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(period) DO UPDATE SET
                      status=excluded.status,
                      catch_up=excluded.catch_up,
                      facts_digest=excluded.facts_digest
                    """,
                    (current["period"], "approved", int(catch_up), facts_digest, created),
                )
                conn.commit()
                return current
            except Exception:
                conn.rollback()
                raise

    def append_outbox(self, item: dict[str, Any]) -> bool:
        if item.get("kind") not in {"privacy_quarantine", "approved_report"}:
            raise ValueError("invalid_outbox_kind")
        assert_clean_mapping(item)
        notice_key = item["notice_key"]
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT 1 FROM outbox WHERE notice_key=?", (notice_key,)).fetchone()
            if existing:
                conn.commit()
                return False
            conn.execute(
                """
                INSERT INTO outbox(notice_key, period, version, recipient_email, kind, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notice_key,
                    item["period"],
                    int(item["version"]),
                    item["recipient_email"],
                    item["kind"],
                    json.dumps(item.get("payload", {})),
                    item["created_at"],
                ),
            )
            conn.commit()
            return True

    def list_outbox(self, period: str | None = None) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            if period:
                rows = conn.execute("SELECT * FROM outbox WHERE period=?", (period,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM outbox").fetchall()
            return [dict(row) for row in rows]

    def save_job(self, job: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs(job_id, celery_task_id, actor_email, state, result_json, created_at, updated_at, period, owner)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                  celery_task_id=excluded.celery_task_id,
                  state=excluded.state,
                  result_json=excluded.result_json,
                  updated_at=excluded.updated_at,
                  period=excluded.period,
                  owner=excluded.owner
                """,
                (
                    job["job_id"],
                    job.get("celery_task_id"),
                    job["actor_email"],
                    job["state"],
                    json.dumps(job.get("result") or {}),
                    job["created_at"],
                    job["updated_at"],
                    job.get("period"),
                    job.get("owner"),
                ),
            )
            conn.commit()
        return job

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                return None
            payload = dict(row)
            raw = payload.pop("result_json")
            payload["result"] = json.loads(raw) if raw else {}
            return payload

    def next_version(self, period: str) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT MAX(version) AS highest FROM drafts WHERE period=?", (period,)).fetchone()
            highest = row["highest"] if row is not None else None
            return int(highest or 0) + 1

    def supersede_open_drafts(self, period: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE drafts SET state='superseded' WHERE period=? AND state='awaiting_tom'",
                (period,),
            )
            conn.commit()

    def successor_draft(self, period: str, parent_version: int) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM drafts
                WHERE period=? AND parent_version=? AND state != 'rejected'
                ORDER BY version DESC
                """,
                (period, int(parent_version)),
            ).fetchone()
            return self._draft_from_row(row) if row else None

    def active_job_for_period(self, period: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE period=? AND state IN ('queued','started') ORDER BY created_at DESC",
                (period,),
            ).fetchone()
            if row is None:
                return None
            payload = dict(row)
            raw = payload.pop("result_json")
            payload["result"] = json.loads(raw) if raw else {}
            return payload

    def claim_job(self, job_id: str, *, owner: str) -> tuple[str, dict[str, Any]]:
        now = datetime.now(timezone.utc)
        lease_until = (now + timedelta(seconds=JOB_LEASE_SECONDS)).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                conn.commit()
                raise KeyError("unknown_job")
            current = dict(row)
            raw = current.pop("result_json")
            current["result"] = json.loads(raw) if raw else {}
            state = current["state"]
            if state == "success":
                conn.commit()
                return "replay", current
            if state == "started":
                active = self._lease_is_active(current.get("lease_until"), now)
                conn.commit()
                if active:
                    return "busy", current
                return "recover", current
            if state != "queued":
                conn.commit()
                return "busy", current
            conn.execute(
                """
                UPDATE jobs SET state=?, owner=?, lease_until=?, updated_at=?
                WHERE job_id=? AND state='queued'
                """,
                ("started", owner, lease_until, now.isoformat(), job_id),
            )
            if conn.total_changes == 0:
                conn.commit()
                return "busy", current
            current["state"] = "started"
            current["owner"] = owner
            current["lease_until"] = lease_until
            conn.commit()
            return "claimed", current

    def _lease_is_active(self, lease_until: str | None, now: datetime) -> bool:
        if not lease_until:
            return True
        try:
            expiry = datetime.fromisoformat(lease_until)
        except ValueError:
            return True
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry > now

    def begin_period_run(self, period: str, facts_digest: str, owner: str) -> tuple[str, str | None]:
        now = datetime.now(timezone.utc)
        lease_until = (now + timedelta(seconds=RUN_LEASE_SECONDS)).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM run_claims WHERE period=? AND facts_digest=?",
                (period, facts_digest),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO run_claims(period, facts_digest, owner, lease_until, draft_id)
                    VALUES (?, ?, ?, ?, NULL)
                    """,
                    (period, facts_digest, owner, lease_until),
                )
                conn.commit()
                return "claimed", None
            if row["draft_id"]:
                # Resolve the latest live revision for this exact source identity.
                # Older stores may still point at a rejected parent after review.
                candidates = conn.execute(
                    "SELECT * FROM drafts WHERE period=? AND state IN ('awaiting_tom','approved') ORDER BY version DESC",
                    (period,),
                ).fetchall()
                for candidate in candidates:
                    if json.loads(candidate["report_json"]).get("facts_digest") == facts_digest:
                        conn.execute(
                            "UPDATE run_claims SET draft_id=? WHERE period=? AND facts_digest=?",
                            (candidate["draft_id"], period, facts_digest),
                        )
                        conn.commit()
                        return "exists", candidate["draft_id"]
                # A terminal rejected/superseded reference cannot be replayed.
                conn.execute(
                    "UPDATE run_claims SET owner=?, lease_until=?, draft_id=NULL WHERE period=? AND facts_digest=?",
                    (owner, lease_until, period, facts_digest),
                )
                conn.commit()
                return "claimed", None
            if self._lease_is_active(row["lease_until"], now):
                conn.commit()
                return "busy", row["draft_id"]
            conn.execute(
                """
                UPDATE run_claims SET owner=?, lease_until=?, draft_id=NULL
                WHERE period=? AND facts_digest=?
                """,
                (owner, lease_until, period, facts_digest),
            )
            conn.commit()
            return "claimed", None

    def finalize_new_draft(self, draft: dict[str, Any], *, facts_digest: str, catch_up: bool, owner: str) -> dict[str, Any]:
        assert_clean_mapping({key: value for key, value in draft.items() if key != "report"})
        assert_clean_mapping(draft["report"])
        created = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT MAX(version) AS highest FROM drafts WHERE period=?",
                (draft["period"],),
            ).fetchone()
            version = int(row["highest"] or 0) + 1
            if draft.get("parent_version") is not None and version <= int(draft["parent_version"]):
                version = int(draft["parent_version"]) + 1
            draft["version"] = version
            try:
                conn.execute(
                    """
                    INSERT INTO drafts(
                      draft_id, period, version, content_sha256, approval_nonce, state, report_json, comments, parent_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        draft["draft_id"],
                        draft["period"],
                        version,
                        draft["content_sha256"],
                        draft["approval_nonce"],
                        draft["state"],
                        json.dumps(draft["report"]),
                        draft.get("comments"),
                        draft.get("parent_version"),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise PeriodRunBusy("duplicate_period_version") from exc
            conn.execute(
                "UPDATE drafts SET state='superseded' WHERE period=? AND state='awaiting_tom' AND draft_id!=?",
                (draft["period"], draft["draft_id"]),
            )
            conn.execute(
                """
                INSERT INTO closes(period, status, catch_up, facts_digest, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(period) DO UPDATE SET
                  status=excluded.status,
                  catch_up=excluded.catch_up,
                  facts_digest=excluded.facts_digest
                """,
                (draft["period"], draft["state"], int(catch_up), facts_digest, created),
            )
            conn.execute(
                """
                UPDATE run_claims SET draft_id=?, owner=? WHERE period=? AND facts_digest=?
                """,
                (draft["draft_id"], owner, draft["period"], facts_digest),
            )
            conn.commit()
        return draft

    def _draft_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        payload["report"] = json.loads(payload.pop("report_json"))
        return payload
