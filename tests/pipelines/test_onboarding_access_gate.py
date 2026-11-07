"""Patient-system access is denied until Claire has approved stage 4."""

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


def test_early_patient_access_is_denied_audited_and_routed_to_claire(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    start_three(runtime)
    with pytest.raises(OnboardingError) as error:
        runtime.request_access("onb-early", "us_ehr", ACTORS["hire_early"]["user_id"])
    assert error.value.code == "patient_system_before_compliance_approval"
    assert runtime.current("onb-early")["current_stage"] == 1
    audit = runtime.audit.lines()
    assert any(item["action"] == "security_early_access_denied" for item in audit)
    assert all(item["actor_type"] == "automated_process" for item in audit)
    notices = runtime.store.read()["notices"]
    assert any(item["recipient"] == "claire" and item["kind"] == "security_event" for item in notices)


def test_passing_compliance_check_alone_does_not_open_patient_access(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    record = complete_paperwork(runtime, start_three(runtime)["onb-austin"])
    for _ in range(3):
        record = submit_answers(runtime, record, ACTORS["hire_austin"])
    assert record["compliance_check_passed"] is True
    assert record["compliance_approved"] is False
    with pytest.raises(OnboardingError) as error:
        runtime.request_access("onb-austin", "us_ehr", ACTORS["hire_austin"]["user_id"])
    assert error.value.code == "patient_system_before_compliance_approval"
    record = decide(runtime, record, ACTORS["claire"], "approve")
    allowed = runtime.request_access("onb-austin", "us_ehr", ACTORS["hire_austin"]["user_id"])
    assert allowed["allowed"] is True
    assert allowed["system_id"] == "us_ehr"
