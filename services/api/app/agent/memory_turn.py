"""Turn bookends for proposal, confirmation, and retrieval.

The support graph still answers the operational question. This module decides
whether that answer may carry a memory proposal, and it resolves at most one
pending proposal before a new one can be staged.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.agent.memory_policy import (
    PHI_REFUSAL,
    PHI_WITHHELD,
    IntentDecision,
    appears_to_contain_phi,
    classify_pending_intent,
    evaluate_memorable,
    proposal_prompt,
    unverified_note_sentence,
)
from app.agent.memory_store import ApprovedFact, MemoryStore

IntentClassifier = Callable[[str, str], IntentDecision]


@dataclass(frozen=True)
class TurnPreparation:
    """What the graph is allowed to see for this turn."""

    skip_graph: bool
    graph_question: str
    trace_question: str
    answer_prefix: str
    direct_answer: str
    memory_proposal: str | None
    approved_notes: list[str]
    phi_refused: bool


def prepare_turn(
    store: MemoryStore | None,
    *,
    actor_user_id: str | None,
    thread_id: str,
    message: str,
    intent_classifier: IntentClassifier | None = None,
) -> TurnPreparation:
    """Resolve a pending proposal, or refuse PHI before the graph runs."""
    if appears_to_contain_phi(message):
        if store is not None and actor_user_id:
            pending = store.get_pending(actor_user_id, thread_id)
            store.record_phi_rejection(
                owner_user_id=actor_user_id,
                actor_user_id=actor_user_id,
                thread_id=thread_id,
                proposal_id=pending.proposal_id if pending is not None else None,
            )
        return TurnPreparation(
            skip_graph=True,
            graph_question="",
            trace_question=PHI_WITHHELD,
            answer_prefix="",
            direct_answer=PHI_REFUSAL,
            memory_proposal=None,
            approved_notes=[],
            phi_refused=True,
        )

    if store is None or not actor_user_id:
        return _plain(message)

    store.expire_stale()
    pending = store.get_pending(actor_user_id, thread_id)
    prefix = ""
    graph_message = message
    direct_answer = ""
    skip_graph = False
    memory_proposal: str | None = None

    if pending is not None:
        classifier = intent_classifier or classify_pending_intent
        decision = classifier(message, pending.text)
        resolved = _apply_decision(
            store,
            actor_user_id=actor_user_id,
            message=message,
            pending_id=pending.proposal_id,
            pending_text=pending.text,
            decision=decision,
        )
        prefix = resolved.prefix
        graph_message = resolved.graph_message
        direct_answer = resolved.direct_answer
        skip_graph = resolved.skip_graph
        memory_proposal = resolved.memory_proposal

    notes = [] if skip_graph else _note_lines(store.read_relevant(actor_user_id, graph_message))
    return TurnPreparation(
        skip_graph=skip_graph,
        graph_question=graph_message,
        trace_question=message,
        answer_prefix=prefix,
        direct_answer=direct_answer,
        memory_proposal=memory_proposal,
        approved_notes=notes,
        phi_refused=False,
    )


def finish_turn(
    store: MemoryStore | None,
    *,
    actor_user_id: str | None,
    thread_id: str,
    source_message: str,
    answer: str,
    preparation: TurnPreparation,
) -> tuple[str, str | None]:
    """Append labeled notes and, when allowed, stage one new proposal."""
    if preparation.phi_refused or store is None or not actor_user_id:
        return answer, preparation.memory_proposal

    if store.get_pending(actor_user_id, thread_id) is not None:
        return answer, preparation.memory_proposal

    candidate = evaluate_memorable(source_message)
    if candidate is None:
        return answer, preparation.memory_proposal

    staged = store.stage_proposal(
        owner_user_id=actor_user_id,
        thread_id=thread_id,
        text=candidate.proposal_text,
        kind=candidate.kind,
        subject_key=candidate.subject_key,
        originating_message=source_message,
    )
    if staged is None:
        return answer, preparation.memory_proposal

    prompt = proposal_prompt(staged.text)
    combined = answer.rstrip()
    if combined:
        combined = f"{combined}\n\n{prompt}"
    else:
        combined = prompt
    return combined, staged.text


def append_unverified_notes(answer: str, notes: list[str]) -> str:
    """Keep retrieved text and add notes that are not already in the answer."""
    extra = [note for note in notes if note not in answer]
    if not extra:
        return answer
    block = "\n".join(extra)
    if not answer.strip():
        return block
    return f"{answer.rstrip()}\n\n{block}"


@dataclass(frozen=True)
class _DecisionResult:
    prefix: str
    graph_message: str
    direct_answer: str
    skip_graph: bool
    memory_proposal: str | None


def _apply_decision(
    store: MemoryStore,
    *,
    actor_user_id: str,
    message: str,
    pending_id: str,
    pending_text: str,
    decision: IntentDecision,
) -> _DecisionResult:
    residual = decision.residual_question
    if decision.label == "approve":
        fact = store.write_approved(
            actor_user_id=actor_user_id,
            proposal_id=pending_id,
            originating_message=message,
        )
        if fact is None:
            return _DecisionResult(
                prefix="",
                graph_message=message,
                direct_answer=PHI_REFUSAL,
                skip_graph=True,
                memory_proposal=None,
            )
        confirmation = (
            "I'll store that as an unverified operational note for your account. "
            "It does not replace company knowledge."
        )
        if residual:
            return _DecisionResult(
                prefix=confirmation,
                graph_message=residual,
                direct_answer="",
                skip_graph=False,
                memory_proposal=None,
            )
        return _DecisionResult(
            prefix="",
            graph_message="",
            direct_answer=confirmation,
            skip_graph=True,
            memory_proposal=None,
        )

    if decision.label == "reject":
        store.reject_pending(
            actor_user_id=actor_user_id,
            proposal_id=pending_id,
            originating_message=message,
        )
        refusal = "I won't store that."
        if residual:
            return _DecisionResult(
                prefix=refusal,
                graph_message=residual,
                direct_answer="",
                skip_graph=False,
                memory_proposal=None,
            )
        return _DecisionResult(
            prefix="",
            graph_message="",
            direct_answer=refusal,
            skip_graph=True,
            memory_proposal=None,
        )

    if decision.label == "edit":
        revised = decision.revised_text or ""
        updated = store.edit_pending(
            actor_user_id=actor_user_id,
            proposal_id=pending_id,
            revised_text=revised,
            originating_message=message,
        )
        if updated is None:
            return _DecisionResult(
                prefix="",
                graph_message="",
                direct_answer=PHI_REFUSAL,
                skip_graph=True,
                memory_proposal=None,
            )
        prompt = proposal_prompt(updated.text)
        edited = f"I updated the pending note. I have not stored it yet. {prompt}"
        if residual:
            return _DecisionResult(
                prefix=edited,
                graph_message=residual,
                direct_answer="",
                skip_graph=False,
                memory_proposal=updated.text,
            )
        return _DecisionResult(
            prefix="",
            graph_message="",
            direct_answer=edited,
            skip_graph=True,
            memory_proposal=updated.text,
        )

    store.discard_pending(
        actor_user_id=actor_user_id,
        proposal_id=pending_id,
        originating_message=message,
    )
    notice = "I set aside the pending memory proposal because that reply was not a clear decision."
    return _DecisionResult(
        prefix=f"{notice}\n\n",
        graph_message=message,
        direct_answer="",
        skip_graph=False,
        memory_proposal=None,
    )


def _note_lines(facts: list[ApprovedFact]) -> list[str]:
    return [unverified_note_sentence(fact.text) for fact in facts if fact.claim_status == "unverified"]


def _plain(message: str) -> TurnPreparation:
    return TurnPreparation(
        skip_graph=False,
        graph_question=message,
        trace_question=message,
        answer_prefix="",
        direct_answer="",
        memory_proposal=None,
        approved_notes=[],
        phi_refused=False,
    )
