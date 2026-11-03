"""Bounded department apply for the six identified I03b legacy suppliers.

This is not inventory's missing-only default. There is no global or future
supplier default. Writes run only after the complete six-identity group is
valid. Untargeted rows may exist and are left unchanged.
"""

from __future__ import annotations

import hashlib
import json

from tinydb.table import Table

from app.access.catalog import DepartmentId
from app.database import get_suppliers_table

# Frozen identity of the six I03b checkpoint rows (doc_id, name).
# Duplicate display names are distinct rows. These are not CONTEXT seed names.
LEGACY_I03B_SUPPLIER_TARGETS: tuple[tuple[int, str], ...] = (
    (1, "I03b 126 Disposable Supplier"),
    (2, "I03b 126 UI Supplier"),
    (3, "I03b 126 Disposable Supplier"),
    (4, "I03b 126 UI Supplier"),
    (5, "I03b 126 Disposable Supplier"),
    (6, "I03b 126 UI Supplier"),
)

LEGACY_SUPPLIER_DEPARTMENT_ID = DepartmentId.people_workforce.value
_EXPECTED_NAME = {doc_id: name for doc_id, name in LEGACY_I03B_SUPPLIER_TARGETS}
_SENSITIVE_FIELDS = frozenset({"contact_email", "notes"})

APPLY = "apply"
NOOP = "noop"
CONFLICT = "conflict"


class LegacySupplierGroupConflict(Exception):
    """The six-identity group is missing, duplicate, mismatched, or conflicting."""


def _is_untagged(document: dict) -> bool:
    if "department_id" not in document:
        return True
    value = document.get("department_id")
    return value is None or value == ""


def _non_department_digest(document: dict) -> str:
    payload = {key: value for key, value in document.items() if key != "department_id"}
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _row_digest(document: dict) -> str:
    encoded = json.dumps(document, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def summarize_supplier_row(doc_id: int, document: dict) -> dict[str, object]:
    """Identity-only row summary. Omits contact_email and notes."""
    return {
        "id": doc_id,
        "name": document.get("name"),
        "department_id": document.get("department_id") if "department_id" in document else None,
        "department_key_present": "department_id" in document,
        "untagged": _is_untagged(document),
        "non_department_sha256": _non_department_digest(document),
        "row_sha256": _row_digest(document),
        "field_names": sorted(key for key in document if key not in _SENSITIVE_FIELDS),
    }


def inspect_supplier_group(table: Table | None = None) -> dict[str, object]:
    suppliers = table if table is not None else get_suppliers_table()
    rows = [summarize_supplier_row(document.doc_id, dict(document)) for document in suppliers.all()]
    untagged_ids = [row["id"] for row in rows if row["untagged"]]
    tagged_ids = [row["id"] for row in rows if not row["untagged"]]
    return {
        "count": len(rows),
        "untagged_count": len(untagged_ids),
        "tagged_count": len(tagged_ids),
        "untagged_ids": untagged_ids,
        "tagged_ids": tagged_ids,
        "rows": rows,
    }


def assess_legacy_supplier_group(table: Table | None = None) -> dict[str, object]:
    """Inspect the six identities before any write.

    Extra unrelated rows are allowed. A matching subset is not. Returns
    action apply, noop, or conflict plus concrete conflict strings.
    """
    suppliers = table if table is not None else get_suppliers_table()
    conflicts: list[str] = []
    by_id: dict[int, dict] = {}
    seen_ids: list[int] = []
    for document in suppliers.all():
        doc_id = document.doc_id
        seen_ids.append(doc_id)
        if doc_id in by_id:
            conflicts.append(f"duplicate_id={doc_id}")
        by_id[doc_id] = dict(document)

    target_seen = [doc_id for doc_id in seen_ids if doc_id in _EXPECTED_NAME]
    if len(target_seen) != len(set(target_seen)):
        conflicts.append("duplicate_target_identity")

    target_records: list[tuple[int, dict]] = []
    for doc_id, expected_name in LEGACY_I03B_SUPPLIER_TARGETS:
        record = by_id.get(doc_id)
        if record is None:
            conflicts.append(f"missing_id={doc_id}")
            continue
        if record.get("name") != expected_name:
            conflicts.append(
                f"id={doc_id} name={record.get('name')!r} expected={expected_name!r}"
            )
        target_records.append((doc_id, record))

    states: list[str] = []
    if len(target_records) == len(LEGACY_I03B_SUPPLIER_TARGETS):
        for doc_id, record in target_records:
            if _is_untagged(record):
                states.append("untagged")
            elif record.get("department_id") == LEGACY_SUPPLIER_DEPARTMENT_ID:
                states.append(LEGACY_SUPPLIER_DEPARTMENT_ID)
            else:
                conflicts.append(
                    f"id={doc_id} conflicting_department={record.get('department_id')!r}"
                )
                states.append("other")

    unique_states = set(states)
    if conflicts:
        action = CONFLICT
    elif unique_states == {"untagged"}:
        action = APPLY
    elif unique_states == {LEGACY_SUPPLIER_DEPARTMENT_ID}:
        action = NOOP
    else:
        action = CONFLICT
        conflicts.append(f"partially_tagged states={states}")

    return {
        "action": action,
        "conflicts": conflicts,
        "target_ids": [doc_id for doc_id, _record in target_records],
        "states": states,
    }


def ensure_legacy_supplier_department_id() -> int:
    """Apply people_workforce to the six identities only after a full-group pass.

    - All six untagged: write people_workforce on those six rows.
    - All six already people_workforce: no-op, zero writes.
    - Missing, duplicate, mismatched, partially tagged, or conflicting:
      raise LegacySupplierGroupConflict and write nothing.
    Extra unrelated rows are preserved. Matching subsets are not applied.
    """
    table = get_suppliers_table()
    assessment = assess_legacy_supplier_group(table)
    if assessment["action"] == CONFLICT:
        raise LegacySupplierGroupConflict("; ".join(assessment["conflicts"]))
    if assessment["action"] == NOOP:
        return 0
    for doc_id, _name in LEGACY_I03B_SUPPLIER_TARGETS:
        table.update({"department_id": LEGACY_SUPPLIER_DEPARTMENT_ID}, doc_ids=[doc_id])
    return 6
