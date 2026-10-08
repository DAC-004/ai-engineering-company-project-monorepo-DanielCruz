# Adherence and deliverables report

Audit date: 2026-10-08 closeout. ZIP (8) review recorded on the same date.

Daniel uploaded evidence ZIP (8). The reviewing assistant's findings from that package are corrected in this revision: stale checklist decisions, the staff-frontend and compliance inventory rows, the owner-source attribution, the injection invocation, residual risk and mitigation, and the component-search record. A05's missed timing is unchanged.

This is an engineering adherence review against `project_specs.md` and `CONTEXT-healthcore.md`. It is not a certification. Final sign-off and submission remain Daniel's. This report does not claim either.

The repository table below is the 2026-10-08 closeout snapshot. It is not the published state. The published state is in `docs/nist/pre-submission-audit.md`: commit `1b4b8f758703651db127f772f2ba896f95d76f34`, pull request #38, 59 of 61 parent items checked, A05 and H06 open.

Daniel approved the corrected pre-submission audit and the 207-entry, 692,200-byte package on 2026-10-08. Both report findings from that review are closed. That approval authorizes staging the six documentation files. It is not final pull-request approval and it is not submission.

## Repository state

| Item | Value |
| --- | --- |
| Branch | `feature/nist-security-practices` |
| HEAD | `38a0806bcc2fc3106aa4e4f969fd893e87953d02` |
| Upstream | None |
| Worktree | One worktree. Closeout edits are uncommitted. |
| Commit and push | Not done |
| Pull request | Not created. After Daniel pushes, the agent creates it against `feature/owasp-top10-audit`. |

The first session fetched and created this branch. A later `git pull origin feature/owasp-top10-audit` printed `Already up to date.` That pull was not the first operation.

## Verified completion

| Item | Evidence |
| --- | --- |
| Owners assigned | `docs/nist/nist-report.md` inventory. Source: `CONTEXT.md`. RFP SSE channel owner is James Osei. This is not a claim that Daniel confirmed the names. |
| Third-party control | James Osei owns integration configuration. Claire Whitfield owns compliance for the 2026-10-06 agreement finding. |
| Five starting components kept in the inventory | Present: RAG and compliance answers. Absent as software, and not built: documentation assistant, referral notifier, patient-chart access log. |
| 2026-10-06 agreement finding | That host used local generation and local sqlite, and the tracker API base was unset. The finding stops there. It does not cover an uninspected deployment. |
| Prohibited-data map | `docs/nist/phi-surface-map.md`. C05 is checked. The map states what is enforced, the tests in `docs/nist/evidence/2026-10-08-c05-path-pytest.txt` (77 passed), and the remaining bound. That bound does not reopen C05. |
| Fixed policy answers | Breach and agreement replies cite the supplied HealthCore context and do not call the model. |
| Generated policy citation | A stubbed answer that omitted the HHS URL and invented an Article 6 basis was returned with the retrieved URL and without that basis. |
| Human confirmation | Tracker Delete arms confirmation. Confirm delete calls `removeNote`. Supplier delete returns HTTP 428 without the header. `validate_auth01.py` sends the header only after `--confirm`. RFP Approve is unchanged. |
| G07 clinic 3 read | Reclassified. The 200 matches the inventory contract. It is not an unauthorized-access gap. `docs/nist/g07-access-correction.md`. |
| HTTPS application delivery | `docs/owasp/evidence/sanitized/healthcore.conf` returns 301 to HTTPS for application requests and leaves the ACME challenge on port 80. The 2026-10-06 capture recorded HTTP `/` as 301. Port 80 was not closed. |
| Six NIST functions, one action each | `docs/nist/nist-report.md`. Those actions were not turned into extra graded builds. |
| Gap-closure tests | `docs/nist/evidence/2026-10-08-gap-closure-pytest.txt`: 69 passed in 16.50s. C05 path tests: `docs/nist/evidence/2026-10-08-c05-path-pytest.txt`: 77 passed in 17.13s. The earlier closeout log remains 52 passed in 12.96s. |

Authoritative checklist: `.project_specs/HEALTHCORE_SECURE_AI_CHECKLIST.md`. 55 of 61 parent items are checked. `docs/nist/checklist.md` matches it. A05 stays unchecked as a historical timing fact. H02 through H06 stay unchecked. Nested OWASP rows are disposed in `docs/nist/finding-disposition.md`.

Daniel uploaded `healthcore-nist-evidence-2026-10-08(9).zip` on 2026-10-08. That package had 203 entries and 698,431 bytes. The reviewing assistant confirmed the five ZIP (8) findings were resolved and found no additional actionable requirement gap. The assistant inspected the required-controls log and did not execute the tests. That review is not final approval, publication, or submission. U04 records it.

Daniel approved the pre-commit audit and ZIP (10) on 2026-10-08. ZIP (10) had 204 entries and 705,753 bytes. That approval authorizes staging. H02 through H06 stay unchecked until commit, push, pull-request creation, review request, and submission are evidenced.

## Evidenced non-applicability

| Item | Why it is not a passed control |
| --- | --- |
| C06, D09, D10, D11, D12 | Confirmed on 2026-10-08 in `docs/nist/evidence/2026-10-08-component-search.md`. Section 6 asks for confirmation in the current implementation. The products stay in the inventory. Absence is not a passed control. |
| C08 | The decision log is metadata for agent decisions. The same search found no patient-chart access log. The decision log is not that system. |
| C03, C04 | Non-applicability is the 2026-10-06 inspected host only. |

## Historical deviation

A05 required the model-input list before code. The list in `docs/nist/README.md` was written after the first edits. That timing was missed and is not marked satisfied. On 2026-10-08 the list was compared with the completed implementation. Rows were added for FastEmbed indexing and retrieval, and for the RFP classifier, orchestrator, worker, department generator, and synthesizer. That comparison is present-day verification. Neither source defines a deviation-signing step. The box stays unchecked.

## Gap accounting

| Class | Items |
| --- | --- |
| Implemented and verified | Injection block, retrieved-instruction drop, rate limit, decision log, fixed policy citations, generated citation repair, note Confirm delete, `--confirm` before the delete header, authenticated supplier mutations, labeled-patient-field rejection on incident and supplier writes, durable auth-rejection and tool-invocation lines, RFP approval button, owner assignments from `CONTEXT.md`. |
| Nested OWASP rows | Disposed in `docs/nist/finding-disposition.md`. Supplier mutations require a bearer. Incident-result reads and inventory stock match their contracts. A06 and A08 are not exploitable or not the host frontend. A09 auth and tool lines are durable. Telemetry was not given a new collector. |
| Evidenced non-applicability | C03 and C04 for the 2026-10-06 inspected host. C06 and D09 through D12 because those clinical actions were not found. Absence is not a passed control. |
| Historical deviation | A05. The input list followed the first code edits. The box stays unchecked. No signature is required. |
| Permitted residual findings | The six NIST actions that were not built, and the optional hardening rows in `docs/nist/finding-disposition.md`. Each names a risk and a mitigation. They are not missing explicit protections. |
| Pending publication and approval | Daniel commits and pushes. The agent then opens the pull request and requests his review. He uploads the ZIP, approves, and submits. |

## Final source audit

| Requirement | Source | Disposition |
| --- | --- | --- |
| Existing fork and `feature/nist-security-practices` | `project_specs.md` How to Start, steps 1-2 | Verified. A later pull of `origin/feature/owasp-top10-audit` was already up to date. |
| Credential inspection | How to Start, step 3 | Verified. Examples are placeholders. Values were not printed. |
| Model-input list before code | How to Start, step 4 | Historical deviation. Present-day inventory is `docs/nist/README.md`, rechecked against the implementation on 2026-10-08. Timing stays missed. |
| Inventory with an owner | What I need; evaluation | Verified from `CONTEXT.md` department responsibility. `CONTEXT-healthcore.md` does not name those people. |
| Six NIST functions, one action each | NIST report | Verified in `docs/nist/nist-report.md`. |
| No hardcoded secrets | Security by design | Verified for the working tree. |
| Input validation before the model | Security by design | Verified. `screen_question()` runs first. |
| System text separate from user text | Security by design | Verified. Retrieved text is labeled untrusted data. |
| Indirect injection mitigation | Security by design | Verified for the embedded medication instruction. |
| Validation before generated code or tool calls | Security by design | The support path does not execute generated code. Inventory writes are rejected. |
| Rate limit on one model endpoint | Security by design; evaluation | Verified on `POST /knowledge/query`. |
| Log one agentic flow | Security by design; evaluation | Verified. The decision line omits the question. |
| Human confirmation for irreversible actions | Security by design; CONTEXT section 5 | Verified for supplier, user, and analysis delete, tracker note delete, and RFP approval. The section 5 clinical actions were not found and were not built. |
| HIPAA and UK GDPR kept separate | CONTEXT sections 2 and 6 | Verified in the NIST report. |
| No prohibited data in events, tables, responses, logs, or AI output | CONTEXT sections 1 and 6 | Verified on the enforced paths, including the approval note. Finite detectors remain the bound. |
| One injection demonstration without identifiable clinical text | CONTEXT sections 4 and 6 | Verified. |
| OWASP 10 by 3 lanes, hardening, critical fixes | CONTEXT section 7 | The existing 2021 audit is the record. Critical fixes already in that audit stay. Optional hardening was not turned into a new requirement. |
| Gaps not fixed this cycle | NIST report | Documented with risk and mitigation. This allowance does not cover a missing explicit protection. |

## Pending publication

1. Daniel commits and pushes `feature/nist-security-practices` using the scope below.
2. After that push is present, the agent creates the pull request against `feature/owasp-top10-audit` and requests his tech-lead review.
3. Daniel uploads the ZIP to the reviewing assistant.
4. Daniel approves and submits separately.

## Checks

| Check | Result |
| --- | --- |
| Gap-closure pytest | Passed. 69 passed in 16.50s. `docs/nist/evidence/2026-10-08-gap-closure-pytest.txt`. |
| C05 path pytest | Passed. 77 passed in 17.13s. `docs/nist/evidence/2026-10-08-c05-path-pytest.txt`. |
| Approval-note pytest | Passed. `tests/pipelines/test_rfp_approval.py`, 8 passed. The new test is `test_approval_note_keeps_operational_text_and_drops_a_labeled_field`. The historical log does not contain the node ids. The command that wrote it is in `docs/nist/evidence/2026-10-08-injection-repro.md`. |
| Required controls | Passed. 10 passed in 1.97s. `docs/nist/evidence/2026-10-08-required-controls.md`. This run supplies the invocation the older summary logs do not contain. |
| NLTK readability | Three tests failed: `test_revenue_section_passes_readability_relevance_and_compliance`, `test_evaluators_enter_together`, and `test_short_text_records_why_no_grade_was_calculated`. `readability_metrics()` recorded `LookupError; no grade was calculated` because the local NLTK data did not satisfy the scorer. Neither source includes a readability grade in the acceptance criteria. These three are not counted as passing. |
| Browser | Not run. The notes list loads from `NEXT_PUBLIC_TRACKER_API_BASE_URL`. The deployed build left that unset, so the button was verified from the component source and the structural test. |
| Host SSH, firewall, HTTPS | Not re-probed. The redirect configuration and the 301 capture still apply because this pass did not change nginx. |

## Proposed commit

Do not include `.project_specs/`, any `.env`, `data/process/agent_decisions/`, `data/process/mcp_invocations/`, `docs/nist/review-package/`, or a Co-authored-by trailer. This list is the exclusion set for a later commit. It is not a request to commit now.

```
Require confirmation and block policy override before model calls.

HealthCore model endpoints now refuse instruction override, limit call rate, and keep irreversible deletes behind an explicit human confirmation step. Approval notes are screened before they are stored or sent to the revision model.
```

Proposed paths: `.env.example`, `.gitignore`, `data/pipelines/rag.py`, `data/pipelines/rfp_intake/agents.py`, `data/pipelines/rfp_intake/approval_graph.py`, `data/pipelines/rfp_intake/node_trace.py`, `data/pipelines/rfp_intake/phi.py`, `docs/nist/` except `docs/nist/review-package/`, `docs/owasp/owasp-top10-audit.md`, `docs/owasp/requirement-matrix.md`, `mcps/healthcore-tools/src/healthcore_tools/invocation_log.py`, `memory-bank/progress.md`, `services/api/.env.example`, `services/api/app/agent/decision_log.py`, `services/api/app/agent/graph.py`, `services/api/app/agent/guardrails/input_scope.py`, `services/api/app/agent/guardrails/text_rules.py`, `services/api/app/core/irreversible.py`, `services/api/app/core/model_rate_limit.py`, `services/api/app/core/prohibited_text.py`, `services/api/app/routers/agent.py`, `services/api/app/routers/auth.py`, `services/api/app/routers/incidents.py`, `services/api/app/routers/knowledge.py`, `services/api/app/routers/suppliers.py`, `services/api/app/routers/users.py`, `services/api/app/services/chat_channel.py`, `services/api/app/services/incident_service.py`, `services/api/app/services/rfp_demonstration_accounts.py`, `services/api/scripts/validate_auth01.py`, `services/api/tests/test_rfp_approval_api.py`, `tests/pipelines/test_agent_guardrails.py`, `tests/pipelines/test_error_path_privacy.py`, `tests/pipelines/test_nist_protections.py`, `tests/pipelines/test_rfp_approval.py`, `tests/pipelines/test_rfp_phi.py`, `uis/talent-pipeline-tracker/components/candidates/NotesSection.tsx`.

## Proposed pull request

Base: `feature/owasp-top10-audit`. Head: `feature/nist-security-practices`. Not `main`.

```
## Summary
- Block policy-override requests and retrieved treatment instructions before the model runs.
- Rate limit POST /knowledge/query and POST /agent/query.
- Require a bearer before supplier create, rate, status, and delete, and keep the human confirmation step before tracker note deletion and before supplier, user, and analysis deletes.
- Cite retrieved policy on generated compliance answers, and cite the supplied HealthCore context on the fixed breach and agreement answers.
- Add the NIST report under docs/nist/.

## Injection test
tests/pipelines/test_nist_protections.py::test_policy_override_is_blocked_before_the_model
tests/pipelines/test_nist_protections.py::test_retrieved_medication_instruction_is_dropped
Invocation and result: docs/nist/evidence/2026-10-08-injection-repro.md (2 passed in 2.08s).
The rate-limit, decision-log, confirmation, and citation checks are in docs/nist/evidence/2026-10-08-required-controls.md (10 passed in 1.97s).
The earlier 69-pass, 77-pass, and 8-pass logs are separate historical counts. Their files do not contain a combined command.

## Gap disposition
- Owners are assigned from CONTEXT.md.
- The 2026-10-06 inspected host did not show an external processor receiving claims, clinical data, or UK personal data. That finding is not a statement about any other deployment.
- Clinic 3 supply reads match the inventory contract and are not an unauthorized-access gap. The inventory source is in the review ZIP.
- Prohibited-data checks cover incident and supplier writes, analysis output, blocked chat text, RFP draft and key-aspect text, allowed support-agent checkpoints, generated answers that contain a labeled patient field, and the approval note before it is checkpointed or sent to the revision model. Finite detectors and unread historical rows remain the bound. That bound does not reopen C05.
- Nested OWASP rows are disposed in docs/nist/finding-disposition.md.
- The documentation assistant, referral notifier, patient-chart access log, and clinical KPI dashboard were searched for on 2026-10-08 and were not found. They stay in the inventory and were not built. That confirmation is not a passed control.
- The model-input list was written after the first code edits. A same-day comparison added the embedding and RFP model-role rows. That timing deviation stands. It is not a signature item.
- Daniel uploaded the 203-entry evidence package on 2026-10-08. That review found no additional actionable requirement gap. It is not final approval or submission.
- Final sign-off and submission remain Daniel's.
```

## Evidence ZIP

`docs/nist/review-package/healthcore-nist-evidence-2026-10-08.zip`

Gitignored. Daniel uploaded the prior package, ZIP (8). This file is the refreshed package. Upload of this package is not done.
