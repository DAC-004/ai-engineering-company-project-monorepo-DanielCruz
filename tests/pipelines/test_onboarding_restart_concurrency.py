"""Restart resume and isolated parallel onboardings. Does not prove UI rendering."""

from __future__ import annotations

import threading
from datetime import date

from tests.pipelines.onboarding_helpers import (
    ACTORS,
    USER_IDS,
    complete_paperwork,
    make_runtime,
    start_three,
    submit_answers,
)
from agents.onboarding_orchestrator.seed import onboarding_specs


def test_three_fictional_onboardings_exist(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    started = start_three(runtime)
    assert set(started) == {"onb-austin", "onb-london", "onb-early"}
    assert started["onb-austin"]["office"] == "Austin"
    assert started["onb-london"]["office"] == "London"
    assert started["onb-austin"]["manager_user_id"] != started["onb-london"]["manager_user_id"]
    assert started["onb-austin"]["claire_user_id"] == started["onb-london"]["claire_user_id"]


def test_restart_resumes_same_stage_pending_and_attempts(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    austin = start_three(runtime)["onb-austin"]
    after_paper = complete_paperwork(runtime, austin)
    failed = submit_answers(runtime, after_paper, ACTORS["hire_austin"], wrong=True)
    assert failed["current_stage"] == 2
    assert failed["attempt_counts"]["2"] == 1
    assert failed["pending_kind"] == "check"
    nonce = failed["decision_nonce"]
    checkpoint = str(runtime.paths.checkpoint)

    resumed = make_runtime(tmp_path)
    assert str(resumed.paths.checkpoint) == checkpoint
    values = resumed.checkpoint_values("onb-austin")
    record = resumed.current("onb-austin")
    assert values["current_stage"] == 2
    assert values["attempt_counts"]["2"] == 1
    assert values["pending_kind"] == "check"
    assert record["decision_nonce"] == nonce
    passed = submit_answers(resumed, record, ACTORS["hire_austin"])
    assert passed["current_stage"] == 3
    assert passed["company_passed"] is True


def test_parallel_onboardings_do_not_share_state(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    started = start_three(runtime)
    austin = complete_paperwork(runtime, started["onb-austin"])
    london = started["onb-london"]
    austin = submit_answers(runtime, austin, ACTORS["hire_austin"])
    assert austin["current_stage"] == 3
    assert runtime.current("onb-london")["current_stage"] == 1
    assert runtime.current("onb-london")["pending_kind"] == "paperwork"
    london = complete_paperwork(runtime, london)
    assert london["current_stage"] == 2
    assert runtime.current("onb-austin")["current_stage"] == 3


def test_duplicate_start_returns_the_existing_thread(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    first = start_three(runtime)["onb-austin"]
    second = runtime.start(onboarding_specs(USER_IDS, date(2026, 11, 9))[0])
    assert second["onboarding_id"] == first["onboarding_id"]
    assert second["decision_nonce"] == first["decision_nonce"]
    assert second["pending_kind"] == "paperwork"
    assert len(runtime.store.list_all()) == 3


def test_two_threads_do_not_drop_projection_rows(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def write_row(onboarding_id: str) -> None:
        try:
            barrier.wait(timeout=5)
            runtime.store.upsert_onboarding(
                {
                    "onboarding_id": onboarding_id,
                    "display_name": onboarding_id,
                    "office": "Austin",
                    "framework": "hipaa",
                    "role_key": "digital_engineer",
                    "department_id": "technology",
                }
            )
        except BaseException as error:  # noqa: BLE001 - collect any worker failure
            errors.append(error)

    workers = [
        threading.Thread(target=write_row, args=("race-a",)),
        threading.Thread(target=write_row, args=("race-b",)),
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
    assert errors == []
    stored = runtime.store.read()["onboardings"]
    assert set(stored) >= {"race-a", "race-b"}


def test_concurrent_starts_keep_separate_checkpoint_threads(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    specs = onboarding_specs(USER_IDS, date(2026, 11, 9))[:2]
    barrier = threading.Barrier(2)
    results: dict[str, dict] = {}
    errors: list[BaseException] = []

    def start_one(spec: dict) -> None:
        try:
            barrier.wait(timeout=5)
            results[spec["onboarding_id"]] = runtime.start(spec)
        except BaseException as error:  # noqa: BLE001 - collect any worker failure
            errors.append(error)

    workers = [threading.Thread(target=start_one, args=(spec,)) for spec in specs]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)
    assert errors == []
    assert results["onb-austin"]["office"] == "Austin"
    assert results["onb-london"]["office"] == "London"
    assert runtime.current("onb-austin")["pending_kind"] == "paperwork"
    assert runtime.current("onb-london")["pending_kind"] == "paperwork"
