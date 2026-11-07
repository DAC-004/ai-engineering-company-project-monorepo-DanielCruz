"""Content stages cannot complete below threshold; retries use a new bank."""

from __future__ import annotations

from tests.pipelines.onboarding_helpers import (
    ACTORS,
    complete_paperwork,
    make_runtime,
    start_three,
    submit_answers,
)


def _advance_to_stage(runtime, record, actor, stage: int):
    current = complete_paperwork(runtime, record) if record["current_stage"] == 1 else record
    while current["current_stage"] < stage:
        current = submit_answers(runtime, current, actor)
        if current["pending_kind"] != "check":
            break
    return current


def test_failed_company_check_does_not_complete_and_changes_bank(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    austin = complete_paperwork(runtime, start_three(runtime)["onb-austin"])
    first_bank = austin["active_bank"]["2"]
    failed = submit_answers(runtime, austin, ACTORS["hire_austin"], wrong=True)
    assert failed["company_passed"] is False
    assert failed["current_stage"] == 2
    assert failed["last_score"] == 0
    assert failed["missed_topics"]
    assert failed["active_bank"]["2"] != first_bank
    notices = runtime.store.read()["notices"]
    assert notices == []


def test_second_failed_non_compliance_check_notifies_manager(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    austin = complete_paperwork(runtime, start_three(runtime)["onb-austin"])
    failed = submit_answers(runtime, austin, ACTORS["hire_austin"], wrong=True)
    failed = submit_answers(runtime, failed, ACTORS["hire_austin"], wrong=True)
    assert failed["attempt_counts"]["2"] == 2
    assert failed["current_stage"] == 2
    notices = runtime.store.read()["notices"]
    assert any(item["recipient"] == "manager" and item["kind"] == "check_failure" for item in notices)


def test_compliance_requires_one_hundred_percent(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    london = start_three(runtime)["onb-london"]
    current = _advance_to_stage(runtime, london, ACTORS["hire_london"], 4)
    assert current["current_stage"] == 4
    from agents.onboarding_orchestrator.checks import questions_for

    bank = current["active_bank"]["4"]
    questions = questions_for(4, framework="uk_gdpr", role_key="revenue_cycle_analyst", bank=bank)
    answers = [int(item["answer"]) for item in questions]
    answers[0] = (answers[0] + 1) % len(questions[0]["choices"])
    failed = runtime.apply_event(
        current["onboarding_id"],
        {"type": "submit_check", "answers": answers, "decision_nonce": current["decision_nonce"]},
        ACTORS["hire_london"],
    )
    assert failed["compliance_check_passed"] is False
    assert failed["last_score"] == 0.8
    assert failed["current_stage"] == 4
    assert failed["pending_kind"] == "check"


def test_second_failed_compliance_notifies_claire(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    austin = start_three(runtime)["onb-austin"]
    current = _advance_to_stage(runtime, austin, ACTORS["hire_austin"], 4)
    failed = submit_answers(runtime, current, ACTORS["hire_austin"], wrong=True)
    failed = submit_answers(runtime, failed, ACTORS["hire_austin"], wrong=True)
    assert failed["attempt_counts"]["4"] == 2
    notices = runtime.store.read()["notices"]
    assert any(item["recipient"] == "claire" for item in notices)
