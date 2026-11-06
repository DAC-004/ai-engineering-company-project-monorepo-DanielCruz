"""Deterministic comprehension scoring. Content stages require a passing check."""

from __future__ import annotations

from dataclasses import dataclass

from agents.onboarding_orchestrator.content import check_catalog_id, load_checks, presented_content

PASS_THRESHOLD = 0.8
COMPLIANCE_THRESHOLD = 1.0


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    score: float
    threshold: float
    missed_topics: tuple[str, ...]
    missed_ids: tuple[str, ...]
    bank: str
    next_bank: str
    attempt: int
    notify: str | None
    reinforcement: str


def _other_bank(bank: str) -> str:
    return "b" if bank == "a" else "a"


def questions_for(
    stage: int,
    *,
    framework: str,
    role_key: str,
    bank: str,
) -> list[dict]:
    catalog_id = check_catalog_id(stage, framework=framework, role_key=role_key)
    catalog = load_checks()[catalog_id]
    return list(catalog["banks"][bank])


def score_answers(
    stage: int,
    answers: list[int],
    *,
    framework: str,
    role_key: str,
    bank: str,
    prior_attempts: int,
) -> CheckResult:
    catalog_id = check_catalog_id(stage, framework=framework, role_key=role_key)
    catalog = load_checks()[catalog_id]
    questions = catalog["banks"][bank]
    if len(answers) != len(questions):
        raise ValueError("answer_count_mismatch")
    correct = 0
    missed_topics: list[str] = []
    missed_ids: list[str] = []
    for index, question in enumerate(questions):
        if int(answers[index]) == int(question["answer"]):
            correct += 1
        else:
            missed_topics.append(str(question["topic"]))
            missed_ids.append(str(question["id"]))
    score = correct / len(questions)
    threshold = float(catalog["threshold"])
    passed = score + 1e-9 >= threshold
    attempt = prior_attempts + 1
    notify = None
    if not passed and attempt >= 2:
        notify = str(catalog["notify_after_failures"])
    reinforcement = ""
    if not passed:
        material = presented_content(stage, framework=framework, role_key=role_key)
        reinforcement = (
            "Review missed topics from "
            + material["document_id"]
            + ": "
            + ", ".join(missed_topics)
        )
    return CheckResult(
        passed=passed,
        score=score,
        threshold=threshold,
        missed_topics=tuple(missed_topics),
        missed_ids=tuple(missed_ids),
        bank=bank,
        next_bank=bank if passed else _other_bank(bank),
        attempt=attempt,
        notify=notify,
        reinforcement=reinforcement,
    )
