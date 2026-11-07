"""18 reproducible, fully synthetic entries; never seed real patient data."""

import sqlite3
from uuid import UUID, uuid5
from .store import AuditStore, event

NAMESPACE = UUID("cfdf6293-7ddb-4be6-8f7a-ec51a6ddceef")


def seed_synthetic(store: AuditStore):
    actions = (
        ["patient.read"] * 8
        + ["patient.update"] * 4
        + ["billing.update"] * 2
        + ["claim.approve", "claim.deny", "patient.export", "agent.patient_access"]
    )
    count = 0
    for i, action in enumerate(actions):
        operation = str(uuid5(NAMESPACE, "operation:" + str(i)))
        exists = False
        if store.path.exists():
            with sqlite3.connect(store.path.resolve().as_uri() + "?mode=ro", uri=True) as c:
                exists = (
                    c.execute(
                        "SELECT 1 FROM audit_entries WHERE json_extract(payload,'$.operation_ref')=?",
                        (operation,),
                    ).fetchone()
                    is not None
                )
        if exists:
            continue
        patient = str(uuid5(NAMESPACE, "synthetic-patient:" + str(i)))
        process = action.startswith("agent.")
        department = (
            "revenue_cycle"
            if action.startswith(("billing.", "claim."))
            else "compliance" if action == "patient.export" else "clinical_operations"
        )
        kind = {
            "patient.read": "clinical_record",
            "patient.update": "clinical_record",
            "billing.update": "billing_record",
            "claim.approve": "claim",
            "claim.deny": "claim",
            "patient.export": "patient_export",
            "agent.patient_access": "clinical_record",
        }[action]
        store.append(
            event(
                actor_kind="process" if process else "human",
                actor_ref=(
                    "process:support-agent"
                    if process
                    else str(uuid5(NAMESPACE, "synthetic-user:" + department))
                ),
                initiator_ref=(
                    str(uuid5(NAMESPACE, "synthetic-user:clinical_operations")) if process else None
                ),
                action=action,
                resource_kind=kind,
                resource_ref=patient,
                patient_ref=patient,
                department_id=department,
                actor_department_id=None if process else department,
                origin="process:support-agent" if process else "192.0.2.10",
                context=(
                    "automated_processing"
                    if process
                    else (
                        "data_export"
                        if action == "patient.export"
                        else (
                            "billing_review"
                            if department == "revenue_cycle"
                            else "referral_resolution"
                        )
                    )
                ),
                outcome="success",
                operation_ref=operation,
            )
        )
        count += 1
    return count
