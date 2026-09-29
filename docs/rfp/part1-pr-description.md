# Pull request title

Add HealthCore RFP intake and routing (Part 1)

# Pull request description

## Summary

- Part 1 RFP intake is added to the existing FastAPI service and the talent-pipeline-tracker backoffice. The graph is in `data/pipelines/rfp_intake/`. There is no second HTTP service.
- A PDF upload returns 202 with status `analyzing`. The pipeline converts the PDF to Markdown, classifies it, and either discards that ticket or routes it through separate revenue, clinical, and compliance workers. The synthesizer summary, department key aspects, and Part 2 handoff are stored in PostgreSQL.
- Generation uses the local Qwen GGUF. A missing model leaves the ticket `analyzing` with `processing_failed`. A process that dies is reported as stalled without rewriting the stored status.

## Test plan

- [ ] From the repository root, run `uv run --project services/api --python 3.13 python -m pytest tests/pipelines/test_rfp_classifier.py tests/pipelines/test_rfp_phi.py tests/pipelines/test_rfp_worker.py tests/pipelines/test_rfp_grounding.py services/api/tests/test_rfp_intake_api.py`
- [ ] Start the API with Python 3.13, `DATABASE_URL`, and the local GGUF available through `RAG_MODELS_DIR` or `data/process/models/`. Start the backoffice with `NEXT_PUBLIC_API_BASE_URL` pointed at that API.
- [ ] Sign in to the backoffice, open RFP intake, and upload a PDF with the file input. Confirm the page moves to the new ticket and reaches `intake_complete` or `discarded` without a manual reload.
- [ ] Read the ticket, metadata, department sections, and `part2_handoff` from PostgreSQL in a separate session.

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

Recorded PostgreSQL read-back for ticket `a95ac8df-c797-4f60-99f9-d56f3f2221c1` after the final grounding run. This is the stored result, not an expected-result substitute. The first completed backoffice view showed the same client, sections, and summary without a manual reload.

Ticket

- ticket_id: a95ac8df-c797-4f60-99f9-d56f3f2221c1
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

- No budget information provided
- No payment terms provided

Open questions:

- Is there a specific budget allocated for the On-site Occupational Health clinic?
- Are there any payment terms or deadlines for the annual wellness screenings?

Synthesizer summary

The Revenue Cycle section of the Meridian Manufacturing, Inc. program requires clarification on the budget allocation and payment terms for the annual wellness screenings. Tom Callahan, the Revenue Cycle contact, has not provided specific budget figures or payment terms. It is important to determine if there is a specific budget allocated for the On-site Occupational Health clinic and if there are any payment terms or deadlines for the annual wellness screenings. US client: quote in USD and include a Business Associate Agreement.

Part 2 handoff

- handoff ticket_id: a95ac8df-c797-4f60-99f9-d56f3f2221c1
- phi_detected: false
- compliance_review_required: false
- metadata, readability, sections, and synthesizer_summary: the same values recorded above

## Match summary

This paragraph is a summary of the comparison. It is not additional output.

The stored client, population, proposal due date, clinic schedule, wellness screenings, chronic-condition support, injury triage, and HIPAA Business Associate Agreement requirement come from the sample. The sample states no budget, and the stored budget is null with a revenue open question. The sample does not label a patient, and the stored ticket has `phi_detected` false. The output does not restate the RFP reference number, the August 3 issue date, Austin, the 12-month term, the evaluation weights, the August 10 question deadline, the September 7 award date, the procurement address, or Rebecca Ortiz.
