# Task 5: traceable monthly financial close

The financial-close agent ingests the briefing’s fictional CSVs, uses model-selected Decimal tools, and produces the seven-section report with producing-record lookup. Missing software and quarantined patient-name rows remain incomplete. The fallback summary derives missing inputs and relevant deviations from the actual facts.

Tom receives an internal version/hash-bound review request before distribution. Initial and revised draft delivery is atomic with persistence; rejected comments carry into a new version. Named Tom approval atomically queues exactly seven internal notices. Replays cannot duplicate drafts or notices. No external communications occur.

## Report structure

Executive summary (at most five lines); consolidated USD actual/budget revenue, expenses and result; revenue by country/payer in local currency; country expenses; relevant deviations with evidence-backed hypotheses; missing/uncertain data; traceability annex. Missing amounts are never treated as zero.

## Calculation tools

`ingest_and_normalize`, `aggregate_lines`, `actual_versus_budget`, `convert_gbp_usd`, `select_relevant_deviations`, `completeness`, `lookup_sources`. Arithmetic and inclusive absolute 5% selection are deterministic. The single agent plans tools and writes guarded hypotheses; it does not calculate numbers.

## Examples and source review

- [Canonical closing report](examples/canonical-october-2026.md), with its JSON figure/source graph.
- [Incomplete operations report](examples/missing-operations-october-2026.md), explicitly deterministic fallback.
- [Requirement matrix](SOURCE-COMPLIANCE.md) and [current validation](review-validation.json).

## Verification

93 financial-close tests; 32 federation and 60 auth/onboarding compatibility tests; full UI TypeScript, full ESLint, 78 Jest tests and isolated production build. Actual existing local GGUF tool plan, used FX results and both source-grounded hypotheses pass. Fresh real worker/beat verifies review/rejection/version-2 approval and seven recipients without duplicates. All are source-bound isolated runs; overlapping historical counts are not added. Historical browser proof is labelled in README and is not a current-code rerun. No existing services were stopped or redeployed.

## Review gates

Leadership sign-off and Daniel’s Task 5 merge approval remain pending. This is an open draft for review, not merge authorization. Synthetic aggregate data and internal notices only; no financial transaction or real email/SMS. Cursor did not commit.
