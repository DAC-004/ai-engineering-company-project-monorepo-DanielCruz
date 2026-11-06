"""Internal outbox only. Seven recipients after Tom approval; Claire for quarantine IDs."""

from __future__ import annotations

from datetime import datetime, timezone

from agents.financial_close.identity import CLAIRE_EMAIL, DISTRIBUTION_EMAILS, PERSON_DISPLAY, person_from_email
from agents.financial_close.runtime import CloseRuntime


class DistributionError(ValueError):
    pass


def privacy_notice_key(period: str, version: int, entry_id: str) -> str:
    return f"privacy:{period}:{version}:{entry_id}"


def report_notice_key(period: str, version: int, draft_id: str, email: str) -> str:
    return f"report:{period}:{version}:{draft_id}:{email}"


def notify_claire_quarantine(runtime: CloseRuntime, period: str, version: int, entry_ids: tuple[str, ...]) -> None:
    created = datetime.now(timezone.utc).isoformat()
    for entry_id in entry_ids:
        runtime.store.append_outbox(
            {
                "notice_key": privacy_notice_key(period, version, entry_id),
                "period": period,
                "version": version,
                "recipient_email": CLAIRE_EMAIL,
                "kind": "privacy_quarantine",
                "payload": {"entry_id": entry_id},
                "created_at": created,
            }
        )
    runtime.audit.record("claire_privacy_notice", period=period, version=version)


def _hash_report(report: dict) -> str:
    import hashlib
    import json

    encoded = json.dumps(report, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def approved_report_notices(draft: dict) -> list[dict]:
    created = datetime.now(timezone.utc).isoformat()
    notices: list[dict] = []
    for email in DISTRIBUTION_EMAILS:
        person = person_from_email(email)
        notices.append(
            {
                "notice_key": report_notice_key(draft["period"], int(draft["version"]), draft["draft_id"], email),
                "period": draft["period"],
                "version": int(draft["version"]),
                "recipient_email": email,
                "kind": "approved_report",
                "payload": {
                    "draft_id": draft["draft_id"],
                    "content_sha256": draft["content_sha256"],
                    "recipient": PERSON_DISPLAY[person] if person else email,
                },
                "created_at": created,
            }
        )
    return notices


def distribute_approved(runtime: CloseRuntime, draft: dict) -> None:
    persisted = runtime.store.get_draft(draft.get("draft_id") or "")
    if persisted is None:
        raise DistributionError("unknown_draft")
    if persisted["state"] != "approved":
        raise DistributionError("unapproved_draft")
    if int(persisted["version"]) != int(draft.get("version") or 0):
        raise DistributionError("draft_version_mismatch")
    if persisted["content_sha256"] != draft.get("content_sha256"):
        raise DistributionError("draft_hash_mismatch")
    if _hash_report(persisted["report"]) != persisted["content_sha256"]:
        raise DistributionError("draft_content_mismatch")
    draft = persisted
    for item in approved_report_notices(draft):
        runtime.store.append_outbox(item)
    runtime.audit.record(
        "distributed_internal_outbox",
        period=draft["period"],
        version=int(draft["version"]),
        draft_id=draft["draft_id"],
    )
