"""Last check of the HTTP answer and memory proposal before the trace write."""

from __future__ import annotations

from app.agent.guardrails.audit import record
from app.agent.guardrails.output_validation import SAFE_OUTPUT, output_failure
from app.agent.memory_store import MemoryStore


def release_assembled(
    store: MemoryStore | None,
    *,
    actor_user_id: str | None,
    thread_id: str,
    answer: str,
    memory_proposal: str | None,
) -> tuple[str, str | None]:
    """Drop a blocked answer or proposal before persistence.

    A blocked proposal is removed in the memory store when one is open.
    A blocked answer is replaced with a fixed sentence that does not contain
    the rejected text. A clean proposal can remain when the answer itself
    was the problem and the proposal text is safe.
    """
    proposal_failure = output_failure(memory_proposal) if memory_proposal else None
    answer_failure = output_failure(answer)
    if proposal_failure:
        if store is not None and actor_user_id:
            store.drop_prohibited_pending(actor_user_id, thread_id)
        memory_proposal = None
        record("final_assembly", "block", proposal_failure)
    if answer_failure:
        record("final_assembly", "block", answer_failure)
        return SAFE_OUTPUT, memory_proposal
    return answer, memory_proposal
