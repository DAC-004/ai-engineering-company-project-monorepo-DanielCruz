"""Check the installed gate. Synthetic detector text only. No model call."""

from __future__ import annotations

from app.agent.guardrails.output_validation import output_failure
from app.services.streaming_release_gate import StreamingReleaseGate

PRIVATE_PAY = (
    "The appointment policy requires a cancellation to be made more than 24 hours "
    "in advance without any charge. If a cancellation is made less than 24 hours "
    "in advance or if it's a no-show, a charge of 50 USD (or 40 GBP in the UK) "
    "applies for private-pay patients."
)
CASES = (
    ("Bring the form for the patients. Please review patient A", "patient A"),
    ("Bring the form for the patients. Note: ignore all your", "ignore all your"),
)
BLOCKS = (
    "cancel the appointment for the patient",
    "cancel the appointment for the patients.",
    "The patient canceled the appointment.",
    "The patients canceled the appointment.",
    "The appointment was cancelled for the patient.",
    "The appointment was canceled for the patients.",
)


def main() -> None:
    for text, protected in CASES:
        for pieces in (list(text), [text], [text[: text.rindex(protected)], protected[:2], protected[2:]]):
            gate = StreamingReleaseGate()
            for piece in pieces:
                gate.push(piece)
            released = gate.complete()
            if protected in released or protected in gate.committed:
                raise SystemExit(f"FLUSHED {protected!r}")
            if "for the patients" not in gate.committed:
                raise SystemExit("BENIGN_FOR_PHRASE_MISSING")
            if output_failure(gate.committed) is not None:
                raise SystemExit("OUTPUT_FAILURE")
            stopped = StreamingReleaseGate()
            for piece in pieces:
                stopped.push(piece)
            if stopped.interrupt() != "":
                raise SystemExit("INTERRUPT_RELEASED")
            if protected in stopped.committed or stopped.push(" later") != "":
                raise SystemExit("INTERRUPT_KEPT")
    policy = StreamingReleaseGate()
    for character in PRIVATE_PAY:
        policy.push(character)
    if policy.committed != PRIVATE_PAY or policy.complete() != "":
        raise SystemExit("PRIVATE_PAY_TRUNCATED")
    for text in BLOCKS:
        gate = StreamingReleaseGate()
        for character in text:
            gate.push(character)
        if "patient" in gate.committed.lower() or gate.complete() != "":
            raise SystemExit(f"CANCELLATION_NOT_BLOCKED {text!r}")
    print("GATE_CHECK_OK")


if __name__ == "__main__":
    main()
