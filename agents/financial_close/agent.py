"""Single financial-close agent: model-selected tools, then grounded writer."""

from __future__ import annotations

import hashlib
import json
import secrets
from uuid import uuid4

from agents.financial_close.constants import AGENT_ID, LINE_IDS
from agents.financial_close.generation import (
    build_plan_messages,
    build_write_messages,
    parse_plan_payload,
    parse_write_payload,
    run_task5_messages,
    text_is_grounded,
)
from agents.financial_close.privacy import assert_clean_mapping
from agents.financial_close.runtime import CloseRuntime
from agents.financial_close.serialize import (
    LAB_QUANTITY_CAVEAT,
    allowed_number_catalog,
    build_report,
    default_hypotheses,
    evidence_sentences,
    known_reference_catalog,
    number_catalogs_by_line,
    writer_projection,
)
from agents.financial_close.store import PeriodRunBusy
from agents.financial_close.tools import CalculationToolbox
from agents.financial_close.types import CloseFacts


def _hash_report(report: dict) -> str:
    encoded = json.dumps(report, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_comments(comments: str | None, allowed_numbers: set[str], allowed_ids: set[str]) -> str | None:
    if not comments or not comments.strip():
        return None
    if not text_is_grounded(comments, allowed_numbers, allowed_ids):
        return None
    return comments.strip()


def _retain_lab_caveat(hypotheses: dict[str, str]) -> dict[str, str]:
    current = hypotheses.get("us_laboratory")
    if not current:
        return hypotheses
    lowered = current.lower()
    if "brief expectation" in lowered and "not observed budget quantity" in lowered:
        return hypotheses
    hypotheses["us_laboratory"] = f"{current.rstrip('. ')}. {LAB_QUANTITY_CAVEAT}."
    return hypotheses


def compute_close_facts(
    runtime: CloseRuntime,
    *,
    catch_up: bool = False,
) -> tuple[CloseFacts, CalculationToolbox, str | None]:
    toolbox = CalculationToolbox(raw_dir=runtime.raw, load_date=runtime.load_date(), catch_up=catch_up)
    planned: list[str] = []
    mandatory: tuple[str, ...] = ()
    plan_raw: str | None = None
    if runtime.transport is not None:
        plan_raw = run_task5_messages(build_plan_messages(), transport=runtime.transport)
        planned = parse_plan_payload(plan_raw)
        mandatory = ("ingest_and_normalize",)
    facts = toolbox.invoke(planned, mandatory=mandatory)
    return facts, toolbox, plan_raw


def compose_close_draft(
    runtime: CloseRuntime,
    facts: CloseFacts,
    toolbox: CalculationToolbox,
    *,
    comments: str | None = None,
    parent_version: int | None = None,
    plan_raw: str | None = None,
) -> dict:
    catalog = allowed_number_catalog(facts)
    known_ids = known_reference_catalog(facts)
    safe_comments = _safe_comments(comments, catalog, known_ids)
    projection = writer_projection(facts)
    evidence = evidence_sentences(facts)
    hypotheses = default_hypotheses(facts)
    summary: list[str] = []
    model_hypotheses: dict[str, str] = {}
    write_raw: str | None = None
    source = "deterministic_fallback"
    if runtime.transport is not None:
        needed = {line_id for line_id, fact in facts.lines.items() if fact.relevant}

        def _parse(raw: str) -> tuple[dict[str, str], list[str]]:
            return parse_write_payload(
                raw,
                set(LINE_IDS),
                catalog,
                number_catalogs_by_line(facts),
                known_ids,
                evidence,
            )

        messages = build_write_messages(projection, comments=safe_comments)
        write_raw = run_task5_messages(messages, transport=runtime.transport)
        parsed_hypo, parsed_summary = _parse(write_raw)
        if needed - set(parsed_hypo):
            retry_raw = run_task5_messages(
                build_write_messages(projection, comments=safe_comments, retry=True),
                transport=runtime.transport,
            )
            retry_hypo, retry_summary = _parse(retry_raw)
            if set(retry_hypo) >= set(parsed_hypo):
                write_raw = retry_raw
                parsed_hypo, parsed_summary = retry_hypo, retry_summary
        model_hypotheses = parsed_hypo
        # Live proof requires every relevant hypothesis from the raw writer, not defaults.
        # Each accepted line copies its evidence sentence; parse adds uncertainty framing.
        if needed and needed <= set(parsed_hypo) and needed <= set(evidence):
            hypotheses.update(parsed_hypo)
            hypotheses = _retain_lab_caveat(hypotheses)
            source = "model"
        summary = parsed_summary
    report = build_report(
        facts,
        hypotheses=hypotheses,
        summary_lines=summary or None,
        reviewer_guidance=safe_comments,
    )
    draft = {
        "draft_id": uuid4().hex,
        "period": facts.period,
        "version": 0,
        "content_sha256": _hash_report(report),
        "approval_nonce": secrets.token_hex(16),
        "state": "awaiting_tom",
        "report": report,
        "comments": safe_comments,
        "parent_version": parent_version,
        "facts_digest": facts.digest,
        "write_source": source,
        "actor_id": AGENT_ID,
        "tools": list(dict.fromkeys(facts.invoked_tools)),
        "model_selected_tools": list(facts.model_selected_tools),
        "dependency_tools": list(facts.dependency_tools),
        "deterministic_fallback": facts.deterministic_fallback,
        "tool_results": {
            "convert_gbp_usd": toolbox.tool_results.get("convert_gbp_usd"),
            "select_relevant_deviations": toolbox.tool_results.get("select_relevant_deviations"),
        },
        # plan_raw/write_raw stay in-memory for contribution proof. Never persist or audit them.
        "plan_raw": plan_raw,
        "write_raw": write_raw,
        "model_hypotheses": model_hypotheses,
    }
    assert_clean_mapping(
        {
            key: value
            for key, value in draft.items()
            if key not in {"report", "tool_results", "plan_raw", "write_raw", "model_hypotheses"}
        }
    )
    return draft


def build_close_draft(
    runtime: CloseRuntime,
    *,
    catch_up: bool = False,
    comments: str | None = None,
    parent_version: int | None = None,
) -> dict:
    facts, toolbox, plan_raw = compute_close_facts(runtime, catch_up=catch_up)
    return compose_close_draft(
        runtime,
        facts,
        toolbox,
        comments=comments,
        parent_version=parent_version,
        plan_raw=plan_raw,
    )


def _notify_quarantine(runtime: CloseRuntime, draft: dict) -> None:
    quarantined = tuple(
        item.get("entry_id")
        for item in draft["report"].get("missing_or_uncertain") or []
        if item.get("entry_id")
    )
    if quarantined:
        from agents.financial_close.distribution import notify_claire_quarantine

        notify_claire_quarantine(runtime, draft["period"], int(draft["version"]), quarantined)


def run_close(
    runtime: CloseRuntime,
    *,
    catch_up: bool = False,
    comments: str | None = None,
    parent_version: int | None = None,
) -> dict:
    owner = uuid4().hex
    facts, toolbox, plan_raw = compute_close_facts(runtime, catch_up=catch_up)
    status, existing_id = runtime.store.begin_period_run(facts.period, facts.digest, owner)
    if status == "exists" and existing_id:
        existing = runtime.store.get_draft(existing_id)
        if existing is not None:
            return existing
    if status == "busy":
        raise PeriodRunBusy("period_run_active", existing_id)
    draft = compose_close_draft(
        runtime,
        facts,
        toolbox,
        comments=comments,
        parent_version=parent_version,
        plan_raw=plan_raw,
    )
    ephemeral = {
        key: draft.pop(key, None)
        for key in ("tool_results", "plan_raw", "write_raw", "model_hypotheses")
    }
    persisted = runtime.store.finalize_new_draft(
        draft,
        facts_digest=facts.digest,
        catch_up=catch_up,
        owner=owner,
    )
    for key, value in ephemeral.items():
        if value is not None:
            persisted[key] = value
    _notify_quarantine(runtime, persisted)
    runtime.audit.record(
        "draft_saved",
        period=persisted["period"],
        draft_id=persisted["draft_id"],
        version=int(persisted["version"]),
        model_selected_tools=list(facts.model_selected_tools),
        deterministic_fallback=facts.deterministic_fallback,
    )
    return persisted
