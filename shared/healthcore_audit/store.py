"""Dedicated SQLite audit ledger. No clinical text, credentials, or request bodies."""

from __future__ import annotations
import hashlib, ipaddress, json, os, sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

DEPARTMENTS = frozenset(
    {
        "clinical_operations",
        "patient_experience",
        "revenue_cycle",
        "compliance",
        "people_workforce",
        "technology",
    }
)
KINDS = frozenset(
    {
        "auth",
        "user",
        "role",
        "department",
        "profile",
        "internal_report",
        "incident",
        "inventory",
        "supplier",
        "rfp",
        "onboarding",
        "financial_close",
        "agent",
        "knowledge",
        "task",
        "audit",
        "report",
        "clinical_record",
        "billing_record",
        "claim",
        "patient_export",
    }
)
ACTIONS = frozenset(
    f"{kind}.{verb}" for kind in KINDS for verb in ("read", "create", "update", "delete", "execute")
) | frozenset(
    {
        "auth.login",
        "auth.federated_start",
        "auth.federated_login",
        "auth.federated_link",
        "auth.federated_unlink",
        "auth.password_reset_requested",
        "auth.password_reset",
        "auth.password_change",
        "user.assignment",
        "patient.read",
        "patient.update",
        "patient.export",
        "billing.update",
        "claim.approve",
        "claim.deny",
        "agent.patient_access",
        "audit.verify",
    }
)
CONTEXTS = frozenset(
    {
        "authentication",
        "staff_administration",
        "routine_review",
        "referral_resolution",
        "billing_review",
        "resource_change",
        "data_export",
        "automated_processing",
        "audit_review",
    }
)
PROCESSES = frozenset(
    {
        "process:http-api",
        "process:support-agent",
        "process:incident-analysis",
        "process:onboarding",
        "process:supplier-contracts",
        "process:financial-close",
        "process:synthetic-seed",
    }
)
FIELDS = frozenset(
    {
        "actor_kind",
        "actor_ref",
        "actor_department_id",
        "initiator_ref",
        "action",
        "resource_kind",
        "resource_ref",
        "patient_ref",
        "department_id",
        "occurred_at",
        "origin",
        "context",
        "outcome",
        "operation_ref",
        "status_code",
    }
)
ZERO = "0" * 64


class AuditError(RuntimeError):
    pass


class AuditIntegrityError(AuditError):
    pass


def audit_path() -> Path:
    explicit = os.getenv("AUDIT_DB_PATH")
    if explicit:
        return Path(explicit).resolve()
    auth = os.getenv("TINYDB_PATH")
    if auth:
        return Path(auth).resolve().parent / "audit.sqlite3"
    return Path(__file__).resolve().parents[2] / "services/api/data/audit/audit.sqlite3"


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError("Opaque UUID required")
    return str(UUID(value))


def opaque_ref(value):
    if value is None:
        return None
    try:
        return _uuid(str(value))
    except ValueError:
        return "ref_" + hashlib.sha256(str(value).encode()).hexdigest()


def _reference(value):
    if value is None:
        return
    if isinstance(value, str) and value.startswith("ref_") and len(value) == 68:
        int(value[4:], 16)
        return
    _uuid(value)


def _time(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("UTC timestamp required")
    return dt.astimezone(UTC).isoformat(timespec="microseconds")


def validate(data):
    if set(data) != FIELDS:
        raise ValueError("Only the fixed metadata schema is allowed")
    if data["actor_kind"] not in {"human", "process", "anonymous"}:
        raise ValueError("Invalid actor kind")
    if data["actor_kind"] == "process":
        if data["actor_ref"] not in PROCESSES:
            raise ValueError("Unknown process")
    else:
        _uuid(data["actor_ref"])
    for key in ["actor_department_id", "department_id"]:
        if data[key] is not None and data[key] not in DEPARTMENTS:
            _reference(data[key])
    if data["initiator_ref"] is not None:
        _uuid(data["initiator_ref"])
    if data["action"] not in ACTIONS or data["resource_kind"] not in KINDS:
        raise ValueError("Unknown structural action/resource")
    _reference(data["resource_ref"])
    _uuid(data["operation_ref"])
    if data["patient_ref"] is not None:
        _uuid(data["patient_ref"])
    if (
        data["resource_kind"] in {"clinical_record", "billing_record", "claim", "patient_export"}
        and data["patient_ref"] is None
    ):
        raise ValueError("Opaque patient_ref required")
    if data["context"] not in CONTEXTS:
        raise ValueError("Context must be a fixed non-clinical code")
    if data["outcome"] not in {"attempted", "success", "denied", "failed"}:
        raise ValueError("Invalid outcome")
    if data["origin"] not in PROCESSES:
        ipaddress.ip_address(data["origin"])
    if data["status_code"] is not None and (
        type(data["status_code"]) is not int or not 100 <= data["status_code"] <= 599
    ):
        raise ValueError("Invalid status")
    if _time(data["occurred_at"]) != data["occurred_at"]:
        raise ValueError("Canonical UTC time required")
    return data


def event(
    *,
    actor_kind,
    actor_ref,
    action,
    resource_kind,
    origin,
    context,
    outcome,
    department_id=None,
    actor_department_id=None,
    initiator_ref=None,
    resource_ref=None,
    patient_ref=None,
    operation_ref=None,
    status_code=None,
):
    department_id = (
        department_id
        if department_id in DEPARTMENTS or department_id is None
        else opaque_ref(department_id)
    )
    actor_department_id = (
        actor_department_id
        if actor_department_id in DEPARTMENTS or actor_department_id is None
        else opaque_ref(actor_department_id)
    )
    data = dict(
        actor_kind=actor_kind,
        actor_ref=actor_ref,
        actor_department_id=actor_department_id,
        initiator_ref=initiator_ref,
        action=action,
        resource_kind=resource_kind,
        resource_ref=resource_ref,
        patient_ref=patient_ref,
        department_id=department_id,
        occurred_at=datetime.now(UTC).isoformat(timespec="microseconds"),
        origin=origin,
        context=context,
        outcome=outcome,
        operation_ref=operation_ref or str(uuid4()),
        status_code=status_code,
    )
    return validate(data)


def _json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(seq, previous, payload):
    return hashlib.sha256(f"{seq}\n{previous}\n{payload}".encode()).hexdigest()


class AuditStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else audit_path()

    def _write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(self.path, timeout=30)
        c.execute("PRAGMA busy_timeout=30000")
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript("""
  CREATE TABLE IF NOT EXISTS audit_entries(seq INTEGER PRIMARY KEY,payload TEXT NOT NULL,previous_hash TEXT NOT NULL,entry_hash TEXT NOT NULL UNIQUE);
  CREATE TABLE IF NOT EXISTS audit_head(singleton INTEGER PRIMARY KEY CHECK(singleton=1),seq INTEGER NOT NULL,entry_hash TEXT NOT NULL);
  CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_entries BEGIN SELECT RAISE(ABORT,'Audit entries are append-only');END;
  CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_entries BEGIN SELECT RAISE(ABORT,'Audit entries are append-only');END;
  CREATE INDEX IF NOT EXISTS audit_by_department ON audit_entries(json_extract(payload,'$.department_id'));
  CREATE INDEX IF NOT EXISTS audit_by_actor ON audit_entries(json_extract(payload,'$.actor_ref'));
  CREATE INDEX IF NOT EXISTS audit_by_time ON audit_entries(json_extract(payload,'$.occurred_at'));
  """)
        return c

    def _read(self):
        c = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
        c.execute("PRAGMA query_only=ON")
        return c

    def append(self, data):
        validate(data)
        payload = _json(data)
        try:
            with self._write() as c:
                c.execute("BEGIN IMMEDIATE")
                head = c.execute(
                    "SELECT seq,entry_hash FROM audit_head WHERE singleton=1"
                ).fetchone() or (0, ZERO)
                tail = c.execute(
                    "SELECT seq,entry_hash FROM audit_entries ORDER BY seq DESC LIMIT 1"
                ).fetchone() or (0, ZERO)
                if head != tail:
                    raise AuditIntegrityError("Audit head mismatch")
                seq = head[0] + 1
                digest = _hash(seq, head[1], payload)
                c.execute(
                    "INSERT INTO audit_entries VALUES(?,?,?,?)", (seq, payload, head[1], digest)
                )
                c.execute(
                    "INSERT INTO audit_head VALUES(1,?,?) ON CONFLICT(singleton) DO UPDATE SET seq=excluded.seq,entry_hash=excluded.entry_hash",
                    (seq, digest),
                )
            return {"seq": seq, **data, "previous_hash": head[1], "entry_hash": digest}
        except (sqlite3.Error, OSError) as exc:
            raise AuditError("Audit storage unavailable") from exc
        finally:
            if "c" in locals():
                c.close()

    def verify(self):
        if not self.path.exists():
            return {"valid": True, "checked": 0}
        try:
            with self._read() as c:
                c.execute("BEGIN")
                previous = ZERO
                seq = 0
                for n, payload, prev, digest in c.execute(
                    "SELECT seq,payload,previous_hash,entry_hash FROM audit_entries ORDER BY seq"
                ):
                    try:
                        validate(json.loads(payload))
                    except (ValueError, TypeError, KeyError):
                        return {
                            "valid": False,
                            "checked": seq,
                            "failure_at": n,
                            "reason": "invalid_metadata",
                        }
                    if n != seq + 1 or prev != previous or digest != _hash(n, prev, payload):
                        return {
                            "valid": False,
                            "checked": seq,
                            "failure_at": n,
                            "reason": "chain_mismatch",
                        }
                    seq = n
                    previous = digest
                head = c.execute(
                    "SELECT seq,entry_hash FROM audit_head WHERE singleton=1"
                ).fetchone() or (0, ZERO)
                return {
                    "valid": head == (seq, previous),
                    "checked": seq,
                    **({"reason": "head_mismatch"} if head != (seq, previous) else {}),
                }
        except (sqlite3.Error, OSError):
            raise AuditError("Audit storage unavailable") from None
        finally:
            if "c" in locals():
                c.close()

    def query(
        self,
        *,
        department_id=None,
        actor_ref=None,
        action=None,
        resource_kind=None,
        resource_ref=None,
        start=None,
        end=None,
        limit=50,
        offset=0,
    ):
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or type(offset) is not int
            or not 0 <= offset <= 100000
        ):
            raise ValueError("Invalid pagination")
        if department_id is not None and department_id not in DEPARTMENTS:
            department_id = opaque_ref(department_id)
        if actor_ref is not None and actor_ref not in PROCESSES:
            _uuid(actor_ref)
        if action is not None and action not in ACTIONS:
            raise ValueError("Unknown action")
        if resource_kind is not None and resource_kind not in KINDS:
            raise ValueError("Unknown resource kind")
        _reference(resource_ref)
        start = _time(start) if start else None
        end = _time(end) if end else None
        if start and end and start > end:
            raise ValueError("Start must precede end")
        if not self.path.exists():
            return {"items": [], "total": 0, "limit": limit, "offset": offset, "has_more": False}
        where = []
        args = []
        for key, value in [
            ("department_id", department_id),
            ("actor_ref", actor_ref),
            ("action", action),
            ("resource_kind", resource_kind),
            ("resource_ref", resource_ref),
        ]:
            if value is not None:
                where.append(f"json_extract(payload,'$.{key}')=?")
                args.append(value)
        for op, value in [(">=", start), ("<=", end)]:
            if value:
                where.append("json_extract(payload,'$.occurred_at')" + op + "?")
                args.append(value)
        clause = " WHERE " + " AND ".join(where) if where else ""
        try:
            with self._read() as c:
                c.execute("BEGIN")
                total = c.execute("SELECT count(*) FROM audit_entries" + clause, args).fetchone()[0]
                items = []
                for seq, payload, prev, digest in c.execute(
                    "SELECT seq,payload,previous_hash,entry_hash FROM audit_entries"
                    + clause
                    + " ORDER BY seq DESC LIMIT ? OFFSET ?",
                    [*args, limit, offset],
                ):
                    try:
                        data = validate(json.loads(payload))
                    except (ValueError, TypeError, KeyError):
                        raise AuditIntegrityError("Invalid audit metadata") from None
                    if digest != _hash(seq, prev, payload):
                        raise AuditIntegrityError("Audit entry changed")
                    items.append({"seq": seq, **data, "previous_hash": prev, "entry_hash": digest})
            return {
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(items) < total,
            }
        except (sqlite3.Error, OSError):
            raise AuditError("Audit storage unavailable") from None
        finally:
            if "c" in locals():
                c.close()


def record_patient_event(
    *,
    patient_ref,
    department_id,
    actor_kind,
    actor_ref,
    action,
    context,
    origin,
    initiator_ref=None,
    store=None,
):
    """Boundary for present/future patient adapters; accepts no record content."""
    patient_ref = _uuid(patient_ref)
    kinds = {
        "patient.read": "clinical_record",
        "patient.update": "clinical_record",
        "patient.export": "patient_export",
        "billing.update": "billing_record",
        "claim.approve": "claim",
        "claim.deny": "claim",
        "agent.patient_access": "clinical_record",
    }
    if action not in kinds:
        raise ValueError("Unknown patient event")
    return (store or AuditStore()).append(
        event(
            actor_kind=actor_kind,
            actor_ref=actor_ref,
            action=action,
            resource_kind=kinds[action],
            resource_ref=patient_ref,
            patient_ref=patient_ref,
            department_id=department_id,
            origin=origin,
            context=context,
            outcome="success",
            initiator_ref=initiator_ref,
        )
    )
