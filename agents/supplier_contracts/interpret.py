"""Bounded model interpretation via the Task 4 generation adapter.

The model may choose allowlisted tools and order optional fact IDs. It does not
compute prices or author DPA/approval outcomes. Keyword routing is a fallback
when no transport is injected. Live generation is never the default.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from agents.supplier_contracts.facts import (
    MANDATORY_CATEGORIES,
    RETAINED_FACT_IDS,
    FactBlock,
    catalog_for_model,
    render_fact_blocks,
)
from agents.supplier_contracts.generation import (
    TransportFn,
    build_plan_messages,
    build_write_messages,
    run_task4_messages,
)
from agents.supplier_contracts.identity import FORBIDDEN_TOOLS, SUPERVISOR_TOOLS
from agents.supplier_contracts.privacy import (
    OutOfScopeError,
    PatientLevelError,
    assert_clean_mapping,
    reject_out_of_scope,
    reject_patient_level,
)
from agents.supplier_contracts.routing import classify_question, pricing_calculation
from agents.supplier_contracts.types import RequestKind

CompleteFn = Callable[..., str]
_JSON_OBJECT = re.compile(r"\{.*\}", re.S)
_JSON_ARRAY = re.compile(r"\[.*\]", re.S)
VALID_KINDS = {
    "question",
    "evaluate_increase",
    "impact",
    "compare",
    "brief",
    "draft_communication",
    "missing_agreements",
}
_UNSUPPORTED_OVERRIDE = re.compile(
    r"no dpa is needed|proceed without compliance|bypass.{0,40}dpa|admin.{0,20}bypass",
    re.I,
)


def _reject_before_model(question: str) -> None:
    reject_patient_level(question)
    reject_out_of_scope(question)


@dataclass(frozen=True)
class PlanTrace:
    kind: RequestKind
    calculation: str
    source: str
    tools: tuple[str, ...]
    json_shape: str
    parsed_kind: str | None
    parsed_kind_status: str


@dataclass(frozen=True)
class WriteTrace:
    answer: str
    source: str
    json_shape: str
    unknown_id_count: int
    unknown_id_digest: str | None
    selected_count: int


def _kind_diagnostic(raw_kind: str | None) -> tuple[str | None, str]:
    if raw_kind is None or raw_kind == "":
        return None, "missing"
    if raw_kind in VALID_KINDS:
        return raw_kind, "valid"
    return None, "invalid"


def _unknown_id_digest(unknown: Sequence[str]) -> str | None:
    if not unknown:
        return None
    material = "\n".join(sorted(unknown)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _plan_json_shape(raw: str) -> tuple[str, dict | None]:
    if not (raw or "").strip():
        return "empty", None
    if _JSON_OBJECT.search(raw) is None:
        if _JSON_ARRAY.search(raw):
            return "array", None
        return "no_json_object", None
    match = _JSON_OBJECT.search(raw)
    try:
        data = json.loads(match.group(0) if match else raw)
    except json.JSONDecodeError:
        return "object_parse_error", None
    if not isinstance(data, dict):
        return "non_object", None
    if "kind" not in data:
        return "object_missing_kind", data
    return "object_with_kind", data


def _write_json_shape(written: str) -> str:
    if not (written or "").strip():
        return "empty"
    if selected_fact_id_order(written) is not None:
        if _JSON_OBJECT.search(written) and '"fact_ids"' in written:
            return "object_with_fact_ids"
        return "array_of_ids"
    if _JSON_OBJECT.search(written):
        return "object_without_usable_fact_ids"
    if _JSON_ARRAY.search(written):
        return "array_without_usable_ids"
    return "no_json"


def interpret_plan_result(
    question: str,
    supplier_id: str,
    *,
    kind_hint: RequestKind = "question",
    complete: CompleteFn | None = None,
    transport: TransportFn | None = None,
) -> PlanTrace:
    """Plan with safe JSON-shape diagnostics. Does not retain model text."""
    _reject_before_model(question)
    if kind_hint != "question":
        parsed_kind, parsed_status = _kind_diagnostic(kind_hint)
        return PlanTrace(
            kind_hint,
            pricing_calculation(kind_hint),
            "hint",
            (),
            "kind_hint",
            parsed_kind,
            parsed_status,
        )
    if complete is None and transport is None:
        resolved = classify_question("question", question)
        return PlanTrace(resolved, pricing_calculation(resolved), "fallback", (), "no_model", None, "no_model")
    json_shape = "unparsed"
    parsed_kind: str | None = None
    parsed_kind_status = "unparsed"
    try:
        if transport is not None:
            raw = run_task4_messages(build_plan_messages(question, supplier_id), transport=transport)
        else:
            context = [
                {
                    "source_document": "supplier-contracts-tools",
                    "section": "allowlist",
                    "text": "Allowed tools: consult_pricing, consult_contracts.",
                }
            ]
            assert_clean_mapping(context)
            raw = complete("Return JSON kind and allowlisted tools only.", context)
        json_shape, data = _plan_json_shape(raw or "")
        if data is None:
            raise ValueError("unusable_plan_json")
        kind = str(data.get("kind") or "")
        parsed_kind, parsed_kind_status = _kind_diagnostic(kind)
        tools = [str(item) for item in data.get("tools") or []]
        if any(tool in FORBIDDEN_TOOLS for tool in tools):
            raise ValueError("forbidden_tool")
        if any(tool not in SUPERVISOR_TOOLS for tool in tools):
            raise ValueError("tool_not_allowed")
        if parsed_kind is None:
            raise ValueError("invalid_kind")
        resolved = parsed_kind  # type: ignore[assignment]
        return PlanTrace(
            resolved,
            pricing_calculation(resolved),
            "model",
            tuple(tools),
            json_shape,
            parsed_kind,
            parsed_kind_status,
        )
    except (PatientLevelError, OutOfScopeError):
        raise
    except Exception:
        resolved = classify_question("question", question)
        return PlanTrace(
            resolved,
            pricing_calculation(resolved),
            "fallback",
            (),
            json_shape,
            parsed_kind,
            parsed_kind_status,
        )


def interpret_plan(
    question: str,
    supplier_id: str,
    *,
    kind_hint: RequestKind = "question",
    complete: CompleteFn | None = None,
    transport: TransportFn | None = None,
) -> tuple[RequestKind, str, str]:
    """Return (kind, calculation, source) where source is 'model' or 'fallback'."""
    trace = interpret_plan_result(
        question,
        supplier_id,
        kind_hint=kind_hint,
        complete=complete,
        transport=transport,
    )
    return trace.kind, trace.calculation, trace.source


def _as_blocks(facts: Sequence[FactBlock] | str) -> tuple[FactBlock, ...]:
    if isinstance(facts, str):
        return (FactBlock("trusted", "compliance", facts),)
    return tuple(facts)


def _fact_ids_from_payload(data: object) -> list[str] | None:
    if isinstance(data, list) and all(isinstance(item, str) for item in data):
        return [str(item) for item in data]
    if not isinstance(data, dict) or "fact_ids" not in data:
        return None
    raw_ids = data.get("fact_ids")
    if not isinstance(raw_ids, list):
        return None
    return [str(item) for item in raw_ids]


def selected_fact_id_order(written: str) -> list[str] | None:
    text = written or ""
    for pattern in (_JSON_OBJECT, _JSON_ARRAY):
        match = pattern.search(text)
        if match is None:
            continue
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        parsed = _fact_ids_from_payload(data)
        if parsed is not None:
            return parsed
    return None


def compose_selected_blocks(blocks: tuple[FactBlock, ...], ordered_ids: list[str]) -> tuple[FactBlock, ...]:
    mandatory = [
        block
        for block in blocks
        if block.category in MANDATORY_CATEGORIES or block.fact_id in RETAINED_FACT_IDS
    ]
    by_id = {block.fact_id: block for block in blocks}
    seen = {block.fact_id for block in mandatory}
    extras: list[FactBlock] = []
    for fact_id in ordered_ids:
        if fact_id in seen:
            continue
        block = by_id.get(fact_id)
        if block is None:
            continue
        extras.append(block)
        seen.add(fact_id)
    return tuple(mandatory + extras)


def ground_written_answer(written: str, facts: Sequence[FactBlock] | str) -> str:
    """Compose verified blocks. Model prose is never appended.

    Mandatory compliance, approval, and source blocks are always first.
    Optional blocks follow the model's valid fact_id order. Invalid,
    contradictory, or free-prose output falls back to canonical specialist order.
    """
    blocks = _as_blocks(facts)
    canonical = render_fact_blocks(blocks)
    if not written.strip() or _UNSUPPORTED_OVERRIDE.search(written):
        return canonical
    ordered_ids = selected_fact_id_order(written)
    if ordered_ids is None:
        return canonical
    allowed = {block.fact_id for block in blocks}
    if any(fact_id not in allowed for fact_id in ordered_ids):
        return canonical
    return render_fact_blocks(compose_selected_blocks(blocks, ordered_ids))


def write_from_facts_result(
    question: str,
    blocks: tuple[FactBlock, ...],
    *,
    complete: CompleteFn | None = None,
    transport: TransportFn | None = None,
) -> WriteTrace:
    """Write with safe JSON-shape and unknown-id diagnostics. Does not retain model text."""
    _reject_before_model(question)
    catalog = catalog_for_model(blocks)
    canonical = render_fact_blocks(blocks)
    if complete is None and transport is None:
        return WriteTrace(canonical, "canonical", "no_model", 0, None, 0)
    try:
        if transport is not None:
            written = run_task4_messages(build_write_messages(question, catalog), transport=transport)
        else:
            written = complete(
                "Select fact_ids from the specialist catalog. Reply with JSON only.",
                catalog,
            )
    except (PatientLevelError, OutOfScopeError):
        raise
    except Exception:
        return WriteTrace(canonical, "transport_error", "transport_error", 0, None, 0)
    json_shape = _write_json_shape(written)
    if not written.strip() or _UNSUPPORTED_OVERRIDE.search(written):
        return WriteTrace(canonical, "unsupported_or_empty", json_shape, 0, None, 0)
    ordered_ids = selected_fact_id_order(written)
    if ordered_ids is None:
        return WriteTrace(canonical, "invalid_selection", json_shape, 0, None, 0)
    allowed = {block.fact_id for block in blocks}
    unknown = [fact_id for fact_id in ordered_ids if fact_id not in allowed]
    if unknown:
        return WriteTrace(
            canonical,
            "invalid_selection",
            json_shape,
            len(unknown),
            _unknown_id_digest(unknown),
            len(ordered_ids),
        )
    return WriteTrace(
        render_fact_blocks(compose_selected_blocks(blocks, ordered_ids)),
        "model",
        json_shape,
        0,
        None,
        len(ordered_ids),
    )


def write_from_facts_reported(
    question: str,
    blocks: tuple[FactBlock, ...],
    *,
    complete: CompleteFn | None = None,
    transport: TransportFn | None = None,
) -> tuple[str, str]:
    """Return (answer, source) where source is model, canonical, invalid_selection, or transport_error."""
    trace = write_from_facts_result(
        question,
        blocks,
        complete=complete,
        transport=transport,
    )
    return trace.answer, trace.source


def write_from_facts(
    question: str,
    blocks: tuple[FactBlock, ...],
    *,
    complete: CompleteFn | None = None,
    transport: TransportFn | None = None,
) -> str:
    return write_from_facts_result(
        question,
        blocks,
        complete=complete,
        transport=transport,
    ).answer


def write_from_trusted(
    question: str,
    trusted: str,
    *,
    complete: CompleteFn | None = None,
    transport: TransportFn | None = None,
) -> str:
    return write_from_facts(
        question,
        _as_blocks(trusted),
        complete=complete,
        transport=transport,
    )
