"""Thin adapter from authenticated identity onto the financial-close agent."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from agents.financial_close.agent import run_close
from agents.financial_close.identity import (
    CLAIRE,
    DISTRIBUTION_EMAILS,
    TOM,
    ActorIdentity,
    ActorRejected,
    trusted_named_person,
)
from agents.financial_close.review import ReviewError, approve_draft, reject_draft
from agents.financial_close.runtime import CloseRuntime, runtime as default_runtime
from agents.financial_close.schedule import tick as schedule_tick
from agents.financial_close.serialize import lookup_figure as lookup_report_figure
from agents.financial_close.store import StaleDraftError
from app.schemas.user import UserInDB, UserRole


class UntrustedApproverError(ValueError):
    pass


def actor_from_user(user: UserInDB) -> ActorIdentity:
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    return ActorIdentity(
        user_id=user.id,
        role=role,
        department_id=user.department_id,
        email=str(user.email).strip().lower(),
        is_active=user.is_active,
        is_admin=role == UserRole.admin.value,
        can_approve=role == UserRole.supervisor.value,
    )


def _current() -> CloseRuntime:
    return default_runtime()


def public_draft(draft: dict) -> dict:
    report = draft["report"]
    return {
        "draft_id": draft["draft_id"],
        "period": draft["period"],
        "version": draft["version"],
        "content_sha256": draft["content_sha256"],
        "approval_nonce": draft["approval_nonce"] if draft["state"] == "awaiting_tom" else None,
        "state": draft["state"],
        "incomplete": report.get("incomplete"),
        "executive_summary": report.get("executive_summary"),
        "consolidated_usd": report.get("consolidated_usd"),
        "revenue_by_country_payer": report.get("revenue_by_country_payer"),
        "expenses_by_country": report.get("expenses_by_country"),
        "relevant_deviations": report.get("relevant_deviations"),
        "missing_or_uncertain": report.get("missing_or_uncertain"),
        "traceability": report.get("traceability"),
        "operations": report.get("operations"),
        "figure_ids": sorted((report.get("figures") or {}).keys()),
        "catch_up": report.get("catch_up"),
        "facts_digest": report.get("facts_digest"),
        "fx_rate": report.get("fx_rate"),
        "load_date": report.get("load_date"),
        "reviewer_guidance": report.get("reviewer_guidance"),
    }


def public_job(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "status": job["state"],
        "task_id": job.get("celery_task_id"),
        "result": job.get("result") or {},
    }


def _can_read(actor: ActorIdentity, draft: dict) -> bool:
    person = trusted_named_person(actor)
    if person is None:
        return False
    if person == TOM:
        return True
    if draft["state"] == "approved" and actor.email in DISTRIBUTION_EMAILS:
        return True
    return False


def list_drafts(actor: ActorIdentity) -> list[dict]:
    visible = []
    for draft in _current().store.list_drafts():
        if _can_read(actor, draft):
            visible.append(public_draft(draft))
    return visible


def get_draft(actor: ActorIdentity, draft_id: str) -> dict:
    draft = _current().store.get_draft(draft_id)
    if draft is None or not _can_read(actor, draft):
        raise KeyError("unknown_draft")
    return public_draft(draft)


def lookup_figure(actor: ActorIdentity, draft_id: str, figure_id: str) -> dict:
    draft = _current().store.get_draft(draft_id)
    if draft is None or not _can_read(actor, draft):
        raise KeyError("unknown_draft")
    return lookup_report_figure(draft["report"], figure_id)


def queue_run(actor: ActorIdentity) -> dict:
    if trusted_named_person(actor) != TOM:
        raise UntrustedApproverError("run_not_authorized")
    now = datetime.now(timezone.utc).isoformat()
    runtime = _current()
    from agents.financial_close.calendar import closing_period_for_load_date

    period = closing_period_for_load_date(runtime.load_date())
    store = runtime.store
    active = store.active_job_for_period(period)
    if active is not None:
        return {"job_id": active["job_id"], "status": "queued", "task_id": active.get("celery_task_id")}
    job_id = uuid4().hex
    store.save_job(
        {
            "job_id": job_id,
            "actor_email": actor.email,
            "state": "queued",
            "created_at": now,
            "updated_at": now,
            "result": {},
            "period": period,
        }
    )
    from app.celery_app import celery_app

    async_result = celery_app.send_task(
        "app.tasks_financial_close.run_financial_close_job",
        args=[job_id],
    )
    latest = store.get_job(job_id) or {}
    store.save_job(
        {
            "job_id": job_id,
            "celery_task_id": async_result.id,
            "actor_email": actor.email,
            "state": latest.get("state") or "queued",
            "created_at": latest.get("created_at") or now,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "result": latest.get("result") or {},
            "period": latest.get("period") or period,
            "owner": latest.get("owner"),
        }
    )
    return {"job_id": job_id, "status": "queued", "task_id": async_result.id}


def execute_queued_job(job_id: str, *, celery_task_id: str | None = None) -> dict:
    store = _current().store
    owner = celery_task_id or job_id
    status, job = store.claim_job(job_id, owner=owner)
    if status == "replay" or (status == "recover" and job.get("result", {}).get("draft_id")):
        return job.get("result") or {}
    if status == "busy":
        latest = store.get_job(job_id)
        if latest and latest["state"] == "success":
            return latest.get("result") or {}
        raise KeyError("unknown_job")
    try:
        draft = run_close(_current(), catch_up=True)
    except Exception:
        store.save_job(
            {
                "job_id": job_id,
                "celery_task_id": celery_task_id or job.get("celery_task_id"),
                "actor_email": job["actor_email"],
                "state": "failure",
                "created_at": job["created_at"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "result": {},
                "period": job.get("period"),
                "owner": owner,
            }
        )
        raise
    result = {"draft_id": draft["draft_id"], "period": draft["period"], "version": draft["version"]}
    store.save_job(
        {
            "job_id": job_id,
            "celery_task_id": celery_task_id or job.get("celery_task_id"),
            "actor_email": job["actor_email"],
            "state": "success",
            "created_at": job["created_at"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
            "period": draft["period"],
            "owner": owner,
        }
    )
    return result


def get_job(actor: ActorIdentity, job_id: str) -> dict:
    if trusted_named_person(actor) != TOM:
        raise UntrustedApproverError("job_not_authorized")
    job = _current().store.get_job(job_id)
    if job is None:
        raise KeyError("unknown_job")
    return public_job(job)


def decide(actor: ActorIdentity, body) -> dict:
    try:
        if body.decision == "approve":
            draft = approve_draft(
                _current(),
                actor,
                draft_id=body.draft_id,
                version=body.version,
                content_sha256=body.content_sha256,
                approval_nonce=body.approval_nonce,
            )
        elif body.decision == "reject":
            draft = reject_draft(
                _current(),
                actor,
                draft_id=body.draft_id,
                version=body.version,
                content_sha256=body.content_sha256,
                approval_nonce=body.approval_nonce,
                comments=body.comments or "",
            )
        else:
            raise ReviewError("unknown_decision")
    except ActorRejected as exc:
        raise UntrustedApproverError(str(exc)) from exc
    return public_draft(draft)


def list_outbox(actor: ActorIdentity) -> list[dict]:
    person = trusted_named_person(actor)
    if person not in {TOM, CLAIRE}:
        raise UntrustedApproverError("outbox_not_authorized")
    rows = _current().store.list_outbox()
    public = []
    for row in rows:
        payload = row["payload_json"] if isinstance(row.get("payload_json"), str) else row.get("payload", {})
        import json

        if isinstance(payload, str):
            payload = json.loads(payload)
        item = {
            "period": row["period"],
            "version": row["version"],
            "recipient_email": row["recipient_email"],
            "kind": row["kind"],
            "payload": payload,
        }
        if item["kind"] == "privacy_quarantine" and person == CLAIRE:
            public.append(item)
        elif person == TOM:
            public.append(item)
    return public


def tick() -> dict:
    return schedule_tick(_current())
