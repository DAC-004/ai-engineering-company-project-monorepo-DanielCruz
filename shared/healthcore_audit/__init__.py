"""Metadata-only, append-only HealthCore accountability ledger."""

from .store import (
    AuditError,
    AuditIntegrityError,
    AuditStore,
    audit_path,
    opaque_ref,
    record_patient_event,
)
