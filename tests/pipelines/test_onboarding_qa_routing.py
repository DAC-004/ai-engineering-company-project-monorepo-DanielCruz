"""Official-material answers cite a document; uncovered questions are routed."""

from __future__ import annotations

from tests.pipelines.onboarding_helpers import ACTORS, make_runtime, start_three


def test_grounded_question_cites_official_company_document(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    start_three(runtime)
    result = runtime.ask(
        "onb-austin",
        "In which year was HealthCore founded in Austin Texas and how many clinics are in the network?",
        ACTORS["hire_austin"]["user_id"],
    )
    assert result["covered"] is True
    assert result["source_document"] == "stage-02-the-company"
    assert "2011" in result["answer"]
    assert result["route_to"] is None


def test_uncovered_compliance_question_routes_to_claire(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    start_three(runtime)
    result = runtime.ask(
        "onb-austin",
        "Does HIPAA let me take a clinic laptop home over the weekend without a BAA?",
        ACTORS["hire_austin"]["user_id"],
    )
    assert result["covered"] is False
    assert result["route_to"] == "claire"
    assert "not covered" in result["answer"].lower()
    notices = runtime.store.read()["notices"]
    assert any(item["recipient"] == "claire" and item["kind"] == "uncovered_question" for item in notices)


def test_uncovered_non_compliance_question_routes_to_diane(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    start_three(runtime)
    result = runtime.ask(
        "onb-london",
        "Where is the staff cafeteria and what time does the shuttle leave?",
        ACTORS["hire_london"]["user_id"],
    )
    assert result["covered"] is False
    assert result["route_to"] == "diane"
    assert "invented" in result["answer"].lower()


def test_unsupported_fine_amount_is_not_covered_by_lexical_overlap(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    start_three(runtime)
    result = runtime.ask(
        "onb-austin",
        "What HIPAA compliance breach fine amount applies at HealthCore?",
        ACTORS["hire_austin"]["user_id"],
    )
    assert result["covered"] is False
    assert result["route_to"] == "claire"


def test_london_hire_sees_uk_notification_window_not_us(tmp_path) -> None:
    runtime = make_runtime(tmp_path)
    start_three(runtime)
    london = runtime.ask(
        "onb-london",
        "What is the incident notification window?",
        ACTORS["hire_london"]["user_id"],
    )
    assert london["covered"] is True
    assert london["source_document"] == "stage-04-compliance-uk-gdpr"
    assert "72" in london["answer"]
    assert "60 days" not in london["answer"]
    austin = runtime.ask(
        "onb-austin",
        "What is the incident notification window?",
        ACTORS["hire_austin"]["user_id"],
    )
    assert austin["source_document"] == "stage-04-compliance-hipaa"
    assert "60 days" in austin["answer"]


def test_unscoped_notification_question_does_not_pick_a_conflicting_window() -> None:
    from agents.onboarding_orchestrator.qa import answer_question

    result = answer_question("What is the incident notification window?")
    assert result.covered is False
    assert result.route_to == "claire"
