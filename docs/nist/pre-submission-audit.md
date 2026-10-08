# Pre-submission audit

Audit date: 2026-10-08.

This audit compares the published tree with `project_specs.md` and `CONTEXT-healthcore.md`. It is not a certification, final pull-request approval, or submission. Daniel remains the tech lead who approves and submits.

Daniel approved this corrected audit and the review package on 2026-10-08. That package had 207 entries and 692,200 bytes. Both report findings from that review are closed. The approval authorizes staging the six documentation and evidence files. It does not approve pull request #38 and it does not confirm submission. A05 and H06 stay open. The approval sentences were added after the package was built.

`docs/nist/pre-commit-audit.md` stays the historical record of the worktree before commit `1b4b8f7`. Its HEAD, 55 of 61 count, and "commit not done" sentences describe that earlier moment.

## Audited revisions

| Item | Value |
| --- | --- |
| Repository | DAC-004/ai-engineering-company-project-monorepo-DanielCruz |
| Local branch | `feature/nist-security-practices` |
| Upstream | `origin/feature/nist-security-practices` |
| Local HEAD | `1b4b8f758703651db127f772f2ba896f95d76f34` |
| Remote head | `1b4b8f758703651db127f772f2ba896f95d76f34` |
| Parent | `38a0806bcc2fc3106aa4e4f969fd893e87953d02` |
| Worktrees | One |
| Pull request | https://github.com/DAC-004/ai-engineering-company-project-monorepo-DanielCruz/pull/38 |
| PR state | Open |
| PR base | `feature/owasp-top10-audit` |
| PR head | `feature/nist-security-practices` |
| PR head OID | `1b4b8f758703651db127f772f2ba896f95d76f34` |
| Commit message | Require confirmation and block policy override before model calls. No `Co-authored-by` trailer. |
| Author | danielcruz, cruzdaniel004@gmail.com, GitHub login DAC-004 |

Before this audit the worktree matched that commit. This report, the checklist recount, and the new evidence files are local changes. They are not part of pull request #38.

## Publication verification

Daniel committed, pushed, and ran `git pull --ff-only origin feature/nist-security-practices`. That pull printed `Already up to date`. Local HEAD, the upstream, and the pull-request head are the same commit. The pull-request base is `feature/owasp-top10-audit` at the parent commit.

The commit contains 57 paths. It includes `docs/nist/nist-report.md`, `docs/nist/README.md`, the implementation under `services/api/`, `data/pipelines/`, the tracker note confirmation, and the test and evidence files named below. `git ls-tree` of that commit contains no `.project_specs/` path, no `docs/nist/review-package/` path, no populated `.env`, no `agent_decisions` log, no `mcp_invocations` log, and no virtual environment. `git grep` of that commit found no occurrence of the retired demonstration password.

The current GitHub description was left in place. It links:

- `docs/nist/nist-report.md` at `1b4b8f7`
- `docs/nist/README.md` at `1b4b8f7`
- both injection tests in `tests/pipelines/test_nist_protections.py`
- `docs/nist/evidence/2026-10-08-injection-repro.md` and its pytest log (`2 passed in 2.08s`)
- `docs/nist/evidence/2026-10-08-required-controls.md` and its pytest log (`10 passed in 1.97s`)

The Remaining findings section explains A05, the absent section 5 actions, and the NIST residuals that the source permits. The Review section asks Daniel to review the pull request as tech lead before final sign-off. GitHub's reviewer list is empty because the author is DAC-004. `reviewDecision` is empty. That request is not approval.

## Eight evaluation points

| Evaluation point | Source | Result |
| --- | --- | --- |
| Inventory with an owner | project_specs.md, What We Will Evaluate, item 1 | Met in `docs/nist/nist-report.md`. Owners come from `CONTEXT.md`. |
| No hardcoded keys | Same section, item 2 | Met for the published source. Keys are environment variables. The old demonstration password is absent from the commit. |
| One injection test | Same section, item 3 | Met. Both section 4 shapes passed again on this commit. |
| Rate limit | Same section, item 4 | Met. `POST /knowledge/query` is rate limited. `POST /agent/query` uses the same limiter. |
| Agent logging | Same section, item 5 | Met. The support-agent block writes a decision line without the question. |
| Human confirmation | Same section, item 6 | Met for deletes and RFP approval that exist. Section 5 clinical actions are absent and were not built. |
| Six NIST functions | Same section, item 7 | Met. Each function has one priority-1 action plus a gap, risk, and mitigation. |
| HealthCore regulatory framework | Same section, item 8 | Met. HIPAA and UK GDPR are separate, with 60 days and 72 hours to the ICO. |

## Source-to-evidence mapping

Status uses the authoritative checklist after this recount. "Published" means the cited file is in commit `1b4b8f7`. "Local" means this audit added it and it is not in that commit. No application code changed in this audit, so no correction is unpublished implementation.

| ID | Source | Location | Verification | Result |
| --- | --- | --- | --- | --- |
| A01 | How to Start, step 1 | This fork | Remote is DAC-004's fork. | Checked |
| A02 | How to Start, step 1 | `feature/nist-security-practices` | Branch exists, tracks origin, and is the PR head. | Checked |
| A03 | How to Start, step 2 | CONTEXT-healthcore.md | Report uses HIPAA and UK GDPR from that file. | Checked |
| A04 | How to Start, step 3 | `.env.example`, `services/api/.env.example` | Placeholder files are in the commit. No populated `.env` is. | Checked |
| A05 | How to Start, step 4 | `docs/nist/README.md` | Present-day list covers user text, knowledge-base documents, embeddings, remote chat, retry, MCP-after-generation, and each RFP role. The list was written after the first edits. | Open. Timing missed. Inventory complete. |
| B01 | Inventory and governance | `docs/nist/nist-report.md` inventory | Each listed component has an owner from `CONTEXT.md`. | Checked |
| B02 | Same section, third-party sentence | NIST report Agreements | James Osei owns integration configuration. Claire Whitfield owns the agreement gate. | Checked |
| B03 | CONTEXT section 3 | Same inventory | All five starting components are listed. Absent ones were not built. | Checked |
| B04 | Challenge text, system-wide review | Inventory plus component search | Present, elsewhere, and absent surfaces are named. | Checked |
| C01 | CONTEXT section 2 and section 6 | NIST report Regulatory regimes | US and UK are separate sections. | Checked |
| C02 | Same sections | Same report | 60 days versus 72 hours to the ICO, and different recipients. | Checked |
| C03 | CONTEXT section 2, BAA when a pipeline touches claims or clinical data | `docs/owasp/evidence/2026-10-06-obligation-inspection.md` | The 2026-10-06 inspected host used local generation. That condition was not met on that host. | Checked as host-limited non-applicability |
| C04 | CONTEXT section 2, DPA for an external processor | Same inspection | No external UK processor was found on that host. | Checked as host-limited non-applicability |
| C05 | CONTEXT section 1 and section 6 Protect item | `docs/nist/phi-surface-map.md` | Write and response paths tested, including approval notes. Finite detectors and unread historical rows remain a bound. | Checked. Bound does not reopen the item. |
| C06 | CONTEXT section 3 documentation risk | `docs/nist/evidence/2026-10-08-component-search.md` | No SOAP sign or send path. | Checked as absence confirmation, not a passed control |
| C07 | CONTEXT section 3 compliance risk | Citation tests | Fixed answers cite the supplied context. Generated repair cites a retrieved URL. | Checked |
| C08 | CONTEXT section 3 access-log risk | Component search | No patient-chart access log. The decision log is a different record. | Checked as absence confirmation |
| D01 | Security by design, credentials | Published source search | No hardcoded demonstration password in the commit. | Checked |
| D02 | User input before the model | `screen_question()` | Policy override is blocked before retrieval. | Checked |
| D03 | System versus user content | `data/pipelines/rag.py` | System message is separate. Test passed on this commit. | Checked |
| D04 | Indirect injection | `chunk_is_prohibited()` | Retrieved medication instruction dropped. Test passed on this commit. | Checked |
| D05 | Generated code, SQL, or tool calls | `safe_output()`, MCP allowlists | This tree does not execute model-written SQL. Tool arguments are checked before the call. | Checked |
| D06 | Rate limit at least one model endpoint | `services/api/app/core/model_rate_limit.py` | Knowledge endpoint test passed on this commit. | Checked |
| D07 | Log at least one agentic flow | `services/api/app/agent/decision_log.py` | Block recorded without the question. Test passed on this commit. | Checked |
| D08 | Irreversible actions | Deletes, note delete, RFP approval | Supplier delete returns 428 without the header. Confirm delete calls `removeNote`. `--confirm` is required before the script sends the header. | Checked |
| D09 | CONTEXT section 5, sign or send a note | Component search | Path absent. Not built. | Checked as absence confirmation |
| D10 | CONTEXT section 5, notify a patient | Component search | Path absent. Not built. | Checked as absence confirmation |
| D11 | CONTEXT section 5, share history | Component search | Path absent. Not built. | Checked as absence confirmation |
| D12 | CONTEXT section 5, status change | `uis/backoffice/app/page.tsx` | Sample appointment counts are not a status write. | Checked as absence confirmation |
| D13 | Challenge text, urgent protections | Injection screen and password removal | Demonstrated by the tests above. | Checked |
| E01 | CONTEXT section 4 and section 6 | `tests/pipelines/test_nist_protections.py` | Both shapes passed on `1b4b8f7`. The fixture uses `SYN-714`, not the named-person example. | Checked |
| E02 | CONTEXT section 6 and section 7 | This pytest log | The new log has no named person and no secret. | Checked |
| E03 | Acceptance criteria, reproducible test | `docs/nist/evidence/2026-10-08-presubmission.md` | Command, cwd, and result recorded. | Checked |
| F01 | NIST Govern | `docs/nist/nist-report.md` Govern | Priority-1 action, gap, risk, mitigation. | Checked |
| F02 | NIST Identify | Same, Identify | Same structure. | Checked |
| F03 | NIST Protect | Same, Protect | Includes the prohibited-data item. | Checked |
| F04 | NIST Detect | Same, Detect | Alert not built. Risk and mitigation are written. Rate limit and decision log exist. | Checked |
| F05 | NIST Respond | Same, Respond | Separate US and UK paths. Roster not invented. | Checked |
| F06 | NIST Recover | Same, Recover | Drill not run. Risk and mitigation are written. | Checked |
| F07 | Gaps not fixed this cycle | Same six gap paragraphs | Each has risk and proposed mitigation. This does not replace a missing explicit protection. | Checked |
| F08 | CONTEXT section 6 deliverable | NIST report plus surface map | Separate regimes, inventory, injection test, section 5 confirmation, Protect item. | Checked |
| G01 | CONTEXT section 7 | `docs/owasp/requirement-matrix.md` | 30 rows, A01-BE through A10-AG, edition Top 10:2021, lanes BE, FE, AG. | Checked |
| G02 | SSH access model | Existing OWASP evidence | Prior host record. Not a new probe. | Checked |
| G03 | Non-root deploy user | Same | Prior host record. | Checked |
| G04 | Firewall rules | Same | Prior host record. | Checked |
| G05 | HTTPS-only clinical surfaces | `docs/owasp/evidence/sanitized/healthcore.conf` | HTTP application requests return 301. Port 80 stays open for the ACME path. | Checked |
| G06 | Block public DB, queue, and model admin | Prior listener evidence | Prior host record. | Checked |
| G07 | Role and clinic boundaries | `docs/nist/g07-access-correction.md` | Clinic 3 HTTP 200 matches the inventory contract. No clinic filter was added. | Checked |
| G08 | Keys, TLS, traces | Finding disposition | Prior audit plus this cycle's secret and trace controls. | Checked |
| G09 | Debug endpoints and physician gate | NIST human-gates table | No auto-send path exists. | Checked |
| G10 | Hardening proof and critical fixes | OWASP report plus this commit | The two priority fixes remain HC-ERR-PRIV and HC-RENEW-LOG from the prior instruction. | Checked |
| H01 | How to Submit, step 2 | `docs/nist/nist-report.md` | In the commit and linked from the pull request. | Checked |
| H02 | How to Submit, step 1 | Commit `1b4b8f7` | Pushed. Upstream matches. | Checked |
| H03 | How to Submit, step 2 | Pull request #38 | Open in this fork. Correct base and head. | Checked |
| H04 | How to Submit, step 3 | Current PR description | Injection links and remaining findings. Description not overwritten. | Checked |
| H05 | How to Submit, step 4 | PR Review section | Requested. Not approved. | Checked |
| H06 | Daniel's approval and submission | PR `reviewDecision` | Empty. Submission not confirmed. | Open |
| U01 | Final audit | This file | This pass. | Checked |
| U02 | Adherence report | `docs/nist/adherence-report.md` | Historical closeout text kept. Current state pointed here. | Checked |
| U03 | Evidence ZIP | Review package rebuilt after this file | Inspected in the build script output. | Checked when the ZIP build succeeds |
| U04 | Prior review | ZIP (9) record in the checklist | 203 entries, 698,431 bytes, five ZIP (8) findings closed. This audit does not replace that record. | Checked for that cycle |

Nested OWASP findings stay in `docs/nist/finding-disposition.md`. A checked G parent is not a claim that every nested residual was implemented. Residuals there keep a risk and a mitigation. Optional items were not built: SRI, GGUF hash-on-read, and a telemetry collector.

## End-to-end paths on this revision

This section traces the published revision. It is a record of test calls, source reads, and reused logs. It is not a browser session and it is not a full runtime pass through every path. The 2026-10-06 and 2026-10-07 host captures were not repeated.

Checks executed in the new ten-test run:

1. Staff question: `screen_question()` returns a fixed refusal for the policy-override fixture. Retrieval and generation are not called. The support-agent test records the block reason and does not record the question.
2. Retrieved protocol text: `chunk_is_prohibited()` drops the embedded medication instruction before it is placed in the user message. The separation test checks that the system message stays apart from the user message and states that it outranks user, retrieved, and tool text.
3. Rate limit: the knowledge-route test observes the fixed window stop the call before the model.
4. Supplier delete: `TestClient` records 401 with no bearer and 428 for an authenticated request without `X-HealthCore-Confirm: confirmed`. `confirmation_headers()` adds that header only when `--confirm` is present.
5. Tracker confirmation, structural source inspection inside that same run: `test_note_delete_waits_for_a_second_human_action` reads `NotesSection.tsx`. The first Delete branch sets `pendingDeleteId`. The Confirm delete branch calls `removeNote`. No browser click was performed.
6. Fixed policy replies and the generated citation repair: the breach and agreement answers cite the supplied context, and `_qualify_permissibility_answer` drops an Article 6 basis that is not in the retrieved chunks and appends a retrieved HHS or ICO URL when the stubbed sample omitted it. The citation test stubs the model.

Earlier unchanged evidence reused, not rerun for this audit:

7. RFP approval note: `decide()` runs `screen_generated()` before the checkpoint command. Operational text is kept. A labeled field is not stored or sent to the revision model. Evidence: `8 passed in 3.04s` in `docs/nist/evidence/2026-10-08-approval-note-pytest.txt`. `approval_graph.py` is unchanged in commit `1b4b8f7`.

Paths traced by source inspection and not exercised in the ten-test run:

8. Chat publication: `event_text_for_turn()` replaces a blocked turn with the withheld label. The withholding test exists and was not part of the ten-test selection.
9. RFP Approve button: `RfpTicketPanel.tsx` calls `handleDecision`, which calls `submitRfpDecision`. That wiring was read in an earlier source test and was not part of the ten-test selection.
10. MCP incident rows: `_row_clause()` appends id, status, category, origin, and branch after generation. Title and description are not copied into the model prompt. The invocation-log test was not in the ten-test selection. `invocation_log.py` is unchanged in this commit, so the gap-closure record remains the invocation evidence.

## Tests executed now

Working directory `services/api`. Interpreter `services/api/.venv`, Python 3.13.12. No API key was set.

Command and result: `docs/nist/evidence/2026-10-08-presubmission.md`.

Observed: exit 0, `10 passed in 1.94s`. Log: `docs/nist/evidence/2026-10-08-presubmission-pytest.txt`.

The ten tests are the two injection cases, system and user separation, the knowledge rate limit, the support-agent decision log, supplier delete without the header, `--confirm`, note Confirm delete, the fixed policy replies, and the generated citation repair.

## Prior evidence reused

| Record | Result | Why it was reused |
| --- | --- | --- |
| `2026-10-08-injection-repro-pytest.txt` | 2 passed in 2.08s | Same two tests passed again in the ten-test run. The older log stays the first recorded invocation. |
| `2026-10-08-required-controls-pytest.txt` | 10 passed in 1.97s | Same selection. The new run is the check on the published commit. The 1.97s log is not rewritten. |
| `2026-10-08-approval-note-pytest.txt` | 8 passed in 3.04s | `approval_graph.py` and `test_rfp_approval.py` are in `1b4b8f7` and were not edited after that run. |
| `2026-10-08-gap-closure-pytest.txt` | 69 passed in 16.50s | Summary only. Arguments were not recovered and were not invented. |
| `2026-10-08-c05-path-pytest.txt` | 77 passed in 17.13s | Summary only. Arguments were not recovered and were not invented. |
| `2026-10-08-nist-pytest.txt` | 6 passed in 1.87s | Historical summary. Not the command. |
| `2026-10-08-followup-pytest.txt` | 49 passed in 13.10s | Historical summary. |
| `2026-10-08-closeout-pytest.txt` | 52 passed in 12.96s | Historical summary. |
| `2026-10-08-nltk-readability.md` | 3 failed, LookupError | Not rerun. Neither source grades readability. Not counted as passing. |
| Host captures dated 2026-10-06 and 2026-10-07 | SSH, firewall, HTTPS 301, agreement inspection | Not a fresh probe. They support G02 through G06 and the host-limited C03 and C04 findings. |

## Findings and corrections

No mandatory implementation failure was found on `1b4b8f7`. No application file was edited.

The published checklist still said commit and the pull request were pending, because that text was committed before those operations. This audit checks H02 through H05 from the operations that followed. H06 stays open. The checklist, this report, the adherence pointer, and `memory-bank/progress.md` are the local corrections. Daniel would need a later commit and push if he wants those files in the pull request. They are not in #38.

U04 stays checked for the ZIP (9) review. This audit is an additional record.

## Non-applicability

- C03 and C04 apply when a pipeline sends claims or clinical text to a vendor, or when an external processor handles UK personal data. The 2026-10-06 inspection found local generation and local sqlite on that host. The finding is limited to that host.
- C06, C08, and D09 through D12 are confirmations that those actions are absent. CONTEXT section 6 asks for confirmation in the current implementation. The products stay in the inventory. Absence is not a passed control.

## Permitted residuals

project_specs.md says a gap not fixed this cycle must document the risk and the proposed mitigation, and that the six functions do not all need an enterprise implementation. Each NIST function in `docs/nist/nist-report.md` has that pair:

- Govern: owner column can go stale. Mitigation: edit it from `CONTEXT.md` when a lead changes.
- Identify: the absence search is point-in-time. Mitigation: repeat it when another branch is merged.
- Protect: no signed BAA or DPA file exists. Mitigation: leave remote model keys unset for claims or clinical text until the agreement exists.
- Detect: logs are not paged. Mitigation: alert on repeated `model_rate_limit` blocks and `policy_override` decisions. The rate limit and the decision log are already implemented.
- Respond: no on-call roster. Mitigation: write a US path and a separate UK path and name the owner. The roster was not invented.
- Recover: the restore drill was not run. Mitigation: write the drill and name who runs it, outside this cycle.

## A05

The model-input inventory in `docs/nist/README.md` matches the call sites in this commit: knowledge and agent questions, WebSocket history, knowledge-base generation and indexing, remote embedding, remote chat, the generation retry, approved memory, MCP rows appended after generation, and the RFP classifier, orchestrator, worker, generators, synthesizer, and approval note.

The list was written after the first code edits. That missed How to Start step 4. The completed list does not satisfy the original sequence. The checkbox stays open. Neither source asks Daniel to sign the deviation.

## Checklist count

Counted from `.project_specs/HEALTHCORE_SECURE_AI_CHECKLIST.md` lines that are `- [x] **… complete**` or `- [ ] **… complete**`.

- Checked: 59
- Open: A05, H06
- Parent items: 61

`docs/nist/checklist.md` repeats that result. The pre-commit report's 55 of 61 count remains the count before H02 through H05 were evidenced.

## Differences from pull request #38

Published and unchanged by this audit: the 57-file commit, including application code and the pre-commit report.

Local, not in the pull request:

- `docs/nist/pre-submission-audit.md`
- `docs/nist/evidence/2026-10-08-presubmission.md`
- `docs/nist/evidence/2026-10-08-presubmission-pytest.txt`
- `docs/nist/checklist.md`
- `docs/nist/adherence-report.md`
- `memory-bank/progress.md`
- `.project_specs/HEALTHCORE_SECURE_AI_CHECKLIST.md` (local-only, copied into the review ZIP)

The review ZIP is gitignored.

## Readiness

The published commit meets the eight evaluation points and the explicit protections. A05 remains a historical timing deviation. H06 remains Daniel's final approval and confirmed submission.

Daniel approved this audit and the 207-entry, 692,200-byte package. That approval authorizes staging. It is not final pull-request approval and it is not submission.
