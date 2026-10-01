# Pull request title

Add HealthCore RFP intake and routing (Part 1)

# Pull request description

## Problem and behavior

Revenue Cycle receives institutional PDFs and cannot tell, from the document alone, which departments to ask and what each one needs. Part 1 stops before proposal writing. It classifies the PDF, and for a HealthCore RFP it records metadata, readability, per-department key aspects, contacts, and a Sales summary.

The upload page is the existing backoffice at `/backoffice/rfp` in `uis/talent-pipeline-tracker`. This repository has no `uis/backoffice` application. `POST /rfp/tickets` on the existing FastAPI service returns 202 with status `analyzing`. MarkItDown converts the PDF before any agent reads it. A dedicated LangGraph in `data/pipelines/rfp_intake/` classifies the Markdown, then either discards that ticket or runs separate revenue, clinical, and compliance workers and a deferred synthesizer. Compliance is always included. The completion commit stores the ticket, metadata, key aspects, and `part2_handoff` together in PostgreSQL. A missing local GGUF leaves the ticket `analyzing` with `processing_failed`. A dead process is reported as `stalled` without changing the stored status.

Audit report: https://github.com/DAC-004/ai-engineering-company-project-monorepo-DanielCruz/blob/feature/rfp-intake/docs/rfp/part1-pre-pr-audit.md

## Setup and checks

Executed this turn, after the synthesis check and the parser tests:

- 29 passed: `uv run --project services/api --python 3.13 python -m pytest tests/pipelines/test_rfp_grounding.py tests/pipelines/test_rfp_phi.py services/api/tests/test_rfp_intake_api.py`
- Meridian `CONTEXT-healthcore-request-1.pdf` was uploaded again through the backoffice file input. The stored result is ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662`.

Earlier, before this synthesis check: 17 grounding and worker tests passed, and 2 classifier tests passed. The Thames Valley and MedFlow uploads were not repeated.

Earlier, on the implementation in `e06c07e`: 24 passed across the classifier, PHI, worker, grounding, and API tests. The note that PHI and API tests were not rerun applied only before the synthesis check. It is superseded by the 29-test run above, which reran grounding, PHI, and the API intake tests. The Thames Valley and MedFlow uploads were not repeated.

Reviewer setup, not an additional claim that these steps were repeated:

- [ ] Use Python 3.13 for `services/api`. Set `DATABASE_URL` to the existing PostgreSQL pooler. Point `RAG_MODELS_DIR`, or `data/process/models/`, at the local `qwen2.5-3b-instruct-q4_k_m.gguf`. Do not download a model for this part.
- [ ] Start the API with `uv run --python 3.13 uvicorn app.main:app --host 127.0.0.1 --port 8000` from `services/api`. Start the backoffice with `NEXT_PUBLIC_API_BASE_URL` pointed at that API.
- [ ] Sign in, open RFP intake, and upload a PDF with the file input.
- [ ] Read the ticket from PostgreSQL in a separate session.

## Sample input

Source: CONTEXT curriculum file `CONTEXT-healthcore-request-1.pdf` (Meridian Manufacturing formal RFP). This is the document text. The PDF file is not in Git.

REQUEST FOR PROPOSAL (RFP)

On-Site Occupational Health & Corporate Wellness Program

RFP Reference No.: MM-OH-2026-002

Issuing Organization: Meridian Manufacturing, Inc.

Date Issued: August 3, 2026

Proposal Due Date: August 23, 2026

1. Background

Meridian Manufacturing operates an 800-employee manufacturing facility in Austin, Texas. We are seeking a healthcare partner to provide on-site occupational health services and a corporate wellness program for our workforce.

2. Scope of Work / Services Requested

The PDF presents these as a bulleted list:

- On-site occupational health clinic staffed 3 days/week
- Injury and illness triage and treatment for workplace incidents
- Annual wellness screenings for all 800 employees
- Chronic condition management support (diabetes, hypertension)
- Contract term: 12 months, with option to renew
- Vendor must be able to execute a Business Associate Agreement (BAA) in compliance with HIPAA prior to contract execution

3. Evaluation Criteria

| Criterion | Weight |
| --- | --- |
| Clinical capacity and staffing plan | 35% |
| Compliance and data security practices | 25% |
| Pricing | 25% |
| References from similar manufacturing clients | 15% |

4. Timeline

| Milestone | Date |
| --- | --- |
| RFP issued | Aug 3, 2026 |
| Questions due | Aug 10, 2026 |
| Proposals due | Aug 23, 2026 |
| Award notification | Sep 7, 2026 |

5. Submission Instructions

Proposals must be submitted electronically to procurement@meridianmfg.com no later than the proposal due date listed above. Late submissions will not be considered.

6. Contact

Rebecca Ortiz
VP of Human Resources, Meridian Manufacturing
Meridian Manufacturing, Inc.

## Actual output

Recorded PostgreSQL read-back for ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662`. This is the stored result, not an expected-result substitute. The completed backoffice view showed the same client, sections, and summary.

Ticket

- ticket_id: 7a7c4afa-e872-4223-974c-bb7bf8b5e662
- status: intake_complete
- processing_failed: false
- processing_error_code: null
- phi_detected: false
- compliance_review_required: false
- stored PDF present: true

Metadata

- client_name: Meridian Manufacturing, Inc.
- client_country: US
- program_type: On-site Occupational Health & Corporate Wellness Program
- covered_population: 800 employees
- deadline: August 23, 2026
- budget_range: null
- departments_needed: revenue, clinical, compliance
- flesch_kincaid_grade: 13.0
- gunning_fog: 11.0

Clinical Operations, Dr. Marcus Reid

Key aspects:

- Injury and illness triage and treatment for workplace incidents
- Annual wellness screenings for all 800 employees
- Chronic condition management support (diabetes, hypertension)
- On-site occupational health clinic staffed 3 days/week.

Open questions: none

Compliance and Data Governance, Claire Whitfield

Key aspects:

- Vendor must be able to execute a Business Associate Agreement (BAA) in compliance with HIPAA prior to contract execution
- USD currency requirement
- No mention of a Data Processing Agreement or UK GDPR reference

Open questions:

- Is there a specific vendor or type of vendor required?
- Are there any additional terms or conditions that need to be addressed in the BAA?
- Is there a preference for a vendor based in the US or a specific region?

Revenue Cycle, Tom Callahan

Key aspects:

- Annual wellness screenings for all 800 employees
- Chronic condition management support (diabetes, hypertension)
- Contract term: 12 months, with option to renew.

Open questions:

- Is there a budget for the on-site occupational health clinic?

Synthesizer summary

Meridian Manufacturing, Inc. is requesting an on-site occupational health and corporate wellness program for 800 employees. The program includes injury and illness triage and treatment, annual wellness screenings, and chronic condition management support. The contact for Clinical Operations is Dr. Marcus Reid. The contact for Compliance and Data Governance is Claire Whitfield. The contact for Revenue Cycle is Tom Callahan. The Compliance contact states that a Business Associate Agreement (BAA) must be executed in compliance with HIPAA. The source request did not state a budget or payment terms. The Revenue Cycle contact does not provide a specific vendor or type of vendor requirement, and the Compliance contact does not provide additional terms or conditions for the BAA. The Revenue Cycle contact does not provide a Data Processing Agreement or UK GDPR reference. US client: quote in USD and include a Business Associate Agreement.
Ask Dr. Marcus Reid (Clinical Operations) about Injury and illness triage and treatment for workplace incidents; Annual wellness screenings for all 800 employees. Ask Tom Callahan (Revenue Cycle) about Contract term: 12 months, with option to renew.

Part 2 handoff

- handoff ticket_id: 7a7c4afa-e872-4223-974c-bb7bf8b5e662
- phi_detected: false
- compliance_review_required: false
- The handoff summary and the three department sections match the values recorded above, including `Contract term: 12 months, with option to renew.`

## Earlier output

Ticket `821d4b8e-a868-4d0b-b2d9-0adcf05eb84f` is the Meridian run before the synthesis check. It is not the current output. Its summary named Dr. Marcus Reid, Claire Whitfield, and Tom Callahan, and it stored the 12-month term on the revenue section, but it did not ask Dr. Marcus Reid about the clinical findings or Tom Callahan about the contract term. Ticket `a95ac8df-c797-4f60-99f9-d56f3f2221c1` is older still: its revenue aspects omitted the 12-month term, and its summary said Tom Callahan had not provided the budget. Those stored fields were not rewritten.

## Match summary

This paragraph is a summary of the comparison with ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662`. It is not additional output.

The stored client, population, proposal due date, clinic schedule, wellness screenings, chronic-condition support, injury triage, HIPAA Business Associate Agreement requirement, and the 12-month term with an option to renew come from the sample. The sample states no budget, and the stored budget is null. The summary asks Dr. Marcus Reid about injury and illness triage and the annual wellness screenings. It asks Tom Callahan about the 12-month contract term and says the source request did not state a budget or payment terms. It names Claire Whitfield, HealthCore's internal Compliance contact. The source requires the vendor to execute the Business Associate Agreement. Naming the contacts is not the synthesis. The sample does not label a patient, and the stored ticket has `phi_detected` false. The output does not restate the RFP reference number, the August 3 issue date, Austin, the evaluation weights, the August 10 question deadline, the September 7 award date, the procurement address, or Rebecca Ortiz.

## Validation results

These are executed results. They are not reviewer instructions.

- Request 1, this verification: ticket `7a7c4afa-e872-4223-974c-bb7bf8b5e662`, recorded in Actual output. PostgreSQL and the completed backoffice view match.
- Request 1, previous correction: ticket `821d4b8e-a868-4d0b-b2d9-0adcf05eb84f`, described under Earlier output. Those fields were not edited.
- Request 2, informal accept, not rerun: ticket `d6e84c4a-74ab-415f-83aa-7000b9bab120`. Client Thames Valley University, UK, around 3,000 students, deadline `about 25 days, around August 28th`, budget null. Flesch-Kincaid 12.0. Gunning fog null, with the reason that `grade_level` was `college`. Summary includes GBP and a Data Processing Agreement referencing UK GDPR.
- Request 3, invalid reject, not rerun: ticket `a77d94f5-d6a7-4445-8a47-e533147da5c9` was `discarded` with no metadata or department sections.
- This turn: 29 passed, covering grounding, PHI, and the API intake tests. Classifier tests were not rerun. The classifier file was not changed.
- An upload before the parser fix, ticket `4dbbed19-213c-40d3-8df9-61b7e9145053`, stayed `analyzing` with code `model_output_invalid`. It was not relabeled.
- Stalled ticket `ab827ac1-535f-411d-9fbc-d823215034fb` remained `analyzing` from the earlier crashed run.

## Limitations

- Request 2's Gunning fog value is null because the scorer returned the label `college`. The numeric Flesch-Kincaid grade was stored. That PDF was not uploaded again after this correction.
- A discarded ticket does not get a metadata row, so its readability numbers are not stored. Valid RFPs do store both metrics.
- The summary still contains model sentences about a vendor type and a Data Processing Agreement. The clinical ask, the revenue contract-term ask, and the source-request budget attribution are present. The source requires the vendor to execute the Business Associate Agreement. Claire Whitfield is HealthCore's internal Compliance contact. The recorded summary attributes missing vendor preferences, additional BAA terms, and DPA information to department contacts. The source and recorded worker sections do not establish that those people supplied or withheld that information. These are unsupported model attributions, not verified source facts.

## Audit

Audit report: https://github.com/DAC-004/ai-engineering-company-project-monorepo-DanielCruz/blob/feature/rfp-intake/docs/rfp/part1-pre-pr-audit.md
