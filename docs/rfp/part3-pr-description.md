# Part 3: Approval and completion

Part 3 continues the same RFP ticket from Part 2. Each HealthCore department pauses on its own checkpoint thread, `rfp-{ticket_id}:{department}`, until that department's demonstration account approves, rejects, or requests changes. The other departments are not blocked. When revenue, clinical, and compliance are approved, the stored drafts match their approval hashes, and PHI, BAA/DPA, currency, and any established capacity conflict are clear, the service writes the final document and sets the ticket to `done` in the same commit.

Conflict arbitration is a deterministic node. Claire Whitfield's account handles PHI and BAA/DPA mismatches. Tom Callahan's account chooses `reduce_covered_population` or `add_sites` only after those regulatory triggers are clear. The choice does not accept a new headcount. A capacity conflict that was already detected stays unresolved if a later revision drops the coverage sentence.

## How to test

Simulated path, from the repository root:

```powershell
uv run --project services/api --python 3.13 python -m pytest tests/pipelines/test_rfp_approval.py tests/pipelines/test_rfp_arbitration.py tests/pipelines/test_rfp_approval_e2e.py services/api/tests/test_rfp_approval_api.py -q
```

The simulated example below is not the live browser session. The live Meridian upload, the initial ticket load, the departmental sign-ins, and the stored final document are recorded separately in [docs/rfp/part3-testing.md](docs/rfp/part3-testing.md). Auth reads and writes share one locked TinyDB handle so the first ticket load does not fail while another request writes that file.

The curriculum PDF is not in this branch.

## Input RFP

This is the intake converter's transcription of `CONTEXT-healthcore-request-1.pdf` (Meridian Manufacturing). The list marker is the converter's `(cid:127)` glyph.

```text
REQUEST FOR PROPOSAL (RFP)

On-Site Occupational Health & Corporate Wellness Program

RFP Reference No.: MM-OH-2026-002

Issuing Organization: Meridian Manufacturing, Inc.

Date Issued: August 3, 2026

Proposal Due Date: August 23, 2026

1. Background

Meridian Manufacturing operates an 800-employee manufacturing facility in Austin, Texas. We are
seeking a healthcare partner to provide on-site occupational health services and a corporate wellness
program for our workforce.

2. Scope of Work / Services Requested

(cid:127) On-site occupational health clinic staffed 3 days/week

(cid:127) Injury and illness triage and treatment for workplace incidents

(cid:127) Annual wellness screenings for all 800 employees

(cid:127) Chronic condition management support (diabetes, hypertension)

(cid:127) Contract term: 12 months, with option to renew

(cid:127) Vendor must be able to execute a Business Associate Agreement (BAA) in compliance with
HIPAA prior to contract execution

3. Evaluation Criteria

Criterion

Clinical capacity and staffing plan

Compliance and data security practices

Pricing

References from similar manufacturing clients

4. Timeline

Milestone

RFP issued

Questions due

Weight

35%

25%

25%

15%

Date

Aug 3, 2026

Aug 10, 2026

Proposals due

Award notification

Aug 23, 2026

Sep 7, 2026

5. Submission Instructions

Proposals must be submitted electronically to procurement@meridianmfg.com no later than the
proposal due date listed above. Late submissions will not be considered.

6. Contact

Rebecca Ortiz
VP of Human Resources, Meridian Manufacturing
Meridian Manufacturing, Inc.
```

## Simulated departmental approvals

Produced by [tests/pipelines/test_rfp_approval_e2e.py](tests/pipelines/test_rfp_approval_e2e.py) for ticket `ticket-e2e`. Generation is stubbed. These calls are not the live UI session.

| Department | Decision | Recorded approver | Submitted by |
| --- | --- | --- | --- |
| clinical | approve | Dr. Marcus Reid | user-clinical |
| revenue | approve | Tom Callahan | user-revenue |
| compliance | approve | Claire Whitfield | user-compliance |

Clinical was approved while revenue was still interrupted. The final document was written only after compliance approved.

## Final document from that test

```json
{
  "ticket_id": "ticket-e2e",
  "sections": [
    {
      "department_id": "revenue",
      "draft_content": "Pricing is quoted in USD for the occupational health program. Payment follows the twelve month contract already stated."
    },
    {
      "department_id": "clinical",
      "draft_content": "Clinical Operations can staff the occupational health program. The covered population was stated as 800 employees."
    },
    {
      "department_id": "compliance",
      "draft_content": "The compliance section includes a Business Associate Agreement clause for this United States client."
    }
  ],
  "currency": "USD",
  "generated_at": "2026-09-30T16:47:24.537523+00:00"
}
```

## Review

Please review this Part 3 approval and completion branch.
