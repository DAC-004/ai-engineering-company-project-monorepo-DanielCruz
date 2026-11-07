"""Task 4 source-requirement counterexamples; synthetic stores and PDFs only."""
from dataclasses import replace
from datetime import date
from pathlib import Path

from agents.supplier_contracts.actor import ActorIdentity
from agents.supplier_contracts.contracts import run_contracts
from agents.supplier_contracts.pdf import write_pdf
from agents.supplier_contracts.runtime import ContractRuntime
from agents.supplier_contracts.supervisor import Supervisor
from agents.supplier_contracts.types import ContractsRequest, SupervisorRequest

CLAIRE_ACTOR = ActorIdentity(user_id="fixture-claire", role="supervisor", department_id="compliance", email="claire.compliance@healthcore.example", can_approve=True)

def runtime_for(tmp_path):
    runtime = ContractRuntime(raw=tmp_path / "raw", process=tmp_path / "process", as_of=date(2026, 11, 6))
    runtime.ensure_seeded()
    return runtime

def extracted(runtime, supplier_id="HC-S06", contract_id="CT-HC-03"):
    return run_contracts(ContractsRequest(supplier_id=supplier_id, question="terms"), pdf_path=runtime.pdf_path(contract_id), load_date=runtime.load_date)

def write_terms(path, protection, *, expiry=True, annex=False):
    lines = ["1. Parties. HealthCore and a fictional supplier.", "3. Non-renewal notice. Either party must give 90 days' notice before expiry.", "4. Price revision. Annual increases are capped at 3 percent.", "5. Exit. No penalty.", "6. Data protection. " + protection, "8. Estimated annual value. The estimated annual value of this agreement is 121800 GBP."]
    if expiry:lines.insert(1, "2. Term. This agreement expires 210 days after the HealthCore data-load date.")
    write_pdf(path, [lines, ["Signed Business Associate Agreement"]] if annex else [lines])

def test_task4_review_patient_registry_cannot_be_overridden_by_contract(tmp_path):
    runtime = runtime_for(tmp_path)
    write_terms(runtime.pdf_dir / "CT-HC-03.pdf", "This supplier does not process patient data.")
    result = extracted(runtime)
    assert result.processes_patient_data is True
    assert result.missing_dpa is True
    assert result.dpa_status == "uncertain"

def test_task4_review_negated_baa_is_not_signed(tmp_path):
    runtime = runtime_for(tmp_path)
    write_terms(runtime.pdf_dir / "CT-HC-02.pdf", "No signed BAA is annexed to this contract.", annex=True)
    result = extracted(runtime, "HC-S03", "CT-HC-02")
    assert result.missing_dpa is True
    assert result.dpa_status == "uncertain"

def test_task4_review_uk_supplier_baa_is_not_a_signed_dpa(tmp_path):
    runtime = runtime_for(tmp_path)
    write_terms(runtime.pdf_dir / "CT-HC-03.pdf", "A signed BAA is annexed to this contract.", annex=True)
    assert extracted(runtime).missing_dpa is True

def test_task4_review_compliance_proceed_is_bound_to_pdf_revision(tmp_path):
    runtime = runtime_for(tmp_path)
    supervisor = Supervisor(runtime)
    result = extracted(runtime)
    supervisor.confirm_dpa(CLAIRE_ACTOR, "HC-S06")
    assert supervisor._dpa_blocks(result) is False
    assert supervisor._dpa_blocks(replace(result, pdf_sha256="f" * 64)) is True

def test_task4_review_missing_date_drops_stale_calendar(tmp_path):
    runtime = runtime_for(tmp_path)
    assert "HC-S06" in runtime.store.read()["calendars"]
    write_terms(runtime.pdf_dir / "CT-HC-03.pdf", "This contract includes no DPA.", expiry=False)
    runtime.refresh_calendars()
    assert "HC-S06" not in runtime.store.read()["calendars"]
    answer = Supervisor(runtime).handle(SupervisorRequest(kind="question", question="When is the notice deadline?", supplier_id="HC-S06"))
    assert "Expiry or notice deadline was not evidenced" in answer.answer

def test_task4_review_default_runtime_clock_tracks_current_day(tmp_path, monkeypatch):
    from agents.supplier_contracts import runtime as module
    class FakeDate(date):
        current = date(2026, 11, 7)
        @classmethod
        def today(cls):return cls.current
    monkeypatch.setattr(module, "date", FakeDate)
    monkeypatch.delenv("SUPPLIER_CONTRACTS_TODAY", raising=False)
    instance = ContractRuntime(raw=tmp_path/"raw", process=tmp_path/"process")
    assert instance.today == date(2026, 11, 7)
    FakeDate.current = date(2027, 2, 5)
    assert instance.today == date(2027, 2, 5)

def test_task4_review_portfolio_question_lists_missing_agreements(tmp_path):
    response = Supervisor(runtime_for(tmp_path)).handle(SupervisorRequest(kind="question", question="Which suppliers process patient data without a signed data protection agreement?", supplier_id=None))
    assert response.blocked is False
    assert "HC-S06" in response.answer and "HC-S04" in response.answer
    assert response.consultation_count <= 4
    assert any(row["recipient"] == "claire.whitfield" for row in response.alerts)

def test_task4_review_alert_figures_have_source_provenance(tmp_path):
    response = Supervisor(runtime_for(tmp_path)).handle(SupervisorRequest(kind="tick_alerts", question="tick", supplier_id=None))
    assert response.alerts
    for alert in response.alerts:
        if alert["kind"] == "price_increase":assert alert["source_row_ids"]
        if alert["kind"] in {"expiry", "notice"}:
            assert alert["contract_id"] and alert["source_citations"]
            assert all(item["clause"] and item["page"] > 0 and item["pdf_sha256"] for item in alert["source_citations"])

def test_task4_review_brief_retains_prices_impact_and_alternatives(tmp_path):
    def transport(messages):return '{"fact_ids":["approval_required"]}'
    response = Supervisor(runtime_for(tmp_path), transport=transport).handle(SupervisorRequest(kind="brief", question="Prepare a brief to renegotiate with ClearPath Labs.", supplier_id="HC-S03"))
    assert response.blocked is False
    for required in ["previous 18.00", "current 19.26", "37800", "HC-S04", "17.20", "Recommendation"]:assert required in response.answer



def test_task4_review_missing_contract_confirmation_is_explicit_and_snapshot_bound(tmp_path):
    runtime = runtime_for(tmp_path)
    supervisor = Supervisor(runtime)
    result = extracted(runtime, "HC-S04", "no-contract")
    assert result.missing_contract and supervisor._dpa_blocks(result)
    supervisor.confirm_dpa(CLAIRE_ACTOR, "HC-S04")
    assert supervisor._dpa_blocks(result) is False
    changed = replace(result, missing_contract=False, contract_id="new-contract", pdf_sha256="e"*64)
    assert supervisor._dpa_blocks(changed) is True


def test_task4_review_combined_scheduler_preserves_both_task_sweeps(tmp_path):
    import json, os, subprocess, sys
    env = dict(os.environ, SUPPLIER_CONTRACTS_ALERT_INTERVAL_SECONDS="60", ONBOARDING_DEADLINE_SWEEP_INTERVAL_SECONDS="60", CELERY_TASK_ALWAYS_EAGER="1")
    code = 'import json; from app.celery_app import celery_app; print(json.dumps({"imports": list(celery_app.conf.imports), "schedule": list(celery_app.conf.beat_schedule)}))'
    got = subprocess.run([sys.executable,"-B","-c",code],cwd=tmp_path,env=env,capture_output=True,text=True,check=True)
    result = json.loads(got.stdout.strip())
    assert "app.onboarding_tasks" in result["imports"] and "app.tasks_supplier_contracts" in result["imports"]
    assert "onboarding-deadline-sweep" in result["schedule"] and "supplier-contract-alerts" in result["schedule"]



def test_task4_review_missing_contract_statement_cannot_be_omitted_by_model(tmp_path):
    def transport(messages):
        if "Catalog ids" in messages[-1]["content"]:
            return '{"fact_ids":["price_change"]}'
        return '{"kind":"question","tools":["consult_contracts"]}'
    response = Supervisor(runtime_for(tmp_path), transport=transport).handle(SupervisorRequest(kind="question", question="What does the BritMed Supplies contract say?", supplier_id="HC-S05"))
    assert response.contracts.missing_contract is True
    assert "has no contract on file" in response.answer
