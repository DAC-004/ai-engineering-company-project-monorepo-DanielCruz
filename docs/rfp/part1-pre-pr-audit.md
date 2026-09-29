# Part 1 pre-PR audit

Pre-commit snapshot, September 29, 2026. Branch `feature/rfp-intake`. Published HEAD at this snapshot is `87b52a9da9836a8ba0ef0899a1fc105c7b229202`, level with `origin/feature/rfp-intake`. At this snapshot that commit does not contain this audit or the contract-term correction. Those edits are uncommitted local changes. `main` is `2ffd9a74d6070677f385c7134ea6ab5d25db8308`, and that commit is the merge base of this branch.

Sources for the checklist: `.project_specs/project_specs.md` and the Part 1 portions of `.project_specs/CONTEXT-healthcore.md`. Part 2 and Part 3 are not scored. Design questions are answers, not extra pass/fail rows.

`py-readability-metrics` is the suggested readability implementation, not a rule that forbids another documented scorer. This project uses that suggested package. A one-off CLI is allowed under `scripts/` and is not required. None was added.

## Readiness

As of this pre-commit snapshot on September 29, 2026, no requirement is FAIL or NOT VERIFIED. Ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662` is the Meridian result cited for the current summary. The project is ready for the user to commit these local changes, push, open the pull request, and request review. Those publication and submission steps are not done as of this snapshot.

## How to start

| Instruction | Result | Evidence |
| --- | --- | --- |
| Create `feature/rfp-intake` from `main` | PASS | `git merge-base HEAD main` is `2ffd9a74d6070677f385c7134ea6ab5d25db8308`, which is current `main`. |
| Install new dependencies with `uv add` | PASS | Inspected manifests in commit `e06c07e`: `services/api/pyproject.toml` and `services/api/uv.lock` list langgraph, llama-cpp-python, markitdown with the pdf extra, py-readability-metrics, and pytest. Those files show the declared dependencies. They do not prove which install command ran. The installation-command claim is agent-reported: `uv add` from `services/api` for `markitdown[pdf]`, `py-readability-metrics`, `langgraph`, and `llama-cpp-python`, then `uv add --dev pytest`. No retained shell log of those commands was found. |
| Extend the existing backoffice, not a new frontend | PASS | Upload pages are `uis/talent-pipeline-tracker/app/(app)/backoffice/rfp/`. This repository has no `uis/backoffice` application. |
| Routes on the existing API, pipeline under `data/pipelines/` | PASS | `services/api/app/routers/rfp_intake.py` and `data/pipelines/rfp_intake/`. |
| Read the company context and upload the sample PDFs through the UI | PASS | Department ids, contacts, USD/BAA, and GBP/DPA come from that context. Meridian was uploaded again through the file input after this correction. The informal accept and invalid reject were not re-uploaded. Their earlier results still apply to the classifier and deadline logic, which this change did not replace. |

## Evaluation criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| Same backend API only; pipeline under `data/pipelines/`; no second HTTP service | PASS | The router calls the pipeline. No second RFP service was added. |
| Ticket, metadata, and key aspects in PostgreSQL | PASS | Separate PostgreSQL read of ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662` after the synthesis upload. |
| Uploaded PDFs land under `data/raw/`; UI drives upload | PASS | Playwright set `#rfp-file` and submitted the form. `has_pdf` is true. A labeled-PHI test still asserts that a patient-labeled PDF is not written. |
| Status is `analyzing`, `intake_complete`, or `discarded` | PASS | The corrected ticket is `intake_complete`. `waiting_for_approval` is not used. Ticket `4dbbed19-213c-40d3-8df9-61b7e9145053` stayed `analyzing` with `processing_failed` and code `model_output_invalid` before the parser accepted trailing prose. That ticket was not relabeled. |
| Async upload and poll | PASS | `POST /rfp/tickets` returned 202. The ticket page polls. The completed view for `7a7c4afa-e872-4223-974c-bb7bf8b5e662` showed the client, sections, and summary together. |
| Classifier rejects a non-RFP without stopping other tickets | PASS | Earlier live discard of ticket `a77d94f5-d6a7-4445-8a47-e533147da5c9` while accepted tickets stayed `intake_complete`. Earlier run: 2 classifier tests passed after the JSON parser change. The latest run is the 29 grounding, PHI, and API intake tests, which did not include the classifier file. The discard branch was not changed. |
| Metadata and readability stored per processed valid RFP | PASS | Ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662` stores Flesch-Kincaid 13.0 and Gunning fog 11.0. Request 2's earlier row stored Flesch-Kincaid 12.0, Gunning fog null, and the reason that the scorer returned `college`. That label was not converted into a number. |
| Separate orchestrator, workers, and synthesizer | PASS | Graph nodes remain `classify`, `orchestrate`, `revenue_worker`, `clinical_worker`, `compliance_worker`, and deferred `synthesize`. The grounding step repairs omissions after the synthesizer. It does not replace the agents. |
| Handoff carries `ticket_id`, summary, and key aspects | PASS | `part2_handoff.ticket_id` is `7a7c4afa-e872-4223-974c-bb7bf8b5e662`. The handoff summary matches the ticket summary, including the clinical and revenue asks. |
| Result lists key aspects and contacts, checked against the samples | PASS | Ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662`. The summary asks Dr. Marcus Reid about injury triage and wellness screenings and asks Tom Callahan about the 12-month contract term. The source requires the vendor to execute the Business Associate Agreement. Claire Whitfield is HealthCore's internal Compliance contact. The handoff sections carry those findings under the same contacts. |
| Unit tests for the classifier and at least one worker | PASS | `tests/pipelines/test_rfp_classifier.py` and `tests/pipelines/test_rfp_worker.py`. Earlier runs: 2 classifier tests passed, and 17 grounding and worker tests passed. The latest run is 29 grounding, PHI, and API intake tests. |
| Departments and RFP rules match the company context | PASS | Revenue, clinical, and compliance are always routed. The corrected summary includes the US rule for USD and a Business Associate Agreement. |

## Explicit build requirements

| Requirement | Result | Notes |
| --- | --- | --- |
| Ticket-mode PDF upload on the existing backend | PASS | 202, then background processing, then poll. |
| PDF stored under `data/raw/` and status `analyzing` | PASS | The analyzing row is committed before the response. The clean PDF is written after the input PHI screen. |
| LangGraph pipeline under `data/pipelines/rfp_intake/` | PASS | Routers do not own the graph. |
| MarkItDown before any agent reads the document | PASS | `convert.py`. An equivalent converter is allowed if it is documented. This project uses MarkItDown. |
| Metadata fields from the company context | PASS | Client, country, program, population, deadline, budget, departments, and readability grades. No patient columns. |
| Readability metrics for processing cost | PASS | Suggested package `py-readability-metrics`. Numeric grades are stored. A non-numeric label stays null with a reason. |
| Classifier, then orchestrator, workers, and synthesizer | PASS | Workers receive metadata plus their own extract. The synthesizer still writes the summary. Grounding adds a stated contract term the revenue worker dropped, names a contact the summary omitted, and corrects budget attribution. |
| Workers do not invent absent volumes | PASS | A missing budget stays an open question. The 12-month term is copied from the converted document, not invented. |
| Sales-facing summary of what to ask whom, then `intake_complete` and a Part 2 handoff | PASS | Ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662` asks Dr. Marcus Reid about the clinical findings and Tom Callahan about the contract term. Claire Whitfield is HealthCore's internal Compliance contact. The source requires the vendor to execute the Business Associate Agreement. A contact name by itself is not treated as that synthesis. |
| PHI is not stored, logged, or returned | PASS | Latest run, with the grounding tests: 29 passed in `tests/pipelines/test_rfp_grounding.py`, `tests/pipelines/test_rfp_phi.py`, and `services/api/tests/test_rfp_intake_api.py`. That run includes the labeled-PHI storage test and `test_generated_phi_is_screened_before_persist`. |
| Same ticket id continues | PASS | `ticket_id` is the handoff id. A separate `rfp_id` is not stored. |

## Submission instructions

| Instruction | Result | Remaining action |
| --- | --- | --- |
| Branch `feature/rfp-intake` committed and pushed | Partial as of this pre-commit snapshot on September 29, 2026 | The published branch at this snapshot is `87b52a9`. The correction, this audit, and the updated description are local only at this snapshot. |
| Pull request describes the implementation and how to test it | User step | Open the pull request against `main` with `docs/rfp/part1-pr-description.md`. |
| Description includes a sample RFP and the actual output | PASS in the local description | The Meridian transcription is unchanged. The actual output is ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662`. Tickets `821d4b8e-a868-4d0b-b2d9-0adcf05eb84f` and `a95ac8df-c797-4f60-99f9-d56f3f2221c1` are labeled as earlier runs. |
| Request a review from the tech lead | User step | The user sends the review request. |

Audit report, as of this pre-commit snapshot on September 29, 2026:

https://github.com/DAC-004/ai-engineering-company-project-monorepo-DanielCruz/blob/feature/rfp-intake/docs/rfp/part1-pre-pr-audit.md

That URL was not fetched during this snapshot.

## Gaps closed in this audit

| Gap | Earlier evidence | Closure |
| --- | --- | --- |
| 12-month term and renewal option missing from key aspects and the handoff | Ticket `a95ac8df-c797-4f60-99f9-d56f3f2221c1` revenue aspects had no contract term | Ticket `821d4b8e-a868-4d0b-b2d9-0adcf05eb84f` revenue aspects and `part2_handoff.sections` include `Contract term: 12 months, with option to renew.` |
| Summary named contacts without asking them about their findings | Ticket `821d4b8e-a868-4d0b-b2d9-0adcf05eb84f` listed Dr. Marcus Reid, Claire Whitfield, and Tom Callahan in separate contact sentences | Ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662` asks Dr. Marcus Reid about injury triage and wellness screenings, and asks Tom Callahan about the 12-month term. Claire Whitfield is HealthCore's internal Compliance contact. The source requires the vendor to execute the Business Associate Agreement. |
| Missing budget attributed to Tom Callahan | That summary said Tom Callahan had not provided budget figures | The corrected summary says the source request did not state a budget or payment terms |

An upload before the parser fix, ticket `4dbbed19-213c-40d3-8df9-61b7e9145053`, stayed `analyzing` with `model_output_invalid` because the synthesizer wrote a JSON object and then another sentence. The parser now keeps the first JSON object. That failed ticket was not rewritten.

## Design questions

- An unknown department name is noted on the revenue open questions. No extra worker is created.
- Workers see shared metadata and their own extract. A missing budget or headcount becomes an open question.
- A non-RFP is discarded with reason `not_healthcore_rfp`. Other tickets are unchanged. A false negative stops only that ticket as discarded. A new upload creates a new ticket.
- Conflicting figures stay unresolved. A missing value is not labeled a disagreement.
- Background work is a FastAPI background task in the API process. A caught failure stays `analyzing` with `processing_failed`. A dead process is reported as `stalled` after 15 minutes without a status rewrite.

## Checks

Latest run: 29 passed in `tests/pipelines/test_rfp_grounding.py`, `tests/pipelines/test_rfp_phi.py`, and `services/api/tests/test_rfp_intake_api.py`.

- Parser cases in that latest run: a fenced JSON object followed by prose is kept and the prose is dropped; malformed JSON and a non-string summary are `model_output_invalid`; a labeled patient field inside an accepted summary is redacted before the synthesizer returns it. The API test `test_generated_phi_is_screened_before_persist` checks that redaction before the response and the database write.
- Meridian PDF uploaded through the backoffice file input. PostgreSQL read-back of ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662`.

Earlier runs, not the latest: 2 classifier tests passed, and 17 grounding and worker tests passed. The classifier test file and the separate worker test file were not included in the latest run. Grounding tests were included alongside PHI and API intake tests. The forecast suite, the backoffice typecheck, and the Thames Valley and MedFlow uploads were not repeated. The informal-accept and invalid-reject uploads predate this check.

## Limitations

- Request 2's Gunning fog value remains null from the earlier run because the scorer returned `college`. No fog number was invented. That PDF was not uploaded again.
- A discarded ticket does not get an `rfp_metadata` row. Readability is stored for each valid RFP.
- The Meridian summary still includes model sentences about a vendor type and a Data Processing Agreement. Those sentences are not the clinical ask or the revenue contract-term ask. The source requires the vendor to execute the Business Associate Agreement. Claire Whitfield is HealthCore's internal Compliance contact. The recorded summary attributes missing vendor preferences, additional BAA terms, and DPA information to department contacts. The source and recorded worker sections do not establish that those people supplied or withheld that information. These are unsupported model attributions, not verified source facts.
