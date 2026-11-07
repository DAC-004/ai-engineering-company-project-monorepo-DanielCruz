"""Human gates stay interrupted until the assigned identity decides."""

from __future__ import annotations

import pytest

from agents.onboarding_orchestrator.runtime import OnboardingError
from tests.pipelines.onboarding_helpers import (
    ACTORS,
    complete_paperwork,
    decide,
    make_runtime,
    start_three,
    submit_answers,
)


def _to_compliance_approval(runtime):
    record = complete_paperwork(runtime, start_three(runtime)["onb-austin"])
    for _ in range(3):
        record = submit_answers(runtime, record, ACTORS["hire_austin"])
    assert record["pending_kind"] == "compliance_approval"
    return record


def test_wrong_identity_cannot_close_a_gate(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    record = _to_compliance_approval(runtime)
    with pytest.raises(OnboardingError) as error:
        decide(runtime, record, ACTORS["admin_other"], "approve")
    assert error.value.code == "unauthorized_approver"
    assert runtime.current("onb-austin")["pending_kind"] == "compliance_approval"
    with pytest.raises(OnboardingError) as error:
        decide(runtime, record, ACTORS["manager_digital"], "approve")
    assert error.value.code == "unauthorized_approver"


def test_stale_nonce_is_rejected(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    record = _to_compliance_approval(runtime)
    with pytest.raises(OnboardingError) as error:
        runtime.apply_event(
            record["onboarding_id"],
            {
                "type": "human_decision",
                "decision": "approve",
                "comment": "",
                "decision_nonce": "not-the-nonce",
            },
            ACTORS["claire"],
        )
    assert error.value.code == "stale_or_duplicate_decision"


def test_claire_approval_advances_and_duplicate_is_rejected(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    record = _to_compliance_approval(runtime)
    approved = decide(runtime, record, ACTORS["claire"], "approve")
    assert approved["compliance_approved"] is True
    assert approved["current_stage"] == 5
    with pytest.raises(OnboardingError):
        decide(runtime, record, ACTORS["claire"], "approve")


def test_rejection_restarts_stage_with_visible_comment(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    record = _to_compliance_approval(runtime)
    rejected = decide(runtime, record, ACTORS["claire"], "reject", "Repeat the logging section")
    assert rejected["compliance_approved"] is False
    assert rejected["compliance_check_passed"] is False
    assert rejected["current_stage"] == 4
    assert rejected["pending_kind"] == "check"
    assert rejected["last_rejection_comment"] == "Repeat the logging section"
    view = runtime.hire_view("onb-austin", ACTORS["hire_austin"]["user_id"])
    assert view["last_rejection_comment"] == "Repeat the logging section"


def test_employee_role_cannot_approve_compliance_even_with_claire_identity(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    record = _to_compliance_approval(runtime)
    employee_claire = {**ACTORS["claire"], "role": "employee"}
    with pytest.raises(OnboardingError) as error:
        decide(runtime, record, employee_claire, "approve")
    assert error.value.code == "unauthorized_approver"
    assert runtime.current("onb-austin")["pending_kind"] == "compliance_approval"


def test_wrong_department_manager_cannot_approve_role(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    record = _to_compliance_approval(runtime)
    record = decide(runtime, record, ACTORS["claire"], "approve")
    record = submit_answers(runtime, record, ACTORS["hire_austin"])
    assert record["pending_kind"] == "manager_approval"
    with pytest.raises(OnboardingError) as error:
        decide(runtime, record, ACTORS["manager_revenue"], "approve")
    assert error.value.code == "unauthorized_approver"
    approved = decide(runtime, record, ACTORS["manager_digital"], "approve")
    assert approved["role_approved"] is True
    assert approved["current_stage"] == 6



def test_all_seven_stages_finish_only_after_diane_closure(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    record = _to_compliance_approval(runtime)
    record = decide(runtime, record, ACTORS["claire"], "approve")
    record = submit_answers(runtime, record, ACTORS["hire_austin"])
    record = decide(runtime, record, ACTORS["manager_digital"], "approve")
    assert record["current_stage"] == 6
    record = submit_answers(runtime, record, ACTORS["hire_austin"])
    assert record["current_stage"] == 7
    assert record["pending_kind"] == "closure"
    assert record["status"] != "complete"
    for actor in [ACTORS["hire_austin"], ACTORS["manager_digital"], ACTORS["claire"]]:
        with pytest.raises(OnboardingError) as error:
            decide(runtime, record, actor, "approve")
        assert error.value.code == "unauthorized_approver"
    rejected = decide(runtime, record, ACTORS["diane"], "reject", "Review the access checklist")
    assert rejected["current_stage"] == 7
    assert rejected["status"] == "waiting_human"
    assert runtime.hire_view("onb-austin", ACTORS["hire_austin"]["user_id"])["last_rejection_comment"] == "Review the access checklist"
    completed = decide(runtime, rejected, ACTORS["diane"], "approve")
    assert completed["status"] == "complete"
    assert completed["closure_approved"] is True
    assert completed["compliance_approved"] and completed["role_approved"]
    assert completed["company_passed"] and completed["operations_passed"] and completed["how_we_work_passed"]
