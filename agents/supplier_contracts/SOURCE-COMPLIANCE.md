# Task 4 source compliance review

Source of truth: all three files in the supplied `.project_specs/Task 4` folder. Their SHA-256 values are in [review-validation.json](review-validation.json). The original assignment image was visually read; its printed checkboxes are not execution evidence.

This review integrates approved Task 2 and Task 3 main without merging Task 4. No other task is under review here.

| ID | Requirement | Implementation and executed evidence |
|---|---|---|
| I1 | Supplier registry and 12-month price ingestion retain row sources | registry.py; pricing.py; seed.py; pricing/model-boundary tests |
| I2 | PDF expiry, notice, revision, exit and penalties extracted | contracts.py; pdf.py; questions/annual-value tests |
| I3 | Every extracted term carries clause, page and PDF hash | contracts.py; alert provenance/source-review tests |
| I4 | Low-confidence or contradictory terms are uncertain | contracts.py; negative BAA, wrong-jurisdiction and patient-registry regressions |
| I5 | Price history by supplier/product/service | pricing.py; registry.py; 84-row fixture evidence |
| I6 | Strictly greater than 4 percent alerts | pricing.py; alerts tests; real scheduled nine-alert proof |
| I7 | Volume-based deterministic annual financial impact | pricing.py; Decimal tests and fixture review |
| I8 | Same-country, same-category alternatives; quote only, no assumed availability | pricing.py; questions/model-boundary tests |
| I9 | Contract permission answers cite clauses | contracts.py; facts.py; questions tests |
| I10 | Detected increases automatically evaluated against cap/CPI | supervisor.py; contracts.py; fixture review |
| I11 | Expiry 90/30 and notice 15-day alerts | alerts.py; runtime.py; scheduler and stale-calendar regressions |
| I12 | Supervisor interprets, consults and combines typed specialist results | ARCHITECTURE.md; generation.py; live local GGUF proof |
| I13 | Increase combines contract allowance and financial impact | supervisor.py; model-boundary/annual-value tests |
| I14 | Brief combines history, alternatives, impact and contractual leverage | supervisor.py; facts.py; adversarial writer-selection regression |
| I15 | Consultations capped at four | supervisor.py; portfolio and model-boundary tests |
| I16 | Deterministic price, impact, comparison and GBP/USD conversion | pricing.py; constants.py; fixture/model-boundary tests |
| I17 | Response/brief figures and clauses trace to source | facts.py; source-review test; alert provenance |
| I18 | Missing facts stated explicitly and cannot be dropped by writer | facts.py; missing contract/date/price regressions |
| I19 | No supplier send tool; drafts require approval | approvals.py; authenticated API/CAS/replay tests; historical approval UI |
| I20 | Marcus always; Claire for patient processing; Sandra above USD500k or unknown | actor.py; approvals.py; annual-value/auth API tests |
| I21 | Separate agent identities and specialty tools | identity.py; ARCHITECTURE.md; typed requests/results and allowlists |
| I22 | Agent-labelled audit for specialist, supervisor and approval actions | audit.py; supervisor.py; privacy/approval tests |
| I23 | Patient data rejected; bank/contact fields excluded from context/logs/output | privacy.py; pdf.py; privacy and draft-payload tests |

The ten evaluation criteria map respectively to I12/I21, I6/I10/I13, I14, I3/I17, I16, I11, I19/I20, I18, I23, and the written architecture rationale in ARCHITECTURE.md.

## Company-specific checks

Seven exact registry entries and four fictional numbered English PDFs are retained. Canonical fixtures have 84 monthly rows, the final month at the load date, and GBP/USD 1.27. S01 increases 4.5% (allowed by 5% cap); S03 increases 7% (exceeds CPI 2.9%); S06 increases 2% (allowed by 3% cap) but lacks a DPA; S07 remains fixed-price. Same-country/category alternatives remain quotes. Annual values come from contract clause 8; missing or uncertain values conservatively require Sandra. Patient processors require the jurisdiction-appropriate signed BAA/DPA. Claire may explicitly proceed despite absence, but that acknowledgement is bound to the exact reviewed PDF/absence snapshot and never changes the extracted missing-agreement status.

## Corrections from this review

Twelve focused regression cases cover contradictory/negated/wrong-jurisdiction agreements; PDF-bound proceed confirmations including explicit absent contracts; stale calendars; advancing service date; portfolio missing-agreement questions; alert provenance; retention of required brief content and missing-data statements; and preserving both Task 3 and Task 4 schedules. The initial nine counterexamples all failed before correction. No requirement was relaxed to obtain a pass.

## Current execution and limits

See review-validation.json for exact isolated run paths, source hashes and JUnit results: 65 Task 4 tests; separate local GGUF notice proof; real worker/beat nine-alert proof with repeated-tick deduplication; combined auth/onboarding compatibility; full UI typecheck, lint, 72 Jest tests and isolated production build. Do not add overlapping historical counts.

Historical browser evidence remains labelled in README; it is not a current-code browser rerun. Current authenticated API regressions cover named approvals, missing-DPA confirmation and CAS. No external messages, real provisioning, financial transaction, deployment or production reliability claim is made.

## Submission and approval gates

Draft PR #42 is the submission. Architecture diagram, typed I/O, rationale, increase example and traceable brief are in ARCHITECTURE.md and PR-DRAFT.md. Operations leadership sign-off and Daniel’s specific Task 4 merge approval remain pending. Task 4 must not be merged before both are satisfied.
