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

from app.agent.guardrails.text_rules import disclosure_is_prohibited  # noqa: E402
from app.agent.memory_policy import appears_to_contain_phi  # noqa: E402
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
    assert partial.committed == "cancel the appointment for "
    assert partial.held == "the patien"
    assert "appointment" in partial.committed
    assert "cancel" in partial.committed
    assert partial.stopped is False

    finished = _assert_partition_stable(THREE_WORD)
    assert finished.committed == "cancel the appointment for "
    assert finished.held == ""
    assert finished.stopped is True
    assert "appointment" in finished.committed
    assert "cancel" in finished.committed
    assert "patient" not in finished.committed.casefold()
    remainder = THREE_WORD[len(finished.committed) :]
    assert remainder == "the patient"
    assert remainder not in finished.committed


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
