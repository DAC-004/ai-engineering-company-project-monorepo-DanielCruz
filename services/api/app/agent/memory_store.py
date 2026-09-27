"""SQLite read/write store for approved HealthCore operational notes.

This database is not the LangGraph checkpointer and it is not the
``healthcore_knowledge`` Qdrant collection. ``write_approved`` is the only
insert into retrievable facts, and it runs only for the proposal owner.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.agent.memory_policy import (
    PHI_WITHHELD,
    MemoryKind,
    appears_to_contain_phi,
    normalize_memory_text,
)
from shared.healthcore_rag.config import REPO_ROOT

MEMORY_DATABASE = REPO_ROOT / "data" / "process" / "agent_memory" / "support_agent_memory.sqlite"

# Design choices, not graded numbers. See docs/agent-memory/architecture.md.
PENDING_TTL = timedelta(hours=24)
FACT_TTL = timedelta(days=180)
MAX_ACTIVE_FACTS = 30

AuditEventName = str


@dataclass(frozen=True)
class PendingProposal:
    """The single unresolved proposal for one owner and thread."""

    proposal_id: str
    owner_user_id: str
    thread_id: str
    text: str
    kind: MemoryKind
    subject_key: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ApprovedFact:
    """One active note. ``claim_status`` stays ``unverified``."""

    fact_id: str
    owner_user_id: str
    authorized_by_user_id: str
    kind: str
    subject_key: str
    text: str
    claim_status: str
    created_at: datetime


@dataclass(frozen=True)
class AuditEvent:
    """One append-only decision row."""

    audit_id: str
    proposal_id: str
    owner_user_id: str | None
    actor_user_id: str | None
    thread_id: str
    event: str
    occurred_at: datetime
    originating_ref: str | None
    content_retained: bool
    safe_text: str | None


def memory_database_path() -> Path:
    """Return the gitignored SQLite file for curated operational memory."""
    return MEMORY_DATABASE


class MemoryStore:
    """Explicit memory interface. Reads do not append turns to a system prompt."""

    def __init__(
        self,
        database_path: Path | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.database_path = database_path or memory_database_path()
        self._clock = clock or (lambda: datetime.now(UTC))
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._create_schema(connection)

    def stage_proposal(
        self,
        *,
        owner_user_id: str,
        thread_id: str,
        text: str,
        kind: MemoryKind,
        subject_key: str,
        originating_message: str,
    ) -> PendingProposal | None:
        """Store one pending proposal and its ``proposed`` audit row.

        Returns None when a proposal is already pending, the text appears to
        contain PHI, or the same text is already an active fact. Nothing is
        written to the facts table here.
        """
        if appears_to_contain_phi(text) or appears_to_contain_phi(originating_message):
            return None
        self.expire_stale()
        if self.get_pending(owner_user_id, thread_id) is not None:
            return None
        if self._active_text_exists(owner_user_id, text):
            return None
        now = self._now()
        proposal = PendingProposal(
            proposal_id=uuid.uuid4().hex,
            owner_user_id=owner_user_id,
            thread_id=thread_id,
            text=text,
            kind=kind,
            subject_key=subject_key,
            created_at=now,
            updated_at=now,
        )
        turn_id = self._insert_turn(
            owner_user_id=owner_user_id,
            thread_id=thread_id,
            body=originating_message,
            withheld_reason=None,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pending_proposals (
                    proposal_id, owner_user_id, thread_id, text, kind,
                    subject_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.proposal_id,
                    proposal.owner_user_id,
                    proposal.thread_id,
                    proposal.text,
                    proposal.kind,
                    proposal.subject_key,
                    _iso(proposal.created_at),
                    _iso(proposal.updated_at),
                ),
            )
        self.record_audit(
            proposal_id=proposal.proposal_id,
            owner_user_id=owner_user_id,
            actor_user_id=owner_user_id,
            thread_id=thread_id,
            event="proposed",
            originating_ref=turn_id,
            content_retained=True,
            safe_text=text,
        )
        return proposal

    def get_pending(self, owner_user_id: str, thread_id: str) -> PendingProposal | None:
        """Load the pending proposal for this actor only."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM pending_proposals
                WHERE owner_user_id = ? AND thread_id = ?
                """,
                (owner_user_id, thread_id),
            ).fetchone()
        if row is None:
            return None
        return _pending_from_row(row)

    def write_approved(
        self,
        *,
        actor_user_id: str,
        proposal_id: str,
        originating_message: str,
    ) -> ApprovedFact | None:
        """Insert the pending text for its owner after a classified approval.

        A different actor cannot write the row. The claim status is always
        ``unverified``. Approval does not check that the operational claim is true.
        """
        pending = self._pending_by_id(proposal_id)
        if pending is None or pending.owner_user_id != actor_user_id:
            return None
        if appears_to_contain_phi(pending.text) or appears_to_contain_phi(originating_message):
            return None
        now = self._now()
        fact = ApprovedFact(
            fact_id=uuid.uuid4().hex,
            owner_user_id=pending.owner_user_id,
            authorized_by_user_id=actor_user_id,
            kind=pending.kind,
            subject_key=pending.subject_key,
            text=pending.text,
            claim_status="unverified",
            created_at=now,
        )
        turn_id = self._insert_turn(
            owner_user_id=actor_user_id,
            thread_id=pending.thread_id,
            body=originating_message,
            withheld_reason=None,
        )
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE facts SET active = 0, superseded_at = ?
                WHERE owner_user_id = ? AND subject_key = ? AND active = 1
                """,
                (_iso(now), fact.owner_user_id, fact.subject_key),
            )
            connection.execute(
                """
                INSERT INTO facts (
                    fact_id, owner_user_id, authorized_by_user_id, kind,
                    subject_key, text, claim_status, active, created_at, superseded_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'unverified', 1, ?, NULL)
                """,
                (
                    fact.fact_id,
                    fact.owner_user_id,
                    fact.authorized_by_user_id,
                    fact.kind,
                    fact.subject_key,
                    fact.text,
                    _iso(fact.created_at),
                ),
            )
            connection.execute(
                "DELETE FROM pending_proposals WHERE proposal_id = ?",
                (proposal_id,),
            )
        self.record_audit(
            proposal_id=proposal_id,
            owner_user_id=pending.owner_user_id,
            actor_user_id=actor_user_id,
            thread_id=pending.thread_id,
            event="approved",
            originating_ref=turn_id,
            content_retained=True,
            safe_text=pending.text,
        )
        self.consolidate()
        return fact

    def reject_pending(
        self,
        *,
        actor_user_id: str,
        proposal_id: str,
        originating_message: str,
    ) -> bool:
        """Drop a pending proposal without inserting a fact."""
        pending = self._require_owner(actor_user_id, proposal_id)
        if pending is None:
            return False
        if appears_to_contain_phi(originating_message):
            self.record_phi_rejection(
                owner_user_id=pending.owner_user_id,
                actor_user_id=actor_user_id,
                thread_id=pending.thread_id,
                proposal_id=pending.proposal_id,
            )
            return False
        turn_id = self._insert_turn(
            owner_user_id=actor_user_id,
            thread_id=pending.thread_id,
            body=originating_message,
            withheld_reason=None,
        )
        self._delete_pending(pending.proposal_id)
        self.record_audit(
            proposal_id=pending.proposal_id,
            owner_user_id=pending.owner_user_id,
            actor_user_id=actor_user_id,
            thread_id=pending.thread_id,
            event="rejected",
            originating_ref=turn_id,
            content_retained=True,
            safe_text=pending.text,
        )
        return True

    def edit_pending(
        self,
        *,
        actor_user_id: str,
        proposal_id: str,
        revised_text: str,
        originating_message: str,
    ) -> PendingProposal | None:
        """Replace pending text after a safe edit. Does not write a fact."""
        pending = self._require_owner(actor_user_id, proposal_id)
        if pending is None:
            return None
        if appears_to_contain_phi(revised_text) or appears_to_contain_phi(originating_message):
            self.record_phi_rejection(
                owner_user_id=pending.owner_user_id,
                actor_user_id=actor_user_id,
                thread_id=pending.thread_id,
                proposal_id=pending.proposal_id,
            )
            return None
        now = self._now()
        turn_id = self._insert_turn(
            owner_user_id=actor_user_id,
            thread_id=pending.thread_id,
            body=originating_message,
            withheld_reason=None,
        )
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE pending_proposals
                SET text = ?, updated_at = ?
                WHERE proposal_id = ?
                """,
                (revised_text, _iso(now), pending.proposal_id),
            )
        self.record_audit(
            proposal_id=pending.proposal_id,
            owner_user_id=pending.owner_user_id,
            actor_user_id=actor_user_id,
            thread_id=pending.thread_id,
            event="edited",
            originating_ref=turn_id,
            content_retained=True,
            safe_text=revised_text,
        )
        updated = self._pending_by_id(pending.proposal_id)
        return updated

    def discard_pending(
        self,
        *,
        actor_user_id: str,
        proposal_id: str,
        originating_message: str,
        event: str = "discarded_ambiguous",
    ) -> bool:
        """Close a proposal because the reply was not a clear decision."""
        pending = self._require_owner(actor_user_id, proposal_id)
        if pending is None:
            return False
        retain_message = not appears_to_contain_phi(originating_message)
        turn_id = self._insert_turn(
            owner_user_id=actor_user_id,
            thread_id=pending.thread_id,
            body=originating_message if retain_message else None,
            withheld_reason=None if retain_message else "phi",
        )
        self._delete_pending(pending.proposal_id)
        self.record_audit(
            proposal_id=pending.proposal_id,
            owner_user_id=pending.owner_user_id,
            actor_user_id=actor_user_id,
            thread_id=pending.thread_id,
            event=event,
            originating_ref=turn_id,
            content_retained=retain_message,
            safe_text=pending.text if retain_message else None,
        )
        return True

    def record_phi_rejection(
        self,
        *,
        owner_user_id: str | None,
        actor_user_id: str | None,
        thread_id: str,
        proposal_id: str | None = None,
    ) -> str:
        """Audit a PHI refusal. The message body and proposal text are not stored."""
        resolved_proposal_id = proposal_id or uuid.uuid4().hex
        turn_id = self._insert_turn(
            owner_user_id=owner_user_id,
            thread_id=thread_id,
            body=None,
            withheld_reason="phi",
        )
        self.record_audit(
            proposal_id=resolved_proposal_id,
            owner_user_id=owner_user_id,
            actor_user_id=actor_user_id,
            thread_id=thread_id,
            event="rejected_phi",
            originating_ref=turn_id,
            content_retained=False,
            safe_text=None,
        )
        return resolved_proposal_id

    def read_relevant(self, owner_user_id: str, question: str, *, limit: int = 5) -> list[ApprovedFact]:
        """Return this owner's active notes that share terms with the question.

        Rows that fail a fresh PHI screen are withheld from the answer and
        blanked. Other users' rows are not loaded.
        """
        self.consolidate()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM facts
                WHERE owner_user_id = ? AND active = 1
                ORDER BY created_at DESC
                """,
                (owner_user_id,),
            ).fetchall()
        matched: list[ApprovedFact] = []
        question_terms = set(normalize_memory_text(question).split())
        for row in rows:
            fact = _fact_from_row(row)
            if appears_to_contain_phi(fact.text):
                self._blank_fact(fact.fact_id)
                continue
            fact_terms = set(normalize_memory_text(fact.text).split()) | set(
                fact.subject_key.split("_")
            )
            if question_terms & fact_terms:
                matched.append(fact)
            if len(matched) >= limit:
                break
        return matched

    def consolidate(self) -> None:
        """Expire stale rows, enforce one active fact per owner and key, and cap growth.

        Any replacement text is screened again. A row that fails is blanked
        and deactivated so the patient content is not kept in the table.
        """
        now = self._now()
        self._expire_pending(now)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM facts WHERE active = 1 ORDER BY created_at ASC"
            ).fetchall()
        for row in rows:
            created_at = _parse_time(row["created_at"])
            if appears_to_contain_phi(str(row["text"])):
                self._blank_fact(str(row["fact_id"]))
                continue
            if created_at + FACT_TTL <= now:
                self._deactivate_fact(str(row["fact_id"]), now)
        self._enforce_single_active_per_key(now)
        self._enforce_cap(now)

    def expire_stale(self) -> int:
        """Mark abandoned proposals expired. Nobody authorized a write."""
        return self._expire_pending(self._now())

    def list_audit(self, proposal_id: str | None = None) -> list[AuditEvent]:
        """Return audit rows for tests and operator review."""
        with self._connect() as connection:
            if proposal_id is None:
                rows = connection.execute(
                    "SELECT * FROM audit_events ORDER BY occurred_at ASC"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM audit_events
                    WHERE proposal_id = ?
                    ORDER BY occurred_at ASC
                    """,
                    (proposal_id,),
                ).fetchall()
        return [_audit_from_row(row) for row in rows]

    def list_active_facts(self, owner_user_id: str) -> list[ApprovedFact]:
        """Return active facts for one owner."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM facts
                WHERE owner_user_id = ? AND active = 1
                ORDER BY created_at ASC
                """,
                (owner_user_id,),
            ).fetchall()
        return [_fact_from_row(row) for row in rows]

    def record_audit(
        self,
        *,
        proposal_id: str,
        owner_user_id: str | None,
        actor_user_id: str | None,
        thread_id: str,
        event: str,
        originating_ref: str | None,
        content_retained: bool,
        safe_text: str | None,
    ) -> AuditEvent:
        """Append one decision. PHI text must already have been removed by the caller."""
        if safe_text and appears_to_contain_phi(safe_text):
            safe_text = None
            content_retained = False
        event_row = AuditEvent(
            audit_id=uuid.uuid4().hex,
            proposal_id=proposal_id,
            owner_user_id=owner_user_id,
            actor_user_id=actor_user_id,
            thread_id=thread_id,
            event=event,
            occurred_at=self._now(),
            originating_ref=originating_ref,
            content_retained=content_retained,
            safe_text=safe_text,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    audit_id, proposal_id, owner_user_id, actor_user_id, thread_id,
                    event, occurred_at, originating_ref, content_retained, safe_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_row.audit_id,
                    event_row.proposal_id,
                    event_row.owner_user_id,
                    event_row.actor_user_id,
                    event_row.thread_id,
                    event_row.event,
                    _iso(event_row.occurred_at),
                    event_row.originating_ref,
                    1 if event_row.content_retained else 0,
                    event_row.safe_text,
                ),
            )
        return event_row

    def database_text(self) -> str:
        """Dump stored text fields. Tests use this to prove PHI was not copied."""
        with self._connect() as connection:
            chunks: list[str] = []
            for table in ("turn_records", "pending_proposals", "audit_events", "facts"):
                rows = connection.execute(f"SELECT * FROM {table}").fetchall()
                for row in rows:
                    chunks.extend(str(value) for value in row if value is not None)
        return "\n".join(chunks)

    def _expire_pending(self, now: datetime) -> int:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM pending_proposals").fetchall()
        expired = 0
        for row in rows:
            updated_at = _parse_time(row["updated_at"])
            if updated_at + PENDING_TTL > now:
                continue
            proposal_id = str(row["proposal_id"])
            self.record_audit(
                proposal_id=proposal_id,
                owner_user_id=str(row["owner_user_id"]),
                actor_user_id=None,
                thread_id=str(row["thread_id"]),
                event="expired_unanswered",
                originating_ref=None,
                content_retained=True,
                safe_text=str(row["text"]) if not appears_to_contain_phi(str(row["text"])) else None,
            )
            self._delete_pending(proposal_id)
            expired += 1
        return expired

    def _enforce_single_active_per_key(self, now: datetime) -> None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT owner_user_id, subject_key, fact_id, created_at
                FROM facts
                WHERE active = 1
                ORDER BY created_at DESC
                """
            ).fetchall()
        seen: set[tuple[str, str]] = set()
        for row in rows:
            key = (str(row["owner_user_id"]), str(row["subject_key"]))
            if key in seen:
                self._deactivate_fact(str(row["fact_id"]), now)
                continue
            seen.add(key)

    def _enforce_cap(self, now: datetime) -> None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT fact_id FROM facts
                WHERE active = 1
                ORDER BY created_at ASC
                """
            ).fetchall()
        overflow = len(rows) - MAX_ACTIVE_FACTS
        for row in rows[: max(overflow, 0)]:
            self._deactivate_fact(str(row["fact_id"]), now)

    def _blank_fact(self, fact_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE facts
                SET text = ?, active = 0, superseded_at = ?
                WHERE fact_id = ?
                """,
                (PHI_WITHHELD, _iso(self._now()), fact_id),
            )

    def _deactivate_fact(self, fact_id: str, now: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE facts SET active = 0, superseded_at = ? WHERE fact_id = ?",
                (_iso(now), fact_id),
            )

    def _active_text_exists(self, owner_user_id: str, text: str) -> bool:
        target = normalize_memory_text(text)
        return any(normalize_memory_text(fact.text) == target for fact in self.list_active_facts(owner_user_id))

    def _require_owner(self, actor_user_id: str, proposal_id: str) -> PendingProposal | None:
        pending = self._pending_by_id(proposal_id)
        if pending is None or pending.owner_user_id != actor_user_id:
            return None
        return pending

    def _pending_by_id(self, proposal_id: str) -> PendingProposal | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM pending_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        return _pending_from_row(row)

    def _delete_pending(self, proposal_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM pending_proposals WHERE proposal_id = ?",
                (proposal_id,),
            )

    def _insert_turn(
        self,
        *,
        owner_user_id: str | None,
        thread_id: str,
        body: str | None,
        withheld_reason: str | None,
    ) -> str:
        turn_id = uuid.uuid4().hex
        if body and appears_to_contain_phi(body):
            body = None
            withheld_reason = "phi"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO turn_records (
                    turn_id, owner_user_id, thread_id, received_at, body, withheld_reason
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (turn_id, owner_user_id, thread_id, _iso(self._now()), body, withheld_reason),
            )
        return turn_id

    def _now(self) -> datetime:
        current = self._clock()
        if current.tzinfo is None:
            return current.replace(tzinfo=UTC)
        return current.astimezone(UTC)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS turn_records (
                turn_id TEXT PRIMARY KEY,
                owner_user_id TEXT,
                thread_id TEXT NOT NULL,
                received_at TEXT NOT NULL,
                body TEXT,
                withheld_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS pending_proposals (
                proposal_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                text TEXT NOT NULL,
                kind TEXT NOT NULL,
                subject_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (owner_user_id, thread_id)
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                audit_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                owner_user_id TEXT,
                actor_user_id TEXT,
                thread_id TEXT NOT NULL,
                event TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                originating_ref TEXT,
                content_retained INTEGER NOT NULL,
                safe_text TEXT
            );
            CREATE TABLE IF NOT EXISTS facts (
                fact_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                authorized_by_user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                subject_key TEXT NOT NULL,
                text TEXT NOT NULL,
                claim_status TEXT NOT NULL,
                active INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                superseded_at TEXT
            );
            """
        )


def _iso(value: datetime) -> str:
    current = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return current.astimezone(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _pending_from_row(row: sqlite3.Row) -> PendingProposal:
    return PendingProposal(
        proposal_id=str(row["proposal_id"]),
        owner_user_id=str(row["owner_user_id"]),
        thread_id=str(row["thread_id"]),
        text=str(row["text"]),
        kind=row["kind"],
        subject_key=str(row["subject_key"]),
        created_at=_parse_time(str(row["created_at"])),
        updated_at=_parse_time(str(row["updated_at"])),
    )


def _fact_from_row(row: sqlite3.Row) -> ApprovedFact:
    return ApprovedFact(
        fact_id=str(row["fact_id"]),
        owner_user_id=str(row["owner_user_id"]),
        authorized_by_user_id=str(row["authorized_by_user_id"]),
        kind=str(row["kind"]),
        subject_key=str(row["subject_key"]),
        text=str(row["text"]),
        claim_status=str(row["claim_status"]),
        created_at=_parse_time(str(row["created_at"])),
    )


def _audit_from_row(row: sqlite3.Row) -> AuditEvent:
    actor = row["actor_user_id"]
    owner = row["owner_user_id"]
    originating = row["originating_ref"]
    safe_text = row["safe_text"]
    return AuditEvent(
        audit_id=str(row["audit_id"]),
        proposal_id=str(row["proposal_id"]),
        owner_user_id=str(owner) if owner is not None else None,
        actor_user_id=str(actor) if actor is not None else None,
        thread_id=str(row["thread_id"]),
        event=str(row["event"]),
        occurred_at=_parse_time(str(row["occurred_at"])),
        originating_ref=str(originating) if originating is not None else None,
        content_retained=bool(row["content_retained"]),
        safe_text=str(safe_text) if safe_text is not None else None,
    )
