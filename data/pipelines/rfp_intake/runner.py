"""Run conversion, both PHI screens, and the intake graph for one PDF.

This function does not open a database connection. The API service persists
the returned structure after the output screen.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from data.pipelines.rfp_intake.convert import pdf_bytes_to_markdown
from data.pipelines.rfp_intake.generation import REPO_ROOT, ChatComplete, ModelAssetMissing, PipelineFailure
from data.pipelines.rfp_intake.graph import run_intake_graph
from data.pipelines.rfp_intake.handoff import build_handoff
from data.pipelines.rfp_intake.phi import bind_blocked_values, reset_blocked_values, screen_structure, screen_text
from data.pipelines.rfp_intake.readability import readability_metrics

logger = logging.getLogger("healthcore.rfp_intake")

RAW_INTAKE_DIR = REPO_ROOT / "data" / "raw" / "rfp_intake"


@dataclass
class IntakeRun:
    status: str
    processing_failed: bool
    error_code: str | None
    phi_detected: bool
    compliance_review_required: bool
    raw_pdf_path: str | None
    metadata: dict[str, Any] | None = None
    readability: dict[str, Any] | None = None
    sections: list[dict[str, Any]] = field(default_factory=list)
    summary: str | None = None
    handoff: dict[str, Any] | None = None
    reason_code: str | None = None
    node_trace: list[dict[str, Any]] = field(default_factory=list)


def _failed(
    code: str,
    *,
    phi_detected: bool = False,
    raw_pdf_path: str | None = None,
) -> IntakeRun:
    # Log the code only. Exception text can echo the document or the model completion.
    logger.error("rfp_intake_failed code=%s", code)
    return IntakeRun(
        status="analyzing",
        processing_failed=True,
        error_code=code,
        phi_detected=phi_detected,
        compliance_review_required=phi_detected,
        raw_pdf_path=raw_pdf_path,
    )


def _store_clean_pdf(pdf_bytes: bytes, ticket_id: str, storage_dir: Path) -> str:
    storage_dir.mkdir(parents=True, exist_ok=True)
    destination = storage_dir / f"{ticket_id}.pdf"
    destination.write_bytes(pdf_bytes)
    return str(destination)


def process_pdf(
    pdf_bytes: bytes,
    ticket_id: str,
    *,
    complete_fn: ChatComplete | None = None,
    storage_dir: Path | None = None,
) -> IntakeRun:
    """Process one upload. A failure leaves the caller on analyzing with an error code."""
    target_dir = storage_dir or RAW_INTAKE_DIR
    try:
        markdown = pdf_bytes_to_markdown(pdf_bytes)
    except PipelineFailure as exc:
        return _failed(exc.code)
    except Exception:
        return _failed("conversion_failed")

    screened_input = screen_text(markdown)
    phi_detected = screened_input.detected
    raw_pdf_path: str | None = None
    if phi_detected:
        # The original bytes and the unredacted markdown are not written.
        logger.error("rfp_intake_phi_input code=phi_detected ticket_id=%s", ticket_id)
    else:
        try:
            raw_pdf_path = _store_clean_pdf(pdf_bytes, ticket_id, target_dir)
        except Exception:
            return _failed("pdf_store_failed")

    token = bind_blocked_values(screened_input.blocked_values)
    try:
        metrics = readability_metrics(screened_input.text)
        state = run_intake_graph(screened_input.text, complete_fn)
    except ModelAssetMissing:
        return _failed("model_asset_missing", phi_detected=phi_detected, raw_pdf_path=raw_pdf_path)
    except PipelineFailure as exc:
        return _failed(exc.code, phi_detected=phi_detected, raw_pdf_path=raw_pdf_path)
    except Exception:
        return _failed("pipeline_exception", phi_detected=phi_detected, raw_pdf_path=raw_pdf_path)
    finally:
        reset_blocked_values(token)

    classification = state["classification"]
    if classification["decision"] == "discard":
        return IntakeRun(
            status="discarded",
            processing_failed=False,
            error_code=None,
            phi_detected=phi_detected,
            compliance_review_required=phi_detected,
            raw_pdf_path=raw_pdf_path,
            readability=metrics,
            reason_code=classification["reason_code"],
            node_trace=list(state.get("node_trace") or []),
        )

    payload = {
        "metadata": state["metadata"],
        "sections": state["worker_results"],
        "summary": state["summary"],
    }
    screened_output, output_phi, _blocked = screen_structure(
        payload,
        extra_values=screened_input.blocked_values,
    )
    assert isinstance(screened_output, dict)
    phi_detected = phi_detected or output_phi or bool(state["output_phi"])
    if output_phi:
        logger.error("rfp_intake_phi_output code=phi_detected ticket_id=%s", ticket_id)
    metadata = screened_output["metadata"]
    metadata["readability"] = metrics
    sections = screened_output["sections"]
    summary = screened_output["summary"]
    handoff = build_handoff(
        ticket_id=ticket_id,
        metadata={key: value for key, value in metadata.items() if key != "readability"},
        readability=metrics,
        sections=sections,
        summary=summary,
        phi_detected=phi_detected,
        compliance_review_required=phi_detected,
    )
    screened_handoff, handoff_phi, _blocked = screen_structure(
        handoff,
        extra_values=screened_input.blocked_values,
    )
    phi_detected = phi_detected or handoff_phi
    if isinstance(screened_handoff, dict):
        screened_handoff["phi_detected"] = phi_detected
        screened_handoff["compliance_review_required"] = phi_detected
    return IntakeRun(
        status="intake_complete",
        processing_failed=False,
        error_code=None,
        phi_detected=phi_detected,
        compliance_review_required=phi_detected,
        raw_pdf_path=raw_pdf_path,
        metadata=metadata,
        readability=metrics,
        sections=sections,
        summary=summary,
        handoff=screened_handoff if isinstance(screened_handoff, dict) else None,
        reason_code=classification["reason_code"],
        node_trace=list(state.get("node_trace") or []),
    )
