# Part 3 testing

Simulated approvals and the live UI upload are separate records.

## Simulated path

This path does not start the browser and does not load the local GGUF model. `complete_fn` is injected.

```powershell
uv run --project services/api --python 3.13 python -m pytest tests/pipelines/test_rfp_approval.py tests/pipelines/test_rfp_arbitration.py tests/pipelines/test_rfp_approval_e2e.py services/api/tests/test_rfp_approval_api.py -q
```

The combined Part 1 through Part 3 suite also includes the Part 1 and Part 2 modules:

```powershell
uv run --project services/api --python 3.13 python -m pytest tests/pipelines/test_rfp_classifier.py tests/pipelines/test_rfp_worker.py tests/pipelines/test_rfp_grounding.py tests/pipelines/test_rfp_phi.py tests/pipelines/test_rfp_response_readiness.py tests/pipelines/test_rfp_generator.py tests/pipelines/test_rfp_evaluator.py tests/pipelines/test_rfp_response_loop.py tests/pipelines/test_rfp_approval.py tests/pipelines/test_rfp_arbitration.py tests/pipelines/test_rfp_approval_e2e.py services/api/tests/test_rfp_intake_api.py services/api/tests/test_rfp_approval_api.py -q
```

Readability uses `data/process/nltk_data`, which this repository does not commit. The intake API test points `NLTK_DATA` at that directory. For a local run, point it at the Part 1 tokenizer directory before pytest:

`C:\4geeks\Projects\Milestone_9_Agentic_RFP_Workflow_Part_1\ai-engineering-company-project-monorepo-DanielCruz\data\process\nltk_data`

Do not copy that directory into git.

Observed on 30 September 2026, before the live UI run: 69 tests passed with that tokenizer directory available.

After the live run, the same command was repeated on 30 September 2026: 72 passed. The two added cases cover a US sentence that rejects UK GDPR and a stored BAA target that no longer matches the current draft.

`tests/pipelines/test_rfp_approval_e2e.py` is the reproducible Part 1 through Part 3 fixture. It is not the live upload.

## Demonstration identities

These accounts are workflow identities, not verified people. Startup creates them with the existing TinyDB user service. The password stays in `services/api/app/services/rfp_demonstration_accounts.py` and is not written here.

| Department | Email | Owner recorded on approval |
| --- | --- | --- |
| revenue | rfp.revenue.demonstration@healthcore.com | Tom Callahan |
| clinical | rfp.clinical.demonstration@healthcore.com | Dr. Marcus Reid |
| compliance | rfp.compliance.demonstration@healthcore.com | Claire Whitfield |

A different account receives 403. `approver` stays empty and that branch is not resumed.

## Live UI upload

This record is the browser session. It is not the stubbed `complete_fn` path above.

Run on 30 September 2026 through `http://localhost:3000`, with the API on `http://127.0.0.1:8000`.

Preparation that was actually used:

- `NLTK_DATA` pointed at the Part 1 tokenizer directory above. It was not copied into git.
- `RAG_MODELS_DIR` pointed at the existing local snapshot that contains `qwen2.5-3b-instruct-q4_k_m.gguf`. No model was downloaded.
- The UI dependencies were installed from `uis/talent-pipeline-tracker` with `npm install`, then started with `npm run dev`.
- The PDF was `CONTEXT-healthcore-request-1.pdf` from the Part 1 `.project_specs` directory. It was attached in the existing upload form at `/backoffice/rfp`. It was not copied into git.

Ticket `bf8ee96a-47a7-4de3-b75a-30fc226da68c` is the same row across intake, generation, and approval.

| Step | Observed |
| --- | --- |
| Upload | `POST /rfp/tickets` returned 202. The page opened that ticket id. |
| Intake | Status moved from `analyzing` to `intake_complete`. Stored client Meridian Manufacturing, Inc., country US, covered population `800 employees`, Flesch-Kincaid 13, Gunning fog 11. Departments clinical, compliance, and revenue were on the ticket. |
| Generation | `POST /rfp/tickets/{id}/response` returned 202. Status became `needs_human_review`. Clinical and revenue evaluations passed. Compliance stayed provisional. |
| Start approval | `POST /rfp/tickets/{id}/approval` moved the ticket to `waiting_for_approval`. The page showed each draft, evaluation, required owner, and the three decisions. |
| Wrong account | Signed in as the revenue demonstration account, Approve on clinical returned 403 `not_department_owner`. All three sections stayed pending. |
| Revenue while others wait | The revenue account approved revenue. Stored approver Tom Callahan. Status stayed `waiting_for_approval`. Clinical and compliance checkpoints were still interrupted. The revenue checkpoint was not. |
| Clinical account | Signed out and signed in as the clinical demonstration account. That page showed revenue already approved and clinical still pending. Approve stored Dr. Marcus Reid. Compliance stayed pending and interrupted. |
| Compliance account | Signed out and signed in as the compliance demonstration account. Approve stored Claire Whitfield. |
| Final document | Status became `done`. The ticket page showed Final document, currency USD, and the three section texts. `GET /rfp/tickets/{id}/final-document` returned 200 with only `ticket_id`, `sections`, `currency`, and `generated_at`. Sections were revenue, clinical, and compliance. `generated_at` was `2026-09-30T19:02:58.941038`. After that, none of the three department checkpoints were interrupted. |

The node trace on that ticket includes Part 1 `classify`, `orchestrate`, the three workers, and `synthesize`; Part 2 `generate` and `evaluate`; and Part 3 `enter_part3`, each `{department}_await_approval`, `arbitrate`, `validate_decision`, `revise_compliance`, `converge_eligibility`, `synthesize_final_document`, and `persist_document_and_done`. Synthesis and persistence are after the approvals that made the ticket eligible.

Live result: passed for this ticket.

Two failures were fixed in scope and the affected checks were rerun before this result:

- The compliance draft said a Business Associate Agreement was required and that a Data Processing Agreement related to UK GDPR was not. The substring check treated that rejection as the wrong instrument, so approval stayed blocked. A sentence that adopts UK GDPR still fails. A sentence that rejects it does not.
- The stored BAA target list from the earlier revision still blocked Approve after the draft no longer adopted that instrument. The approve gate now reads the current drafts.

## Initial ticket load

On the first live upload, `GET /rfp/tickets/bf8ee96a-47a7-4de3-b75a-30fc226da68c` returned 500 before any reload. `get_current_user` raised `JSONDecodeError: Expecting value: line 1 column 1`. FastAPI runs those auth reads on a thread pool, and they share one TinyDB file handle. A write seeks that handle, so a concurrent read can decode an empty buffer or a torn document. A later reload returned 200. That recovery did not make the first load successful.

The auth file now uses `LockedJSONStorage` in `services/api/app/db/tinydb.py`. Each complete read and each complete write holds one lock. The user and profile tables are unchanged.

Regression, 30 September 2026:

```powershell
uv run --project services/api --python 3.13 python -m pytest services/api/tests/test_tinydb_concurrent_auth.py services/api/tests/test_rfp_intake_api.py services/api/tests/test_rfp_approval_api.py -q
```

14 passed. `test_tinydb_concurrent_auth.py` reads the user row while another thread writes it. The same pattern without the lock raises the empty-buffer `JSONDecodeError`.

After that fix, a new browser upload of the same Meridian PDF opened `http://localhost:3000/backoffice/rfp/a28f9894-08d6-4496-bb33-1a90dd1d0180` with no reload. The first `GET /rfp/tickets/a28f9894-08d6-4496-bb33-1a90dd1d0180` returned 200, and the page showed `analyzing`. The API log for that process has no 500 and no `JSONDecodeError`. This check stops at the first ticket load. It does not replace the approval and final-document record for `bf8ee96a-47a7-4de3-b75a-30fc226da68c`. The storage lock does not change those stored approvals or that final document.

The revenue draft on the completed ticket proposes commercial terms, including dollar amounts. The request's budget field stayed "Not stated". Those amounts are generated proposal text, not a budget extracted from the RFP. They are in the stored final document because approval copied the approved draft.
