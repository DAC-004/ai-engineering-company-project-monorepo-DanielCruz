"""Controlled live GGUF evidence through Supervisor plan and fact selection.

Non-empty transport text alone is smoke, not this proof. Fallback keyword
routing and canonical fact rendering are failures here, not passes. A missing
GGUF or load error is a capacity failure, not a skip.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest

from agents.supplier_contracts.generation import configured_transport
from agents.supplier_contracts.runtime import ContractRuntime
from agents.supplier_contracts.supervisor import Supervisor
from agents.supplier_contracts.types import SupervisorRequest
from data.pipelines.rag import local_llm_is_loaded, release_local_llm
from shared.healthcore_rag.config import GENERATION_API_KEY, LOCAL_GENERATION_GGUF_FILENAME, MODELS_DIR

LIVE_ENV = "SUPPLIER_CONTRACTS_LIVE_GENERATION"
PROOF_ENV = "SUPPLIER_CONTRACTS_LIVE_PROOF"
EXPECTED_S01_NOTICE_DEADLINE = "2027-03-06"


def _live_requested() -> bool:
    return os.environ.get(LIVE_ENV, "").strip() == "1"


def _write_proof(payload: dict[str, object]) -> None:
    raw = os.environ.get(PROOF_ENV, "").strip()
    if not raw:
        return
    path = Path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@pytest.mark.skipif(not _live_requested(), reason=f"Set {LIVE_ENV}=1 for the local GGUF Supervisor proof")
def test_supervisor_live_model_plan_and_fact_selection(tmp_path: Path) -> None:
    if GENERATION_API_KEY:
        pytest.fail("capacity_failure: GENERATION_API_KEY is set, so the adapter would use a remote provider.")
    model_file = Path(MODELS_DIR) / LOCAL_GENERATION_GGUF_FILENAME
    if not model_file.is_file() or model_file.stat().st_size <= 0:
        pytest.fail(f"capacity_failure: local GGUF is missing: {model_file}")

    runtime = ContractRuntime(raw=tmp_path / "raw", process=tmp_path / "process", as_of=date(2026, 11, 6))
    supervisor = Supervisor(runtime, transport=configured_transport)
    try:
        try:
            response = supervisor.handle(
                SupervisorRequest(
                    kind="question",
                    question="When is the non-renewal notice deadline?",
                    supplier_id="HC-S01",
                )
            )
        except Exception as exc:
            proof = {
                "outcome": "capacity_or_runtime_failure",
                "error_type": type(exc).__name__,
                "gguf": str(model_file),
                "model_loaded": local_llm_is_loaded(),
                **supervisor.safe_generation_diagnostics(),
            }
            _write_proof(proof)
            pytest.fail(f"capacity_or_runtime_failure: {type(exc).__name__}")
        loaded = local_llm_is_loaded()
        exact_deadline = EXPECTED_S01_NOTICE_DEADLINE in response.answer
        proof = {
            "outcome": "sampled",
            "kind_blocked": response.blocked,
            "contracts_present": response.contracts is not None,
            "expected_notice_deadline": EXPECTED_S01_NOTICE_DEADLINE,
            "exact_notice_deadline_in_answer": exact_deadline,
            "gguf": str(model_file),
            "model_loaded": loaded,
            **supervisor.safe_generation_diagnostics(),
        }
        _write_proof(proof)
        if supervisor.last_plan_source != "model":
            pytest.fail(
                f"fallback_failure: interpret_plan source={supervisor.last_plan_source} "
                "(keyword fallback is not live model evidence)"
            )
        if supervisor.last_write_source != "model":
            pytest.fail(
                f"fallback_failure: write_from_facts source={supervisor.last_write_source} "
                "(canonical/invalid selection is not live fact-selection evidence)"
            )
        assert loaded is True
        assert response.blocked is False
        assert response.contracts is not None
        assert "notice_deadline" in response.answer
        assert EXPECTED_S01_NOTICE_DEADLINE in response.answer
    finally:
        release_local_llm()
