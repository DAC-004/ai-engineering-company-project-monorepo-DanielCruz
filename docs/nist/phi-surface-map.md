# Prohibited-data surface map

Date: 2026-10-08 C05 path verification. This map records what is enforced, what was verified, and the remaining bound. A synthetic marker in a blocked test is a control check. It is not a demonstrated disclosure of PHI.

## Events

| Surface | What is stored | Control inspected | Limit |
| --- | --- | --- | --- |
| Chat `user_message` | `event_text_for_turn()` in `services/api/app/services/chat_channel.py` | A blocked label (`policy_override`, `identifier_disclosure`, `embedded_instruction`, `jailbreak`, `patient_case`, `breach_probe`) or a match from `appears_to_contain_phi()` is replaced with `The submitted message was withheld from the event.` before publish and before the session message is appended. | An allowed question is still echoed. A detector miss is still published. |
| Support-agent decision log | `flow`, `action`, `reason`, `route`, `trace_id`, `recorded_at` | `append_decision()` does not take the question or the answer. Rejected login uses the same logger with `credentials_rejected` or `inactive`. | The line does not contain the account or the password. |
| Rate-limit log | Endpoint name and result | `model_rate_limit.py` logs the route and the block or allow result. | Does not cover other loggers. |
| Guardrail count log | Guard name, action, failure type | `audit.py` `record()` | Does not include the question. |
| RFP approval events | Decision status and department | The validate event records the decision and the revision count, not the note. The resume payload is screened before the checkpoint write. | A note that does not match the labeled-field screen is stored. |

## Tables

| Surface | What is stored | Control inspected | Limit |
| --- | --- | --- | --- |
| Agent traces | Blocked turns store `trace_label`, not the question. `graph.py` `persist_trace()`. | `screen_question()` runs before the trace write. | Allowed turns store `preparation.trace_question`, which is the message when `appears_to_contain_phi()` is false. |
| Memory audit | `rejected_phi` with `content_retained=False` and `safe_text=None` | `MemoryStore.record_phi_rejection()` | Only the memory store. |
| Approved memory notes | Staff-approved operational notes | `appears_to_contain_phi()` refuses a candidate before a proposal. | Not a scan of historical rows. |
| Users, suppliers, incidents, RFP tickets | Existing application rows | Incident title and description, and supplier name and notes, are rejected before insert when `screen_text()` finds a labeled patient field. Ordinary operational sentences are stored. Analysis `to_dict()` and the CSV export omit the uploaded patient field. | Production rows were not dumped. Text that does not match the labeled-field detector can still be stored. |

## Endpoint responses

| Surface | What is returned | Control inspected | Limit |
| --- | --- | --- | --- |
| Knowledge and agent query | Fixed refusal or fixed domain answer for screened classes. Generated text passes `safe_output()` before it is returned. | `screen_question()` returns `BREACH_NOTIFICATION`, `CONTRACT_SCOPE`, or `CONTRACT_REFUSAL` without calling the model. `disclosure_is_prohibited()` also rejects a labeled patient field. | A sentence that matches none of those detectors can still be returned. The tests do not prove every future model string. |
| Supplier delete without the header | HTTP 428 and a fixed detail | `require_explicit_confirmation()` | The log line is the action name and `rejected_unconfirmed`. |
| Chat assistant message | The agent answer | Same screen as the agent. | Allowed answers are returned to the caller. |

## Model output

Retrieved chunks that match the medication-instruction rule are dropped in `keep_chunks()`. The system prompt says retrieved text is data. Generated answers are verified with stubbed model text in the tests named below. A live local model was not sampled. The citation proof is separate from the prohibited-data check.

## What was fixed in this follow-up

`start_user_turn()` previously appended and published the raw text before `run_support_agent()`. Blocked classes and `appears_to_contain_phi()` matches are now withheld from that event. The original text is still passed into the agent so the existing refusal runs.

## Source, control, and evidence

This table is the bound of the prohibited-data check. A row that names columns, or a test that checks a citation, is not a check of free-text values. No production rows were read. No disclosure is inferred from a synthetic marker, from permitted policy text, or from a detector that might miss a phrase.

| Surface | Source | Control | Evidence | Bound |
| --- | --- | --- | --- | --- |
| Chat `user_message` | `chat_channel.py` `event_text_for_turn()` | Blocked labels and `appears_to_contain_phi()` are replaced before the event is stored. Allowed text is stored. | `test_blocked_chat_text_is_withheld_from_the_event` | The test uses a synthetic marker and one policy sentence. It does not scan stored events. |
| Decision log | `decision_log.py` | Fields are time, flow, action, reason, route, and trace id. | `test_support_agent_records_the_block_without_the_question` | One blocked turn. Other loggers are not this file. |
| Rate-limit log | `model_rate_limit.py` | Route and result only. | Rate-limit test asserts the question is absent from the 429 body. | That response body. Not every access log. |
| Guardrail log | `audit.py` `record()` | Guard name, action, and failure type. | Source inspection. | No separate value sample in this pass. |
| Telemetry event | `schemas/telemetry.py` | Envelope is validated. Per-event properties are not persisted. | `docs/owasp/evidence/2026-10-06-obligation-inspection.md` | Schema and that note. Property values were not read. |
| Users table | `UserInDB` fields `id`, `email`, `hashed_password`, `is_active`, `role`, `created_at` | No clinical column in the schema. | Same obligation note, column names only. | Values were not read. |
| Inventory tables | `MedicalSupply`, `SupplyDelivery`, `SupplyConsumption` | Stock and movement columns, including `clinic_id` and `vendor_name`. | Schema plus the obligation note's column list. | Values were not read. Column names do not prove the text in `vendor_name`. |
| RFP text tables | `draft_content`, `sections`, `key_aspects` | `screen_generated()` redacts labeled fields and patient-attached prose before a draft or aspect is stored. `append_trace()` stores `screen_generated_structure()`, not the raw model string. | `test_stored_rfp_text_omits_a_labeled_patient_field` in `tests/pipelines/test_rfp_phi.py`. `test_part1_through_part3_trace_keeps_order_and_redacts` asserts `REDACTME` is absent from the trace. `test_unlabeled_patient_prose_sets_contains_phi_and_redacts_stored_text` and `test_accepted_summary_is_screened_for_phi_before_it_is_returned`. | The stored copy in those tests omits the synthetic name. Historical rows were not read. A phrase outside the detector can still be stored. |
| Agent trace and checkpoint | `graph.py` `persist_trace()` and the sqlite checkpointer | A blocked turn stores `trace_label`. An allowed turn stores the question. `safe_output()` replaces a prohibited model answer before the checkpoint update. | `test_allowed_checkpoint_keeps_the_question_and_drops_a_labeled_field` and `test_model_phi_and_breach_text_are_removed_before_persistence` in `tests/pipelines/test_agent_guardrails.py`. | The allowed question is present in that checkpoint. The labeled field from the stubbed model answer is not. The test does not prove every future question. |
| Memory audit | `MemoryStore.record_phi_rejection()` | `content_retained=False` and `safe_text=None`. | Source comment and function body. | That rejection row. Not every memory note. |
| Knowledge and agent responses | `screen_question()` and `generate_answer()` | Screened classes return a fixed sentence. `generate_answer()` calls `_release_generated_text()`, which uses `safe_output()`. | Bypass tests. `test_generated_compliance_answer_cites_the_retrieved_policy` in `tests/pipelines/test_nist_protections.py`. `test_allowed_checkpoint_keeps_the_question_and_drops_a_labeled_field`. | Those classes and that stubbed answer. Retrieved policy text that is not prohibited is still returned. |
| Supplier and incident responses | Response schemas | Supplier fields are commercial. Incident results are aggregate counts on the results route. | Schema inspection. `docs/owasp/owasp-top10-audit.md` A01-BE. | Schemas are not a sample of stored description text. |
| Model output | `generate_answer()`, `keep_chunks()`, `safe_output()` | A medication-instruction chunk is dropped. `safe_output()` replaces a blocked string, including a labeled patient field. | `test_retrieved_medication_instruction_is_dropped`. `test_allowed_checkpoint_keeps_the_question_and_drops_a_labeled_field`. `test_model_phi_and_breach_text_are_removed_before_persistence`. | The citation test is not a PHI check. These tests use stubbed model text. They do not sample a live model and they do not prove every future string. |

## What this record means for C05

1. **What the implementation enforces.** Chat events withhold blocked text. Incident and supplier writes reject a labeled patient field. Analysis responses omit the CSV patient field. RFP `draft_content`, `key_aspects`, and node traces store the screened string from `screen_generated()` or `screen_generated_structure()`. An allowed support-agent checkpoint stores the question. A generated answer that `disclosure_is_prohibited()` rejects, including a labeled patient field, is replaced before it is returned or checkpointed.

2. **What was verified, and where.** `docs/nist/evidence/2026-10-08-c05-path-pytest.txt` records 77 passed. `docs/nist/evidence/2026-10-08-gap-closure-pytest.txt` records 69 passed. Neither file contains the pytest arguments or the node ids, so this map does not reconstruct those selections. The tests named in the table exist in the tree. No production rows were read.

3. **Remaining limitation, and its effect on completion.** The detectors match specific patterns. A sentence outside those patterns can still be stored, including an approval note that does not match them. Historical rows already on the host were not re-read, and that unread text is not treated as a violation. These bounds do not leave the checked paths unverified, and they do not reopen C05. They also do not prove every future input. C05 stays checked on the enforced write and response paths.

## Approval note

CONTEXT section 1 prohibits PHI, patient identifiers, and sensitive health data in events, tables, endpoint responses, logs, and AI output. Section 6 requires that verification as its own Protect item, using synthetic audit metadata rather than identifiable clinical text. Neither section prescribes a filter or an architecture.

The request body is `DepartmentDecision.note`. `submit_rfp_approval` passes it to `submit_approval_decision`, which calls `ApprovalRun.decide`. Reject and request-changes require a non-empty note. `decide` screens the note with `screen_generated()` before `Command(resume=...)`. The checkpointer stores that payload. `_await_approval` screens it again before graph state is written. `_revise` then places `feedback` in the generator user message. The validate trace records the decision and the count, not the note. The public section schema has no note field. The revision trace is passed through `append_trace`, which screens stored strings.

`test_approval_note_keeps_operational_text_and_drops_a_labeled_field` submits `Keep the twelve month term. patient: AUDIT-NOTE-1`. The checkpoint bytes, the revision prompt, and the trace omit `AUDIT-NOTE-1`. The operational sentence remains. That marker is audit metadata, not a clinical case.
