# Task 5 current source compliance review

All three supplied `.project_specs/Task 5` files were read, including the assignment image. Their hashes and current execution records are in [review-validation.json](review-validation.json). Printed checkboxes are not test evidence. Approved Tasks 2–4 main is integrated at `bbc8810f665bc4dfa84aed54088aa69beb535e7c`; Task 5 remains unmerged.

| ID | Source requirement | Implementation and executed evidence |
|---|---|---|
| I1 | Ingest exact ledger, budget and operations CSVs | ingest.py; canonical fixture/source/schema contracts |
| I2 | Normalize while retaining source row/hash/entry identity | ingest.py; source/traceability contracts |
| I3 | Incomplete and inconsistent records remain uncertain | consistency/source/schema contracts; missing example |
| I4 | Deterministic totals, actual/budget, signed absolute/percent deviation and FX | money.py; tools.py; tools/grounding contracts |
| I5 | Every calculation tool has automated coverage | tools/schema/source/grounding contracts; actual model FX proof |
| I6 | Same input/period produces identical figures | tools/workflow/replay contracts; no mutable source writes |
| I7 | Single agent chooses allowlisted calculation tools | agent.py; CalculationToolbox; real parsed model plan |
| I8 | Inclusive absolute five-percent relevance | money.py; tools tests; exact threshold contracts |
| I9 | Relevant deviations use evidence-backed, explicitly hypothetical explanations | generation.py; serialize.py; actual Medicare/laboratory model proof |
| I10 | Seven required report sections and country/payer breakdown | serialize.py; current canonical example; 78 UI tests/build |
| I11 | Missing/uncertain data declared without zero fill | current missing-ledger regression; current missing-operations example |
| I12 | Every figure links to source records or producing figures | serialize.py; traceability contracts; figure annex |
| I13 | Reviewer can look up source of any figure | authenticated source lookup; source-ID UI; historical browser proof |
| I14 | Background close on third business day at 06:00 Austin | calendar/schedule contracts; fresh real beat/worker proof |
| I15 | Report delivered to Tom before distribution | atomic internal review_request on initial/revised drafts; rollback/replay tests |
| I16 | Tom approve/reject with comments; rejection creates successor | review.py; current real worker/store revision proof; API CAS tests |
| I17 | Approved distribution restricted to seven named recipients | atomic approval outbox; interruption regression; current seven-recipient worker proof |
| I18 | Dedicated automated identity; read-only finance sources | identity.py; audit.py; fixture/source immutability checks |
| I19 | Every automated action audited | agent/schedule/review audit records; workflow and worker evidence |
| I20 | No patient data, individual salaries or bank details downstream | privacy/ingest/model-boundary/source contracts; model/process privacy scans |

The eight evaluation criteria map to I12/I13, I4/I5, I6, I8/I9, I11, I15/I16/I17, I18/I19 and I20 respectively.

## Company-specific acceptance

Canonical fixtures retain the exact four revenue and ten expense budgets, specified actuals and eight operations metrics. Each line has several aggregate ledger entries; UK software has none. The intentional fictional patient-name row is quarantined and represented only by entry_id; Claire receives only that ID. Actual source files remain read-only. Payroll is country aggregate. GBP converts at 1.27. Medicare -10% and US laboratory +7% are relevant; consumables +4.5% and UK private about +4.2% are below threshold. Missing software is not zero or -100%. Reports retain all seven sections, no more than five summary lines, sources and uncertainty. Only active named Tom with supervisor/revenue-cycle identity reviews. Approval produces exactly the seven briefing recipients; no real email/SMS is sent. Weekdays are the explicit business-day default because the briefing names no holiday calendar; holidays remain configurable.

## Gaps closed in this review

The fallback summary now derives relevant deviations and missing inputs from current facts rather than hardcoding the canonical example. Initial and revised reports now enqueue an explicit version/hash-bound internal review notice for Tom in the draft transaction, including fault rollback and replay deduplication. Shared routes/navigation and all three task schedules are preserved. No check or source requirement was weakened.

## Current evidence and limits

93 Task 5 non-live tests pass. Combined UI full TypeScript, full ESLint, 78 Jest tests and isolated production build pass. Separate 32 federation and 60 auth/onboarding tests pass. The actual local GGUF model selects tools, uses the FX result and supplies both evidence-grounded hypotheses. Fresh real worker/beat creates the awaiting draft, preserves rejection feedback on approved version 2, queues internal review notices and seven approved recipients without duplicate drafts/notices. Exact source manifests are retained. Do not sum overlapping historical counts.

Historical normal-browser and restart proofs are preserved in README; they are not current-code browser reruns. Fresh worker uses explicit deterministic transport injection, and actual model is a separate proof. Current authenticated API checks cover approval and source access. This is fictional acceptance evidence, not production deployment or universal model correctness. Existing services and real data remain untouched.

## Submission gates

PR #43 includes report structure, calculation tool list, current canonical and missing-operations examples with traceability. Leadership sign-off and Daniel’s separate Task 5 merge approval are pending. Do not merge before approval. Cursor does not commit; supervisor publication is authorized.
