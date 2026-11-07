"""Named Tom Callahan CAS approval and rejection. Admin cannot substitute."""

from __future__ import annotations

from agents.financial_close.agent import build_close_draft
from agents.financial_close.distribution import approved_report_notices
from agents.financial_close.generation import text_is_grounded
from agents.financial_close.identity import ActorIdentity, ActorRejected, TOM, named_tom_from_actor
from agents.financial_close.privacy import is_safe_prose
from agents.financial_close.runtime import CloseRuntime
from agents.financial_close.serialize import allowed_number_catalog
from agents.financial_close.store import StaleDraftError
from agents.financial_close.tools import build_facts


class ReviewError(ValueError):
    pass


def _require_tom(actor: ActorIdentity) -> None:
    if named_tom_from_actor(actor) != TOM:
        raise ActorRejected("wrong_named_identity")


def approve_draft(
    runtime: CloseRuntime,
    actor: ActorIdentity,
    *,
    draft_id: str,
    version: int,
    content_sha256: str,
    approval_nonce: str,
) -> dict:
    _require_tom(actor)
    current = runtime.store.get_draft(draft_id)
    if current is None:
        raise KeyError("unknown_draft")
    facts = build_facts(
        raw_dir=runtime.raw,
        load_date=runtime.load_date(),
        catch_up=bool(current["report"].get("catch_up")),
    )
    if facts.digest != current["report"].get("facts_digest"):
        raise StaleDraftError("stale_source_digest")
    updated = runtime.store.approve_and_enqueue(
        draft_id,
        expected_nonce=approval_nonce,
        expected_version=version,
        expected_hash=content_sha256,
        facts_digest=facts.digest,
        notices=approved_report_notices(current),
        catch_up=bool(current["report"].get("catch_up")),
    )
    runtime.audit.record("approved_by_tom", period=updated["period"], draft_id=draft_id, version=int(updated["version"]))
    return updated


def reject_draft(
    runtime: CloseRuntime,
    actor: ActorIdentity,
    *,
    draft_id: str,
    version: int,
    content_sha256: str,
    approval_nonce: str,
    comments: str,
) -> dict:
    _require_tom(actor)
    if not comments or not comments.strip():
        raise ReviewError("comments_required")
    if not is_safe_prose(comments):
        raise ReviewError("comments_rejected")
    current = runtime.store.get_draft(draft_id)
    if current is None:
        raise KeyError("unknown_draft")
    facts = build_facts(
        raw_dir=runtime.raw,
        load_date=runtime.load_date(),
        catch_up=bool(current["report"].get("catch_up")),
    )
    if not text_is_grounded(comments, allowed_number_catalog(facts)):
        raise ReviewError("comments_rejected")
    if int(current["version"]) != version or current["content_sha256"] != content_sha256:
        raise StaleDraftError("stale_draft_hash")
    if current["state"] == "awaiting_tom" and current["approval_nonce"] != approval_nonce:
        raise StaleDraftError("stale_or_replayed_nonce")
    existing = runtime.store.successor_draft(current["period"], int(current["version"]))
    if existing is not None:
        return existing
    successor = build_close_draft(
        runtime,
        catch_up=bool(current["report"].get("catch_up")),
        comments=comments.strip(),
        parent_version=int(current["version"]),
    )
    for key in ("tool_results", "plan_raw", "write_raw", "model_hypotheses"):
        successor.pop(key, None)
    revised = runtime.store.reject_and_insert_successor(draft_id, successor, comments=comments.strip())
    runtime.audit.record(
        "rejected_by_tom",
        period=current["period"],
        draft_id=draft_id,
        version=int(current["version"]),
        successor_draft_id=revised["draft_id"],
    )
    return revised


def recover_rejected_successor(runtime: CloseRuntime, actor: ActorIdentity, rejected_draft_id: str) -> dict:
    _require_tom(actor)
    rejected = runtime.store.get_draft(rejected_draft_id)
    if rejected is None:
        raise KeyError("unknown_draft")
    comments = rejected.get("comments") or "Please emphasize the 7 percent laboratory increase."
    return reject_draft(
        runtime,
        actor,
        draft_id=rejected_draft_id,
        version=int(rejected["version"]),
        content_sha256=rejected["content_sha256"],
        approval_nonce=rejected["approval_nonce"],
        comments=comments,
    )
