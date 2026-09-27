"""Write reviewed support-agent traces by running the compiled graph.

The retrieval and generation functions are patched. This command does not
download a model or call a live LLM. Evals read the files this command writes;
they do not call it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.agent.graph import run_support_agent  # noqa: E402
from app.agent.tracing import load_trace  # noqa: E402

REFERRAL_DOCUMENT = (
    REPO_ROOT / "docs" / "company-knowledge-base" / "healthcore-referral-process.en.md"
)
EMPTY_QUESTION = "   \n\t"
NO_CONTEXT_QUESTION = "What is the capital of France?"
REFERRAL_QUESTION = "How long does an internal referral take?"
GROUNDED_ANSWER = (
    "The indexed referral policy says the target completed-referral time "
    "is 11 days from creation to a confirmed appointment."
)


def referral_payload() -> dict[str, Any]:
    """Use the indexed paragraph that states the 11-day referral target."""
    document = REFERRAL_DOCUMENT.read_text(encoding="utf-8")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", document) if part.strip()]
    matching = next(part for part in paragraphs if "11 days" in part)
    return {
        "company": "healthcore",
        "source_document": "referral-process",
        "section": "Target completed-referral time",
        "language": "en",
        "chunk_index": 1,
        "text": matching,
    }


def _grounded_answer(question: str, context: list[dict[str, Any]]) -> str:
    del question
    retrieved_text = "\n".join(str(item.get("text", "")) for item in context)
    if "11 days" not in retrieved_text:
        raise RuntimeError(
            "Retrieved referral context did not include the indexed 11-day timeframe."
        )
    return GROUNDED_ANSWER


def _run_case(
    question: str,
    *,
    retrieve_impl: Any,
    generate_impl: Any,
    checkpoint_path: Path,
    trace_dir: Path,
) -> dict[str, Any]:
    with (
        patch("data.pipelines.rag.retrieve", retrieve_impl),
        patch("data.pipelines.rag.generate_answer", generate_impl),
    ):
        outcome = run_support_agent(
            question,
            checkpoint_path=checkpoint_path,
            trace_dir=trace_dir,
        )
    return load_trace(outcome.trace_id, trace_dir)


def record_reviewed_traces(fixture_dir: Path, export_path: Path) -> dict[str, dict[str, Any]]:
    """Run the three review cases and write sanitized trace JSON."""
    import tempfile

    fixture_dir.mkdir(parents=True, exist_ok=True)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    payload = referral_payload()
    written: dict[str, dict[str, Any]] = {}

    with tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)
        checkpoint_path = temp_dir / "support_agent.sqlite"
        trace_dir = temp_dir / "traces"
        cases = {
            "empty_question": _run_case(
                EMPTY_QUESTION,
                retrieve_impl=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AssertionError("retrieve() ran for an empty question")
                ),
                generate_impl=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AssertionError("generate_answer() ran for an empty question")
                ),
                checkpoint_path=checkpoint_path,
                trace_dir=trace_dir,
            ),
            "no_context": _run_case(
                NO_CONTEXT_QUESTION,
                retrieve_impl=lambda *_args, **_kwargs: [],
                generate_impl=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AssertionError("generate_answer() ran without retrieved context")
                ),
                checkpoint_path=checkpoint_path,
                trace_dir=trace_dir,
            ),
            "referral_grounding": _run_case(
                REFERRAL_QUESTION,
                retrieve_impl=lambda *_args, **_kwargs: [payload],
                generate_impl=_grounded_answer,
                checkpoint_path=checkpoint_path,
                trace_dir=trace_dir,
            ),
        }
        for name, trace in cases.items():
            destination = fixture_dir / f"{name}.json"
            destination.write_text(
                (trace_dir / f"{trace['trace_id']}.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            written[name] = trace

    export_path.write_text(
        (fixture_dir / "referral_grounding.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return written


def main() -> None:
    fixture_dir = REPO_ROOT / "tests" / "pipelines" / "fixtures" / "agent_traces"
    export_path = REPO_ROOT / "docs" / "rag" / "sample-agent-trace.json"
    record_reviewed_traces(fixture_dir, export_path)


if __name__ == "__main__":
    main()
