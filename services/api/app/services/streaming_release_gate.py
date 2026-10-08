"""Release generated text only after it leaves every existing detector prefix.

The gate does not define a new PHI or disclosure rule. Completed matches still
come from ``appears_to_contain_phi`` and ``disclosure_is_prohibited``. Those
functions return false for an unfinished pattern, so a false result is not
permission to emit the current suffix.

``committed`` is text that has left every proper-prefix family. ``held`` is
the longest suffix that could still grow into an existing pattern. Characters
move from ``held`` to ``committed`` during ``push``. ``interrupt`` drops
``held``. ``complete`` may release a benign "for the/a patient(s)" hold, but
only the part that is not also an unfinished name or instruction prefix.
Later ``push`` calls emit nothing. Flushing ``patient A`` or
``ignore all your`` would publish text the boolean detectors have not
accepted and have not rejected.
"""

from __future__ import annotations

import re

from app.agent.guardrails.text_rules import (
    _BREACH_DETAIL,
    _CONFIDENTIAL_CONTRACT,
    _INSTRUCTION,
    _NAMED_PATIENT,
    disclosure_is_prohibited,
)
from app.agent.memory_policy import (
    _FOR_PATIENT,
    _NAMED_AS_PATIENT,
    _PATIENT_NAME,
    _PHI_TERMS,
    _cites_an_appointment_cancellation_for_a_patient,
    appears_to_contain_phi,
)

# Expansions of the imported patterns. A test checks that each phrase is a
# match of one of those patterns so this list cannot become a second policy.
_FIXED_PHRASES: tuple[str, ...] = (
    "medical record",
    "mrn",
    "date of birth",
    "dob",
    "diagnosis",
    "diagnosed",
    "insurance number",
    "nhs number",
    "national insurance",
    "lab result",
    "lab results",
    "clinical note",
    "clinical notes",
    "member identifier",
    "you are now an assistant",
    "forget that you work",
    "no compliance rules",
    "act as an assistant with no",
    "act as if you had no rules",
    "records exposed",
    "records were exposed",
    "records are exposed",
    "records have been exposed",
    "records had been exposed",
    "breach was discovered",
    "discovery time",
    "under investigation",
    "compliance_breach",
    "how many records",
    "when was it discovered",
    "when was the breach discovered",
    "confidential baa",
    "confidential dpa",
    "business associate agreement fee",
    "business associate agreement term",
    "business associate agreement price",
    "data processing agreement fee",
    "data processing agreement term",
    "data processing agreement price",
)
_PATTERN_SOURCES: tuple[re.Pattern[str], ...] = (
    _PHI_TERMS,
    _INSTRUCTION,
    _BREACH_DETAIL,
    _CONFIDENTIAL_CONTRACT,
)
_CONJUNCTION_WORDS: tuple[str, ...] = ("appointment", "cancel", "patient")
_REPEAT_WORDS: tuple[str, ...] = ("all", "your", "previous")
_INSTRUCTIONS_WORD = "instructions"
_WORD_CHAR = re.compile(r"\w")


def _is_word_char(character: str) -> bool:
    return bool(_WORD_CHAR.search(character))


def _is_ascii_letter(character: str) -> bool:
    return len(character) == 1 and ("A" <= character <= "Z" or "a" <= character <= "z")


def _starts_at_word_boundary(text: str, start: int) -> bool:
    """Mirror regex ``\\b`` using the same word-character class as the detectors."""
    if start <= 0:
        return True
    if start >= len(text):
        return False
    return _is_word_char(text[start - 1]) != _is_word_char(text[start])


def _consume_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _read_name_word(text: str, start: int) -> int:
    """Advance over ``[A-Za-z][A-Za-z'-]*`` without requiring the second character.

    The completed name patterns require two characters. A one-character word
    can still grow, so it remains an open prefix until whitespace or another
    non-name character ends it.
    """
    if start >= len(text) or not _is_ascii_letter(text[start]):
        return start
    index = start + 1
    while index < len(text) and (_is_ascii_letter(text[index]) or text[index] in "'-"):
        index += 1
    return index


def _fixed_phrase_suffix_is_open(suffix: str) -> bool:
    folded = suffix.casefold()
    # Casefold can change length for a few non-ASCII characters. The detector
    # phrases are ASCII; skip a suffix whose length would not map back.
    if len(folded) != len(suffix):
        return False
    for phrase in _FIXED_PHRASES:
        phrase_folded = phrase.casefold()
        if folded and len(folded) < len(phrase_folded) and phrase_folded.startswith(folded):
            return True
    return False


def _patient_name_suffix_is_open(suffix: str) -> bool:
    """Proper prefix of ``patients?`` plus whitespace and at most one name character.

    The second name character completes ``_PATIENT_NAME`` or ``_NAMED_PATIENT``
    when a boundary is present. That character is handled by the detector abort
    before this function sees it.
    """
    folded = suffix.casefold()
    for stem in ("patients", "patient"):
        if len(folded) <= len(stem) and stem.startswith(folded):
            return True
        if not folded.startswith(stem):
            continue
        rest = suffix[len(stem) :]
        if not rest:
            return True
        if not rest[0].isspace():
            return False
        index = _consume_whitespace(rest, 0)
        if index == len(rest):
            return True
        return index == len(rest) - 1 and _is_ascii_letter(rest[index])
    return False


def _match_keyword_prefix(text: str, index: int, keyword: str) -> int | None:
    """Return the end index of a keyword prefix, or None when the text diverges."""
    folded = text.casefold()
    target = keyword.casefold()
    if index >= len(folded):
        return None
    position = 0
    while index + position < len(folded) and position < len(target):
        if folded[index + position] != target[position]:
            return None
        position += 1
    if position == 0:
        return None
    if position < len(target) and index + position != len(folded):
        return None
    return index + position


def _role_tail_is_open(rest: str) -> bool:
    """Proper prefix of ``\\s+is\\s+a\\s+patient`` after two name words.

    The completed role is not open. The detector already returns true for it,
    and treating it as held would make a later flush eligible.
    """
    if not rest or not rest[0].isspace():
        return False
    index = _consume_whitespace(rest, 0)
    if index == len(rest):
        return True
    after_is = _match_keyword_prefix(rest, index, "is")
    if after_is is None:
        return False
    if after_is == len(rest):
        return True
    if not rest[after_is].isspace():
        return False
    index = _consume_whitespace(rest, after_is)
    if index == len(rest):
        return True
    after_a = _match_keyword_prefix(rest, index, "a")
    if after_a is None:
        return False
    if after_a == len(rest):
        return True
    if not rest[after_a].isspace():
        return False
    index = _consume_whitespace(rest, after_a)
    if index == len(rest):
        return True
    after_patient = _match_keyword_prefix(rest, index, "patient")
    if after_patient is None:
        return False
    # The full word completes the existing named-as-patient pattern.
    if after_patient - index == len("patient"):
        return False
    return after_patient == len(rest)


def _named_as_patient_suffix_is_open(suffix: str) -> bool:
    """One open name word, two name words, or those words plus an open role prefix.

    A one-letter word already ended by whitespace can never satisfy
    ``[A-Za-z][A-Za-z'-]+``, so it is not kept open.
    """
    if not suffix or not _is_ascii_letter(suffix[0]):
        return False
    after_first = _read_name_word(suffix, 0)
    if after_first == len(suffix):
        return True
    if not suffix[after_first].isspace() or after_first < 2:
        return False
    index = _consume_whitespace(suffix, after_first)
    if index == len(suffix):
        return True
    if not _is_ascii_letter(suffix[index]):
        return False
    second_start = index
    after_second = _read_name_word(suffix, index)
    if after_second == len(suffix):
        return True
    if after_second - second_start < 2 or not suffix[after_second].isspace():
        return False
    return _role_tail_is_open(suffix[after_second:])


def _conjunction_prefix_is_open(suffix: str) -> bool:
    """Proper prefix of appointment, cancel, or patient.

    The existing check is substring containment. Holding only a proper prefix
    lets the word that completes the three-way condition abort instead of emit.
    The finished word ``patient`` stays with the patient-name family; it is not
    a proper prefix of itself.
    """
    folded = suffix.casefold()
    return any(word.startswith(folded) and len(folded) < len(word) for word in _CONJUNCTION_WORDS)


def _ignore_tail_is_open(tail: str) -> bool:
    """Text after the single space that follows ``ignore`` in ``_INSTRUCTION``."""
    if tail == "":
        return True
    folded = tail.casefold()
    if not folded[0].isascii() or not folded[0].isalpha():
        return False
    index = 1
    while index < len(folded) and folded[index].isascii() and folded[index].isalpha():
        index += 1
    word = folded[:index]
    at_end = index == len(folded)
    if at_end:
        if word == _INSTRUCTIONS_WORD:
            return False
        if word in _REPEAT_WORDS or any(repeat.startswith(word) for repeat in _REPEAT_WORDS):
            return True
        return _INSTRUCTIONS_WORD.startswith(word)
    if word not in _REPEAT_WORDS:
        return False
    if not folded[index].isspace():
        return False
    index = _consume_whitespace(folded, index)
    if index == len(folded):
        return True
    return _ignore_tail_is_open(tail[index:])


def _ignore_suffix_is_open(suffix: str) -> bool:
    """Proper prefix of ``ignore (?:(?:all|your|previous)\\s+)*instructions``.

    The compiled pattern has no leading word boundary and uses one literal
    space after ``ignore``. A completed ``instructions`` ending is not open.
    """
    folded = suffix.casefold()
    if not folded:
        return False
    if "ignore".startswith(folded) and len(folded) < len("ignore"):
        return True
    if not folded.startswith("ignore"):
        return False
    rest = suffix[len("ignore") :]
    if rest == "":
        return True
    if not rest.startswith(" "):
        return False
    return _ignore_tail_is_open(rest[1:])


def _suffix_is_open(text: str, start: int) -> bool:
    suffix = text[start:]
    if not suffix:
        return False
    bounded = _starts_at_word_boundary(text, start)
    if bounded and (
        _fixed_phrase_suffix_is_open(suffix)
        or _patient_name_suffix_is_open(suffix)
        or _named_as_patient_suffix_is_open(suffix)
        or _conjunction_prefix_is_open(suffix)
    ):
        return True
    # ``_INSTRUCTION`` searches for "ignore" without a leading word boundary.
    return _ignore_suffix_is_open(suffix)


def _text_is_prohibited(text: str) -> bool:
    return appears_to_contain_phi(text) or disclosure_is_prohibited(text)


def _trailing_patient_may_be_plural(text: str) -> bool:
    """Hold a final "patient" only when the next letter can remove the match.

    End of the current buffer is a word boundary, so a pattern can match
    "patient" before an "s" arrives. This does not decide that plural wording
    is policy text. If the plural spelling is still prohibited, the gate stops.
    """
    if not text.casefold().endswith("patient"):
        return False
    if (
        _PATIENT_NAME.search(text)
        or _NAMED_AS_PATIENT.search(text)
        or _NAMED_PATIENT.search(text)
        or _PHI_TERMS.search(text)
    ):
        return False
    if not _text_is_prohibited(text):
        return False
    return not _text_is_prohibited(text + "s")


_FOR_PATIENT_PREFIXES = (
    "for the patients",
    "for the patient",
    "for a patients",
    "for a patient",
    "for patients",
    "for patient",
)


def _open_cancellation_tie_length(text: str) -> int:
    """Hold "for the/a patient(s)" from its first character until it is decided.

    An unfinished "for the pat" is a proper prefix, so "for" is not emitted
    before the noun is known. A finished phrase stays held while appointment
    or the action word can still arrive. ``complete`` releases that hold when
    the finished text is not a cancellation match.
    """
    if not text:
        return 0
    lowered = text.casefold()
    if _cites_an_appointment_cancellation_for_a_patient(text):
        return 0
    match = re.search(_FOR_PATIENT, lowered)
    if match is not None:
        return len(text) - match.start()
    best = 0
    for start in range(len(lowered)):
        if start and (lowered[start - 1].isalnum() or lowered[start - 1] == "_"):
            continue
        suffix = lowered[start:]
        if any(phrase.startswith(suffix) for phrase in _FOR_PATIENT_PREFIXES):
            best = max(best, len(text) - start)
    return best


def open_suffix_length(text: str) -> int:
    """Length of the longest suffix that is still a proper prefix of a pattern."""
    if not text:
        return 0
    longest = _open_cancellation_tie_length(text)
    for start in range(len(text)):
        if _suffix_is_open(text, start):
            return max(longest, len(text) - start)
    return longest


def _protected_open_suffix_length(text: str) -> int:
    """Length of an unfinished detector prefix, excluding the cancellation hold.

    ``complete`` may release a benign for-phrase. That release must stop
    before a later open name or instruction prefix, because those prefixes
    are not prohibited until another character arrives.
    """
    if not text:
        return 0
    for start in range(len(text)):
        if _suffix_is_open(text, start):
            return len(text) - start
    return 0


class StreamingReleaseGate:
    """Character-wise release gate for one generated answer.

    Processing each character inside ``push`` keeps every chunk partition of
    the same input on the same committed text. A chunk-level boolean check
    would emit a completed match that happened to fall inside one chunk and
    withhold that same match when it was split.
    """

    def __init__(self) -> None:
        self.committed = ""
        self.held = ""
        self.stopped = False

    def push(self, chunk: str) -> str:
        """Emit the portion of ``chunk`` that left every open prefix.

        Returns an empty string once the gate has stopped. A prohibited match
        clears ``held`` and stops before the completing character is emitted.
        """
        if self.stopped or not chunk:
            return ""
        emitted: list[str] = []
        for character in chunk:
            if self.stopped:
                break
            candidate = self.committed + self.held + character
            if _text_is_prohibited(candidate) and not _trailing_patient_may_be_plural(candidate):
                # The open prefix is the start of the match. Drop it with the
                # completing character. Do not unsend text already committed.
                self.held = ""
                self.stopped = True
                break
            self.held += character
            emitted.append(self._release_closed_prefix())
        return "".join(emitted)

    def interrupt(self) -> str:
        """Stop because generation was interrupted. Do not flush ``held``."""
        return self._terminate()

    def complete(self) -> str:
        """Stop because generation ended.

        Name and instruction prefixes stay dropped. An unresolved
        "for the/a patient(s)" phrase is released when the finished text is
        not a cancellation match, so ordinary wording is not truncated.
        A protected prefix inside that hold is not part of the release.
        """
        if self.stopped or not self.held:
            return self._terminate()
        combined = self.committed + self.held
        if _text_is_prohibited(combined):
            return self._terminate()
        if _open_cancellation_tie_length(combined) != len(self.held):
            return self._terminate()
        protected = _protected_open_suffix_length(combined)
        if protected > len(self.held):
            # The unfinished prefix began in text already committed. Do not
            # extend it by flushing the cancellation hold.
            return self._terminate()
        released = self.held if protected == 0 else self.held[:-protected]
        if released and _text_is_prohibited(self.committed + released):
            return self._terminate()
        self.held = ""
        self.committed += released
        self.stopped = True
        return released

    def _terminate(self) -> str:
        self.held = ""
        self.stopped = True
        return ""

    def _release_closed_prefix(self) -> str:
        suffix_length = open_suffix_length(self.held)
        if suffix_length <= 0:
            released = self.held
            self.held = ""
        elif suffix_length >= len(self.held):
            released = ""
        else:
            released = self.held[:-suffix_length]
            self.held = self.held[-suffix_length:]
        self.committed += released
        return released
