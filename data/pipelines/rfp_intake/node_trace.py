"""Ticket-level node trace. Input and output are screened before they are stored.

A PHI hit keeps the redacted text and sets contains_phi. The blocked value is
not copied onto the record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from data.pipelines.rfp_intake.phi import screen_generated_structure


def screened_record(
    node: str,
    agent: str,
    node_input: object,
    node_output: object,
    *,
    sequence: int,
) -> dict[str, Any]:
    """Build one trace record. sequence is assigned by the caller under its lock."""
    screened_input, input_phi = screen_generated_structure(node_input)
    screened_output, output_phi = screen_generated_structure(node_output)
    record: dict[str, Any] = {
        "sequence": sequence,
        "node": node,
        "agent": agent,
        "input": screened_input,
        "output": screened_output,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if input_phi or output_phi:
        record["contains_phi"] = True
    return record


def append_trace(
    records: list[dict[str, Any]],
    node: str,
    agent: str,
    node_input: object,
    node_output: object,
) -> dict[str, Any]:
    """Append the next record. The caller holds the ticket's response lock."""
    record = screened_record(
        node,
        agent,
        node_input,
        node_output,
        sequence=len(records) + 1,
    )
    records.append(record)
    return record
