# Pre-submission control rerun

Date executed: 2026-10-08. Audited revision: `1b4b8f758703651db127f772f2ba896f95d76f34`. This is the published head of pull request 38. The run checks the same ten tests as `docs/nist/evidence/2026-10-08-required-controls.md`. It does not replace that log, the injection log, or the historical summary counts.

Working directory: `services/api`

Interpreter: `services/api/.venv`, Python 3.13.12. No API key or other secret was set. The tests stub the model or read source. Pytest reported rootdir as the repository root because the selected files are under `tests/pipelines/`.

```
.\.venv\Scripts\python.exe -m pytest -v --tb=short --override-ini testpaths= ..\..\tests\pipelines\test_nist_protections.py::test_policy_override_is_blocked_before_the_model ..\..\tests\pipelines\test_nist_protections.py::test_retrieved_medication_instruction_is_dropped ..\..\tests\pipelines\test_nist_protections.py::test_system_instructions_stay_separate_from_user_content ..\..\tests\pipelines\test_nist_protections.py::test_knowledge_endpoint_rate_limit_stops_before_the_model ..\..\tests\pipelines\test_nist_protections.py::test_support_agent_records_the_block_without_the_question ..\..\tests\pipelines\test_nist_protections.py::test_supplier_delete_route_rejects_a_request_without_the_header ..\..\tests\pipelines\test_nist_protections.py::test_operator_flag_is_required_before_the_delete_header_is_sent ..\..\tests\pipelines\test_nist_protections.py::test_note_delete_waits_for_a_second_human_action ..\..\tests\pipelines\test_nist_protections.py::test_bypass_answers_cite_the_supplied_context_and_do_not_call_the_model ..\..\tests\pipelines\test_nist_protections.py::test_generated_compliance_answer_cites_the_retrieved_policy
```

Observed result: exit 0. `10 passed in 1.94s`. Log: `docs/nist/evidence/2026-10-08-presubmission-pytest.txt`.

The log names the ten tests and does not contain the question text, a named-person example, or a secret.
