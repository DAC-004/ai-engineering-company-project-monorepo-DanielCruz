# Section 3 and section 5 search

Date executed: 2026-10-08, repeated for the ZIP (8) review. Branch: `feature/nist-security-practices`. HEAD: `38a0806bcc2fc3106aa4e4f969fd893e87953d02`.

`CONTEXT-healthcore.md` section 3 lists the clinical documentation assistant, automated referral workflow, RAG over clinical protocols, compliance agent, and access audit log. Section 7 adds the clinical KPI dashboard and the staff frontend. Section 6 says the report must include that inventory and must confirm the section 5 actions in the current implementation. `project_specs.md` asks for an inventory of the AI systems built so far. Neither source says to build a missing clinical product in this audit.

## Expressions and results

The search tool was `rg -n` with globs `*.py`, `*.ts`, and `*.tsx`, from the repository root. A no-match result means these expressions found no line. It does not by itself prove that every possible implementation name is absent.

| Expression | Result |
| --- | --- |
| `def .*(sign_\|send_note\|notify_\|share_history\|update_referral\|update_appointment)` | No matches. |
| `SOAP\|soapNote\|notifyPatient\|labResult\|chartAccess\|kpiDashboard` | No matches. |
| `referral status\|appointment status` | No matches. |

The raw capture is `docs/nist/evidence/2026-10-08-component-search-raw.txt`.

A separate expression, `sampleAppointments|generateOperationalReports`, does match. Those matches are Milestone 2 sample reporting, not a section 5 status change:

- `uis/backoffice/app/page.tsx` lines 4-8 import `sampleAppointments` and call `generateOperationalReports`. Lines 41-43 render `sampleAppointments.length`. Lines 75-79 render the returned JSON.
- `src/utils/transformations.ts` `generateOperationalReports` returns `generateCareRequestReports` and `generateAppointmentReports`. `generateAppointmentReports` counts by status and clinic name. It does not write a new status.

`src/data/sample.ts` holds the sample appointment records, including `status: 'Scheduled'`. That file also holds care-request contact fields. It is not copied into this evidence note or the review ZIP. The page source that renders the counts is in the ZIP.

## What the file reads add

RAG and compliance answers are `data/pipelines/rag.py` and `services/api/app/agent/`. `docs/company-knowledge-base/healthcore-referral-process.en.md` is policy text. `services/api/app/agent/decision_log.py` records an agent action, reason, route, and trace id. `origin/feature/sse-notifications` at `969e5d2` is not an ancestor of this HEAD.

The no-match expressions plus these file reads support the inventory statement that this tree has no SOAP generator, patient notifier, history-share function, chart-access writer, KPI dashboard, or referral or appointment status route. The no-match lines alone are the weaker statement. The page and transformation reads are the stronger statement for the appointment surface: the code that mentions appointments counts sample rows and does not change one.
