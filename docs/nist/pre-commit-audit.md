# Pre-commit audit

Date: 2026-10-08. Daniel approved this audit and ZIP (10) on 2026-10-08. ZIP (10) is the package at 204 entries and 705,753 bytes. That approval authorizes publication preparation and staging. Commit, push, pull-request creation, and submission have not occurred. Final sign-off is not claimed.

## ZIP (9)

Daniel uploaded `healthcore-nist-evidence-2026-10-08(9).zip` on 2026-10-08. The package had 203 entries and 698,431 bytes.

The reviewing assistant inspected it and confirmed that all five findings from ZIP (8) were resolved:

- Stale checklist decisions corrected.
- Staff-frontend and compliance inventory statements corrected.
- Reproducible injection-test instructions supplied.
- Residual gaps documented with risks, mitigations, and priorities.
- Component-search evidence and supporting sources included.

The separate attachments matched the ZIP text. The required-controls log identified ten tests and recorded `10 passed in 1.97s`. The reviewing assistant inspected that evidence and did not execute the tests. The review found no additional actionable requirement gap. It did not constitute final approval, publication, or submission.

U04 is checked for that upload, review, and resolution. The authoritative checkbox count after that change is 55 of 61.

## Repository

| Item | Evidence |
| --- | --- |
| Remote | `origin` `https://github.com/DAC-004/ai-engineering-company-project-monorepo-DanielCruz.git` (fetch and push) |
| Branch | `feature/nist-security-practices` |
| HEAD | `38a0806bcc2fc3106aa4e4f969fd893e87953d02` |
| HEAD subject | Prevent sensitive error disclosure and document the two priority security fixes |
| Upstream | None. `git branch -vv` shows no tracking branch. |
| Worktrees | One. This directory. |
| Staged | None. `git diff --cached --name-only` was empty. |
| Base | `origin/feature/owasp-top10-audit` is the same commit as HEAD. |

Unstaged modifications and untracked files are the proposed commit, after the exclusions below. Nothing is staged.

## Match to ZIP (9)

Before this audit file was added, the implementation files in the worktree matched ZIP (9) once Windows newlines were normalized. Seven historical evidence files differed because ZIP (9) decoded UTF-16 bytes as UTF-8 and stored replacement characters:

- `docs/nist/evidence/2026-10-08-nist-pytest.txt`
- `docs/nist/evidence/2026-10-08-closeout-pytest.txt`
- `docs/nist/evidence/2026-10-08-followup-pytest.txt`
- `docs/owasp/evidence/2026-10-05-npm-audit-root.json`
- `docs/owasp/evidence/2026-10-05-npm-audit-tracker.json`
- `docs/owasp/evidence/2026-10-05T234354Z-guest-readonly-recapture.txt`
- `docs/owasp/evidence/2026-10-07T2317Z-chat-worker-deploy.txt`

The three NIST logs were transcribed to UTF-8 after that comparison. Their last lines remain `6 passed in 1.87s`, `52 passed in 12.96s`, and `49 passed in 13.10s`. The four OWASP files were not rewritten. The refreshed package stores repository bytes for files that are not valid UTF-8.

Changes after ZIP (9), all documentation:

- U04 checked and the checklist count set to 55 of 61.
- `docs/nist/checklist.md`, `docs/nist/adherence-report.md`, and this file.
- The three NIST log transcriptions above.

No application code changed after ZIP (9). The 10-pass suite was not rerun for that reason.

## Proposed commit scope

Include the unstaged paths from `git status --short` and the untracked files under `docs/nist/` except `docs/nist/review-package/`, plus:

- `services/api/app/agent/decision_log.py`
- `services/api/app/core/irreversible.py`
- `services/api/app/core/model_rate_limit.py`
- `services/api/app/core/prohibited_text.py`
- `tests/pipelines/test_nist_protections.py`

`.env.example` and `services/api/.env.example` are placeholders. The rate-limit lines are comments. `RFP_DEMONSTRATION_PASSWORD=` is empty.

Exclude:

- `.project_specs/`
- `docs/nist/review-package/`
- populated `.env` files
- `data/process/agent_decisions/`
- `data/process/mcp_invocations/`
- `__pycache__/`, `.pytest_cache/`, `.venv/`, and `services/api/.venv/`

`git check-ignore` matches `/.project_specs/` and `docs/nist/review-package/`. No `Co-authored-by` trailer.

Suggested message:

```
Require confirmation and block policy override before model calls.

HealthCore model endpoints now refuse instruction override, limit call rate, and keep irreversible deletes behind an explicit human confirmation step. Approval notes are screened before they are stored or sent to the revision model.
```

## Secret and data inspection

The diff removes the previous demonstration password string from `rfp_demonstration_accounts.py`. `services/api/tests/test_rfp_approval_api.py` sets `RFP_DEMONSTRATION_PASSWORD` to `rfp-approval-test-password` for that test process. That is a test fixture, not a populated environment file. The approval-note test uses the marker `AUDIT-NOTE-1`. `src/data/sample.ts` is not in the proposed scope. No populated `.env` is modified. The status list does not include caches, virtual environments, decision logs, or invocation logs.

## Requirements and evidence

| Source requirement | Evidence |
| --- | --- |
| Existing fork and `feature/nist-security-practices` | Remote and branch above. HEAD equals `origin/feature/owasp-top10-audit`. |
| Credential examples inspected | `.env.example` files. Values were not printed. |
| Model-input inventory | `docs/nist/README.md`. Present-day list verified against the call sites. A05 timing stays missed. |
| Inventory with an owner | `docs/nist/nist-report.md`. Names come from `CONTEXT.md`. |
| No hardcoded production secret | Demonstration password read from the environment. |
| Input validation before the model | `screen_question()` before retrieval. 10-pass log. |
| System text separate from user text | `test_system_instructions_stay_separate_from_user_content`. |
| Indirect injection from retrieved text | `test_retrieved_medication_instruction_is_dropped`. |
| Validation before generated code or tool calls | This tree does not execute model-written SQL. MCP rows are checked by `partition_rows()` and are not sent to the model. |
| Rate limit on one model endpoint | `test_knowledge_endpoint_rate_limit_stops_before_the_model`. |
| Log one agent decision | `test_support_agent_records_the_block_without_the_question`. |
| Human confirmation for irreversible actions that exist | Supplier 428, `--confirm`, Confirm delete, RFP approval button. |
| Section 5 actions in the current implementation | `docs/nist/evidence/2026-10-08-component-search.md`. The source sentence is "Confirm that the actions in section 5 require human confirmation in your current implementation." The missing products were not built. |
| HIPAA and UK GDPR kept separate | `docs/nist/nist-report.md` Regulatory regimes. |
| Prohibited data on enforced paths | `docs/nist/phi-surface-map.md`. Finite detectors remain the bound. |
| One injection demonstration | `docs/nist/evidence/2026-10-08-injection-repro.md` and the 10-pass log. |
| Six NIST functions, one action each | `docs/nist/nist-report.md`. |
| Gaps not fixed this cycle | Same report. Exact source sentence: "For each identified gap you didn't fix in this cycle, document the risk and the proposed mitigation." |
| OWASP report retained | `docs/owasp/owasp-top10-audit.md` and the 30-row matrix. Residual rows in `docs/nist/finding-disposition.md`. |

Evaluation points use the same evidence: inventory and owners, no hardcoded production key, the injection tests, the rate-limit test, the decision-log test, confirmation on the actions that exist, six NIST actions, and the HealthCore regulatory section.

## Tests, kept separate

| Record | Result | Scope |
| --- | --- | --- |
| `docs/nist/evidence/2026-10-08-required-controls-pytest.txt` | 10 passed in 1.97s | Ten named tests in `test_nist_protections.py`. Command in `docs/nist/evidence/2026-10-08-required-controls.md`. |
| `docs/nist/evidence/2026-10-08-injection-repro-pytest.txt` | 2 passed in 2.08s | The two injection tests only. |
| `docs/nist/evidence/2026-10-08-gap-closure-pytest.txt` | 69 passed in 16.50s | Summary only. Arguments were not recovered. |
| `docs/nist/evidence/2026-10-08-c05-path-pytest.txt` | 77 passed in 17.13s | Summary only. Arguments were not recovered. |
| `docs/nist/evidence/2026-10-08-approval-note-pytest.txt` | 8 passed in 3.04s | `tests/pipelines/test_rfp_approval.py`. |
| `docs/nist/evidence/2026-10-08-nist-pytest.txt` | 6 passed in 1.87s | Historical summary. The file now has more tests. |
| `docs/nist/evidence/2026-10-08-closeout-pytest.txt` | 52 passed in 12.96s | Historical summary. |
| `docs/nist/evidence/2026-10-08-followup-pytest.txt` | 49 passed in 13.10s | Historical summary. |

NLTK: `test_revenue_section_passes_readability_relevance_and_compliance`, `test_evaluators_enter_together`, and `test_short_text_records_why_no_grade_was_calculated` failed with `LookupError; no grade was calculated`. `project_specs.md` and `CONTEXT-healthcore.md` do not include a readability grade. Those failures are not counted as passing. See `docs/nist/evidence/2026-10-08-nltk-readability.md`.

No required verification was found missing after ZIP (9). The documentation edits do not change runtime behavior, so the 10-pass suite was not repeated.

## Distinctions

- A05 is a historical timing deviation. The inventory in `docs/nist/README.md` is the present-day list. The checkbox stays open. No signature is requested.
- Section 5 absence is confirmation in the current implementation, recorded in the component search. It is not a passed clinical control.
- The six NIST actions that were not built are source-permitted residual findings. Each states the gap, risk, mitigation, and priority. They are not the injection, rate-limit, logging, or confirmation requirements.

## Proposed pull request

Not created. Base `feature/owasp-top10-audit` matches `origin/feature/owasp-top10-audit` at HEAD. Head would be `feature/nist-security-practices` after a push. The proposed body is in `docs/nist/adherence-report.md`. It links the injection tests and states the remaining gaps.

## Current state

Working tree is dirty. Nothing is staged. The branch has no upstream. Commit, push, pull, merge, pull-request creation, and submission were not performed.
