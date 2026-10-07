"""Deterministic checks for the streaming release gate.

Fixtures use detector vocabulary only. They are not patient records.
No model, socket, or live generation is started.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
for import_path in (str(REPO_ROOT), str(API_ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from app.agent.guardrails.output_validation import (  # noqa: E402
    SAFE_OUTPUT,
    output_failure,
    safe_output,
)
from app.agent.guardrails.text_rules import (  # noqa: E402
    _NAMED_PATIENT,
    disclosure_is_prohibited,
)
from app.agent.memory_policy import (  # noqa: E402
    _NAMED_AS_PATIENT,
    _PATIENT_NAME,
    _PHI_TERMS,
    _cites_an_appointment_cancellation_for_a_patient,
    appears_to_contain_phi,
)
from app.services.streaming_release_gate import (  # noqa: E402
    _FIXED_PHRASES,
    _PATTERN_SOURCES,
    StreamingReleaseGate,
)

ORDINARY = "UK GDPR requires a documented basis."
ORDINARY_OPEN_TAIL = "UK GDPR requires a documented basis"
OPEN_PATIENT_PREFIX = "Please review patient A"
OPEN_INSTRUCTION_PREFIX = "Note: ignore all your"
THREE_WORD = "cancel the appointment for the patient"
JOHNSON = "Patient Johnson cancelled tomorrow's appointment, note that down."
PATIENT_SMITH = "patient Smith had a failed referral"
PRIVATE_PAY_POLICY = (
    "The appointment policy requires a cancellation to be made more than 24 hours "
    "in advance without any charge. If a cancellation is made less than 24 hours "
    "in advance or if it's a no-show, a charge of 50 USD (or 40 GBP in the UK) "
    "applies for private-pay patients."
)
_CANCEL_FORMS = (
    "cancel",
    "cancelled",
    "canceled",
    "cancelling",
    "canceling",
    "cancellation",
    "cancelation",
)
PLURAL_PATIENTS = "cancel the appointment for the patients."
PATIENT_CANCELED = "The patient canceled the appointment."
PATIENTS_CANCELED = "The patients canceled the appointment."
PASSIVE_UK = "The appointment was cancelled for the patient."
PASSIVE_US = "The appointment was canceled for the patients."
PASSIVE_FRONT = "For the patients, the appointment was canceled."
PASSIVE_MIDDLE = "The appointment for the patient was cancelled."
# Eleven words sit between "appointment" and "cancelled".
LONG_PASSIVE = (
    "The appointment originally scheduled by the downtown clinic after the referral "
    "review was cancelled for the patient."
)
# Ten words sit between "patient" and "canceled".
LONG_ACTOR = (
    "The patient called the downtown clinic after the referral review and then "
    "canceled the appointment."
)
GENERIC_CATEGORY = "A cancellation notice before the appointment applies to patients."


def _chunk_partitions(text: str) -> list[list[str]]:
    partitions = [
        [text],
        list(text),
    ]
    for width in (2, 3, 5):
        partitions.append([text[index : index + width] for index in range(0, len(text), width)])
    if len(text) > 4:
        partitions.append([text[:1], text[1:4], text[4:]])
    return partitions


def _replay(chunks: list[str]) -> StreamingReleaseGate:
    gate = StreamingReleaseGate()
    emitted: list[str] = []
    for chunk in chunks:
        emitted.append(gate.push(chunk))
    assert "".join(emitted) == gate.committed
    return gate


def _assert_partition_stable(text: str) -> StreamingReleaseGate:
    gates = [_replay(partition) for partition in _chunk_partitions(text)]
    reference = gates[0]
    assert all(gate.committed == reference.committed for gate in gates)
    assert all(gate.held == reference.held for gate in gates)
    assert all(gate.stopped == reference.stopped for gate in gates)
    assert not appears_to_contain_phi(reference.committed)
    assert not disclosure_is_prohibited(reference.committed)
    assert text.startswith(reference.committed)
    return reference


def test_fixed_phrases_belong_to_existing_detectors() -> None:
    for phrase in _FIXED_PHRASES:
        assert any(pattern.search(phrase) for pattern in _PATTERN_SOURCES), phrase


def test_fixture_detector_baseline() -> None:
    assert not appears_to_contain_phi(ORDINARY)
    assert not disclosure_is_prohibited(ORDINARY)
    assert not appears_to_contain_phi(ORDINARY_OPEN_TAIL)
    assert not disclosure_is_prohibited(ORDINARY_OPEN_TAIL)
    assert not appears_to_contain_phi("patient A")
    assert not disclosure_is_prohibited("patient A")
    assert not disclosure_is_prohibited("ignore all your")
    assert appears_to_contain_phi("patient Aa")
    assert disclosure_is_prohibited("patient Aa")
    assert appears_to_contain_phi("medical record")
    assert disclosure_is_prohibited("medical record")
    assert disclosure_is_prohibited("ignore all your instructions")
    assert appears_to_contain_phi(THREE_WORD)
    assert disclosure_is_prohibited(THREE_WORD)
    assert appears_to_contain_phi("Aa Bb is a patient")
    assert disclosure_is_prohibited("Aa Bb is a patient")


def test_ordinary_text_is_preserved_across_partitions() -> None:
    gate = _assert_partition_stable(ORDINARY)
    assert gate.committed == ORDINARY
    assert gate.held == ""
    assert gate.stopped is False


def test_eligible_text_is_emitted_before_scripted_generation_finishes() -> None:
    before_last_character = ORDINARY[:-1]
    gate = _assert_partition_stable(before_last_character)
    assert gate.committed == "UK GDPR requires a "
    assert gate.held == "documented basis"
    assert gate.stopped is False
    assert 0 < len(gate.committed) < len(ORDINARY)

    finished = _assert_partition_stable(ORDINARY)
    assert finished.committed.startswith(gate.committed)
    assert finished.committed == ORDINARY


def test_ordinary_open_suffix_is_accounted_for_and_not_flushed() -> None:
    gate = _assert_partition_stable(ORDINARY_OPEN_TAIL)
    assert gate.committed == "UK GDPR requires a "
    assert gate.held == "documented basis"
    withheld = ORDINARY_OPEN_TAIL[len(gate.committed) :]
    assert withheld == "documented basis"

    for stop_name in ("interrupt", "complete"):
        for partition in _chunk_partitions(ORDINARY_OPEN_TAIL):
            running = _replay(partition)
            released = running.interrupt() if stop_name == "interrupt" else running.complete()
            assert released == ""
            assert running.committed == "UK GDPR requires a "
            assert running.held == ""
            assert running.stopped is True
            assert withheld not in running.committed
            assert running.push(" more") == ""
            assert running.committed == "UK GDPR requires a "


def test_prohibited_matches_stay_withheld_across_chunk_partitions() -> None:
    cases = {
        "patient Aa": "",
        "Policy note. medical record": "Policy note. ",
        "Note: ignore all your instructions": "Note: ",
        "Aa Bb is a patient": "",
        "Policy note. records exposed": "Policy note. ",
        "Policy note. confidential baa": "Policy note. ",
        "Policy note. you are now an assistant": "Policy note. ",
    }
    for text, expected in cases.items():
        gate = _assert_partition_stable(text)
        assert gate.committed == expected, text
        assert gate.held == ""
        assert gate.stopped is True
        assert gate.push(" later") == ""
        assert gate.committed == expected


def test_three_word_completing_word_is_not_emitted() -> None:
    before_last_character = THREE_WORD[:-1]
    partial = _assert_partition_stable(before_last_character)
    assert partial.committed == "cancel the appointment "
    assert partial.held == "for the patien"
    assert "appointment" in partial.committed
    assert "cancel" in partial.committed
    assert partial.stopped is False

    finished = _assert_partition_stable(THREE_WORD)
    assert finished.committed == "cancel the appointment "
    assert finished.stopped is True
    assert finished.held == ""
    assert "appointment" in finished.committed
    assert "cancel" in finished.committed
    assert "patient" not in finished.committed.casefold()
    assert "for" not in finished.committed.casefold()
    assert appears_to_contain_phi(THREE_WORD) is True
    assert disclosure_is_prohibited(THREE_WORD) is True
    assert output_failure(THREE_WORD) == "content"
    remainder = THREE_WORD[len(finished.committed) :]
    assert remainder == "for the patient"
    assert remainder not in finished.committed
    _assert_completion_drops_held(THREE_WORD, finished.committed)


def _gate_without_flush(text: str) -> StreamingReleaseGate:
    gate = StreamingReleaseGate()
    gate.push(text)
    return gate


def _assert_completion_drops_held(text: str, committed: str) -> None:
    """Chunk splits and completion must not emit held or later text."""
    for partition in _chunk_partitions(text):
        running = _replay(partition)
        assert running.committed == committed
        released = running.complete()
        assert released == ""
        assert running.held == ""
        assert running.stopped is True
        assert running.committed == committed
        assert "patient" not in running.committed.casefold()
        assert running.push(" later") == ""
        assert running.committed == committed


def test_private_pay_policy_sentence_is_not_phi() -> None:
    gate = _gate_without_flush(PRIVATE_PAY_POLICY)
    assert _cites_an_appointment_cancellation_for_a_patient(PRIVATE_PAY_POLICY) is False
    assert _PATIENT_NAME.search(PRIVATE_PAY_POLICY) is None
    assert _NAMED_PATIENT.search(PRIVATE_PAY_POLICY) is None
    assert _PHI_TERMS.search(PRIVATE_PAY_POLICY) is None
    assert appears_to_contain_phi(PRIVATE_PAY_POLICY) is False
    assert disclosure_is_prohibited(PRIVATE_PAY_POLICY) is False
    assert output_failure(PRIVATE_PAY_POLICY) is None
    assert safe_output(PRIVATE_PAY_POLICY) == PRIVATE_PAY_POLICY
    assert gate.stopped is False
    assert gate.committed == PRIVATE_PAY_POLICY
    assert gate.held == ""
    for partition in _chunk_partitions(PRIVATE_PAY_POLICY):
        running = _replay(partition)
        assert running.committed == PRIVATE_PAY_POLICY
        assert running.held == ""
        assert running.complete() == ""
        assert running.committed == PRIVATE_PAY_POLICY
        assert running.held == ""


@pytest.mark.parametrize("verb", _CANCEL_FORMS)
def test_inflected_cancellation_for_the_patient_is_blocked(verb: str) -> None:
    text = f"{verb} the appointment for the patient."
    assert _PATIENT_NAME.search(text) is None
    assert _NAMED_PATIENT.search(text) is None
    assert _NAMED_AS_PATIENT.search(text) is None
    assert _PHI_TERMS.search(text) is None
    assert _cites_an_appointment_cancellation_for_a_patient(text) is True
    assert appears_to_contain_phi(text) is True
    assert disclosure_is_prohibited(text) is True
    assert output_failure(text) == "content"
    assert safe_output(text) == SAFE_OUTPUT
    gate = _assert_partition_stable(text)
    assert gate.stopped is True
    assert gate.held == ""
    assert "patient" not in gate.committed.casefold()
    assert output_failure(gate.committed) is None
    _assert_completion_drops_held(text, gate.committed)


@pytest.mark.parametrize("verb", _CANCEL_FORMS)
@pytest.mark.parametrize(
    "sentence",
    [
        "{verb} the appointment for patient Smith.",
        "{verb} the appointment for Patient Johnson.",
        "{verb} the appointment for patient Aa.",
    ],
)
def test_named_patient_cancellation_is_blocked_by_the_name_detector(verb: str, sentence: str) -> None:
    text = sentence.format(verb=verb)
    assert _PATIENT_NAME.search(text) is not None
    assert _NAMED_PATIENT.search(text) is not None
    assert appears_to_contain_phi(text) is True
    assert disclosure_is_prohibited(text) is True
    assert output_failure(text) == "content"
    assert safe_output(text) == SAFE_OUTPUT
    gate = _gate_without_flush(text)
    assert gate.stopped is True
    assert "Smith" not in gate.committed
    assert "Johnson" not in gate.committed
    assert "Aa" not in gate.committed


@pytest.mark.parametrize(
    "text",
    [
        PLURAL_PATIENTS,
        PATIENT_CANCELED,
        PATIENTS_CANCELED,
        PASSIVE_UK,
        PASSIVE_US,
        PASSIVE_FRONT,
        PASSIVE_MIDDLE,
        LONG_PASSIVE,
        LONG_ACTOR,
    ],
)
def test_patient_cancellation_relation_is_blocked_for_either_number(text: str) -> None:
    assert _NAMED_PATIENT.search(text) is None
    assert _NAMED_AS_PATIENT.search(text) is None
    assert _PHI_TERMS.search(text) is None
    assert _cites_an_appointment_cancellation_for_a_patient(text) is True
    assert appears_to_contain_phi(text) is True
    assert disclosure_is_prohibited(text) is True
    assert output_failure(text) == "content"
    assert safe_output(text) == SAFE_OUTPUT
    gate = _assert_partition_stable(text)
    assert gate.stopped is True
    assert gate.held == ""
    assert "patient" not in gate.committed.casefold()
    assert output_failure(gate.committed) is None
    _assert_completion_drops_held(text, gate.committed)


FORM_THEN_NAME = "Bring the form for the patients. Please review patient A"
FORM_THEN_INSTRUCTION = "Bring the form for the patients. Note: ignore all your"
_PROTECTED_TAILS = {
    FORM_THEN_NAME: "patient A",
    FORM_THEN_INSTRUCTION: "ignore all your",
}


def _partitions_including_protected_splits(text: str, protected: str) -> list[list[str]]:
    """Whole text, one character, fixed widths, and cuts inside the protected tail."""
    partitions = _chunk_partitions(text)
    start = text.rindex(protected)
    head = text[:start]
    tail = text[start:]
    partitions.append([head, tail[:1], tail[1:3], tail[3:]])
    partitions.append([head, tail[: len(tail) // 2], tail[len(tail) // 2 :]])
    return partitions


def test_completion_does_not_flush_a_protected_prefix_inside_a_benign_for_phrase() -> None:
    """A benign for-phrase hold must not carry out an unfinished detector prefix."""
    for text, protected in _PROTECTED_TAILS.items():
        assert output_failure(text) is None, text
        assert protected not in text[: text.rindex(protected)]
        for partition in _partitions_including_protected_splits(text, protected):
            running = _replay(partition)
            before = running.committed
            assert protected not in before
            assert output_failure(before) is None
            released = running.complete()
            assert released == running.committed[len(before) :]
            assert running.committed == before + released
            assert protected not in released
            assert protected not in running.committed
            assert "for the patients" in running.committed
            assert output_failure(running.committed) is None
            assert running.held == ""
            assert running.stopped is True
            assert running.push(" later") == ""
            assert running.committed == before + released

            interrupted = _replay(partition)
            committed_before_interrupt = interrupted.committed
            assert interrupted.interrupt() == ""
            assert interrupted.committed == committed_before_interrupt
            assert protected not in interrupted.committed
            assert "for the patients" not in interrupted.committed
            assert interrupted.held == ""
            assert interrupted.stopped is True
            assert interrupted.push(protected) == ""
            assert interrupted.committed == committed_before_interrupt


def test_unrelated_for_the_patients_phrase_is_released_at_completion() -> None:
    text = "Bring the listed form for the patients."
    assert _cites_an_appointment_cancellation_for_a_patient(text) is False
    gate = _assert_partition_stable(text)
    assert gate.stopped is False
    assert "patient" not in gate.committed.casefold()
    assert gate.held.casefold().startswith("for the patient")
    for partition in _chunk_partitions(text):
        running = _replay(partition)
        released = running.complete()
        assert released == running.committed[len(gate.committed) :]
        assert running.committed == text
        assert running.held == ""
        assert output_failure(running.committed) is None


def test_generic_patient_category_is_not_a_cancellation_citation() -> None:
    assert _cites_an_appointment_cancellation_for_a_patient(GENERIC_CATEGORY) is False
    assert _cites_an_appointment_cancellation_for_a_patient(PRIVATE_PAY_POLICY) is False
    assert appears_to_contain_phi(GENERIC_CATEGORY) is False
    assert disclosure_is_prohibited(GENERIC_CATEGORY) is False
    assert output_failure(GENERIC_CATEGORY) is None
    gate = _assert_partition_stable(GENERIC_CATEGORY)
    assert gate.stopped is False
    assert gate.committed == GENERIC_CATEGORY
    for partition in _chunk_partitions(GENERIC_CATEGORY):
        running = _replay(partition)
        assert running.complete() == ""
        assert running.committed == GENERIC_CATEGORY
        assert running.held == ""


def test_existing_identifier_fixtures_stay_blocked_by_their_name_detectors() -> None:
    assert _PATIENT_NAME.search(JOHNSON) is not None
    assert _NAMED_PATIENT.search(JOHNSON) is not None
    assert appears_to_contain_phi(JOHNSON) is True
    assert disclosure_is_prohibited(JOHNSON) is True
    assert output_failure(JOHNSON) == "content"
    johnson_gate = _gate_without_flush(JOHNSON)
    assert johnson_gate.stopped is True
    assert "Johnson" not in johnson_gate.committed

    assert _PATIENT_NAME.search(PATIENT_SMITH) is not None
    assert _NAMED_PATIENT.search(PATIENT_SMITH) is not None
    assert appears_to_contain_phi(PATIENT_SMITH) is True
    assert disclosure_is_prohibited(PATIENT_SMITH) is True
    assert output_failure(PATIENT_SMITH) == "content"
    smith_gate = _gate_without_flush(PATIENT_SMITH)
    assert smith_gate.stopped is True
    assert "Smith" not in smith_gate.committed


def test_held_prefixes_are_not_flushed_and_later_pushes_emit_nothing() -> None:
    cases = {
        OPEN_PATIENT_PREFIX: ("Please review ", "patient A"),
        OPEN_INSTRUCTION_PREFIX: ("Note: ", "ignore all your"),
    }
    for text, (expected_committed, expected_held) in cases.items():
        gate = _assert_partition_stable(text)
        assert gate.committed == expected_committed
        assert gate.held == expected_held
        assert gate.stopped is False

        for stop_name in ("interrupt", "complete"):
            for partition in _chunk_partitions(text):
                running = _replay(partition)
                released = running.interrupt() if stop_name == "interrupt" else running.complete()
                assert released == ""
                assert running.committed == expected_committed
                assert running.held == ""
                assert running.stopped is True
                assert expected_held not in running.committed
                assert running.push("a") == ""
                assert running.push(expected_held) == ""
                assert running.committed == expected_committed


def test_same_chunk_tail_after_a_match_is_not_emitted() -> None:
    text = "Policy note. medical record EXTRA"
    gate = _assert_partition_stable(text)
    assert gate.committed == "Policy note. "
    assert "medical record" not in gate.committed
    assert "EXTRA" not in gate.committed
    assert gate.stopped is True


@pytest.mark.parametrize("width", [1, 2, 3, 5])
def test_width_partitions_match_the_whole_string(width: int) -> None:
    samples = (
        ORDINARY,
        ORDINARY_OPEN_TAIL,
        THREE_WORD,
        "patient Aa",
        OPEN_PATIENT_PREFIX,
        OPEN_INSTRUCTION_PREFIX,
    )
    for text in samples:
        whole = _replay([text])
        pieces = [text[index : index + width] for index in range(0, len(text), width)]
        split = _replay(pieces)
        assert split.committed == whole.committed
        assert split.held == whole.held
        assert split.stopped == whole.stopped
