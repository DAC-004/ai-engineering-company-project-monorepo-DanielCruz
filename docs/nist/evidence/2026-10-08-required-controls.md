# Required control demonstration

Date executed: 2026-10-08. The earlier NIST logs record counts and do not record the pytest arguments. This run is the completion of that missing invocation. It does not replace those historical counts and it does not make the A05 pre-code timing satisfied.

Working directory: `services/api`

Interpreter: `services/api/.venv`, Python 3.13.12. No API key or other secret was set. The tests stub the model or read source.

```
.\.venv\Scripts\python.exe -m pytest -v --tb=short --override-ini testpaths= ..\..\tests\pipelines\test_nist_protections.py::test_policy_override_is_blocked_before_the_model ..\..\tests\pipelines\test_nist_protections.py::test_retrieved_medication_instruction_is_dropped ..\..\tests\pipelines\test_nist_protections.py::test_system_instructions_stay_separate_from_user_content ..\..\tests\pipelines\test_nist_protections.py::test_knowledge_endpoint_rate_limit_stops_before_the_model ..\..\tests\pipelines\test_nist_protections.py::test_support_agent_records_the_block_without_the_question ..\..\tests\pipelines\test_nist_protections.py::test_supplier_delete_route_rejects_a_request_without_the_header ..\..\tests\pipelines\test_nist_protections.py::test_operator_flag_is_required_before_the_delete_header_is_sent ..\..\tests\pipelines\test_nist_protections.py::test_note_delete_waits_for_a_second_human_action ..\..\tests\pipelines\test_nist_protections.py::test_bypass_answers_cite_the_supplied_context_and_do_not_call_the_model ..\..\tests\pipelines\test_nist_protections.py::test_generated_compliance_answer_cites_the_retrieved_policy
```

Observed result: exit 0. `10 passed in 1.97s`. Log: `docs/nist/evidence/2026-10-08-required-controls-pytest.txt`.

| Source requirement | Test | Observed |
| --- | --- | --- |
| Prompt injection blocked | `test_policy_override_is_blocked_before_the_model` and `test_retrieved_medication_instruction_is_dropped` | Passed |
| System text separate from user text | `test_system_instructions_stay_separate_from_user_content` | Passed |
| Rate limit on one model endpoint | `test_knowledge_endpoint_rate_limit_stops_before_the_model` | Passed |
| Log one agent decision | `test_support_agent_records_the_block_without_the_question` | Passed |
| Human confirmation before delete | supplier 428, `--confirm`, and Confirm delete | Passed |
| Compliance answer cites the policy | fixed replies and the generated citation repair | Passed |
