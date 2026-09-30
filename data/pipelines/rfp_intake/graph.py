"""Dedicated rfp_intake graph. Nodes call the agents. They do not contain a second decision."""

from __future__ import annotations

import contextvars
import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from data.pipelines.rfp_intake.agents import (
    analyze_department,
    classify_rfp,
    orchestrate_rfp,
    synthesize_findings,
)
from data.pipelines.rfp_intake.grounding import apply_source_grounding
from data.pipelines.rfp_intake.departments import DEPARTMENT_IDS
from data.pipelines.rfp_intake.generation import ChatComplete
from data.pipelines.rfp_intake.node_trace import screened_record

_complete_fn: contextvars.ContextVar[ChatComplete | None] = contextvars.ContextVar(
    "rfp_complete_fn",
    default=None,
)


class IntakeState(TypedDict):
    screened_markdown: str
    classification: dict[str, str]
    metadata: dict[str, Any]
    extracts: dict[str, str]
    unknown_departments: list[str]
    worker_results: Annotated[list[dict[str, Any]], operator.add]
    summary: str
    unresolved_disagreements: list[str]
    output_phi: bool
    node_trace: Annotated[list[dict[str, Any]], operator.add]


def _trace(node: str, agent: str, node_input: object, node_output: object) -> dict[str, Any]:
    return screened_record(node, agent, node_input, node_output, sequence=0)


def _classify(state: IntakeState) -> dict[str, Any]:
    classification = classify_rfp(state["screened_markdown"], _complete_fn.get())
    return {
        "classification": classification,
        "node_trace": [_trace("classify", "classifier", {"source": "screened_markdown"}, classification)],
    }


def _route_after_classify(state: IntakeState) -> str:
    if state["classification"]["decision"] == "discard":
        return "stop"
    return "orchestrate"


def _orchestrate(state: IntakeState) -> dict[str, Any]:
    decomposed = orchestrate_rfp(state["screened_markdown"], _complete_fn.get())
    metadata = {
        "client_name": decomposed["client_name"],
        "client_country": decomposed["client_country"],
        "program_type": decomposed["program_type"],
        "covered_population": decomposed["covered_population"],
        "deadline": decomposed["deadline"],
        "budget_range": decomposed["budget_range"],
        "departments_needed": list(DEPARTMENT_IDS),
    }
    update = {
        "metadata": metadata,
        "extracts": decomposed["extracts"],
        "unknown_departments": decomposed["unknown_departments"],
    }
    return {
        **update,
        "node_trace": [_trace("orchestrate", "orchestrator", {"source": "screened_markdown"}, metadata)],
    }


def _worker(department_id: str):
    def run(state: IntakeState) -> dict[str, Any]:
        section = analyze_department(
            department_id,
            state["metadata"],
            state["extracts"].get(department_id, ""),
            _complete_fn.get(),
        )
        if department_id == "revenue" and state["unknown_departments"]:
            note = "Unrecognized department name: " + ", ".join(state["unknown_departments"])
            section["open_questions"] = [*section["open_questions"], note]
        return {
            "worker_results": [section],
            "node_trace": [
                _trace(
                    f"{department_id}_worker",
                    section.get("contact_name") or department_id,
                    {"department_id": department_id},
                    section,
                )
            ],
        }

    return run


def _synthesize(state: IntakeState) -> dict[str, Any]:
    # defer=True waits until revenue, clinical, and compliance have all written.
    result = synthesize_findings(state["metadata"], state["worker_results"], _complete_fn.get())
    update = {
        "summary": result["summary"],
        "unresolved_disagreements": result["unresolved_disagreements"],
        "output_phi": result["phi_detected"],
    }
    return {
        **update,
        "node_trace": [_trace("synthesize", "synthesizer", {"departments": list(DEPARTMENT_IDS)}, update)],
    }


def _stop(state: IntakeState) -> dict[str, Any]:
    reason = state.get("classification", {}).get("reason_code")
    return {"node_trace": [_trace("stop", "classifier", {"reason_code": reason}, {"stopped": True})]}


def build_intake_graph():
    """Compile the dedicated intake graph. There is no checkpointer and no CX node."""
    graph = StateGraph(IntakeState)
    graph.add_node("classify", _classify)
    graph.add_node("orchestrate", _orchestrate)
    graph.add_node("revenue_worker", _worker("revenue"))
    graph.add_node("clinical_worker", _worker("clinical"))
    graph.add_node("compliance_worker", _worker("compliance"))
    graph.add_node("synthesize", _synthesize, defer=True)
    graph.add_node("stop", _stop)
    graph.set_entry_point("classify")
    graph.add_conditional_edges(
        "classify",
        _route_after_classify,
        {"stop": "stop", "orchestrate": "orchestrate"},
    )
    graph.add_edge("stop", END)
    for department_id in ("revenue_worker", "clinical_worker", "compliance_worker"):
        graph.add_edge("orchestrate", department_id)
        graph.add_edge(department_id, "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


_compiled = None


def run_intake_graph(screened_markdown: str, complete_fn: ChatComplete | None = None) -> IntakeState:
    """Run one document through the classifier, orchestrator, workers, and synthesizer."""
    global _compiled
    if _compiled is None:
        _compiled = build_intake_graph()
    token = _complete_fn.set(complete_fn)
    try:
        state = _compiled.invoke(
            {
                "screened_markdown": screened_markdown,
                "classification": {"decision": "", "reason_code": ""},
                "metadata": {},
                "extracts": {},
                "unknown_departments": [],
                "worker_results": [],
                "summary": "",
                "unresolved_disagreements": [],
                "output_phi": False,
                "node_trace": [],
            }
        )
        for index, record in enumerate(state.get("node_trace") or [], start=1):
            record["sequence"] = index
    finally:
        _complete_fn.reset(token)
    # The synthesizer has already written. Repair placement and deadline wording
    # from the screened document before the handoff is built.
    if state["classification"].get("decision") == "accept":
        metadata, sections, summary = apply_source_grounding(
            state["screened_markdown"],
            state["metadata"],
            state["worker_results"],
            state["summary"],
        )
        state = {
            **state,
            "metadata": metadata,
            "worker_results": sections,
            "summary": summary,
        }
    return state
