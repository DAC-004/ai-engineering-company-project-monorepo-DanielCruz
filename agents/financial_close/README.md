# Monthly financial close

Task 5 closes the last full calendar month before the load date using read-only financial CSV tools. For the supplied 6 November 2026 load, that is October 2026. Amounts and signed/percentage deviations use Decimal arithmetic; relevance is inclusive at absolute 5%. GBP consolidates at the briefing rate of 1.27 USD.

Missing software entries and quarantined transactions remain missing/incomplete. They are never zero-filled. Payroll is country-level aggregate data. Patient/employee identifiers and raw sensitive descriptions are excluded before generation; Claire receives affected entry IDs only.

## Tools and generation

| Allowlisted tool | Responsibility |
|---|---|
| ingest_and_normalize | Validate source files, dates, currencies, signs, duplicates and sensitive records |
| aggregate_lines | Aggregate verified country/category/payer amounts |
| actual_versus_budget | Compute signed amount and percentage deviations |
| convert_gbp_usd | Apply the source-traced fixed exchange rate |
| select_relevant_deviations | Select complete lines at the inclusive threshold |
| completeness | Preserve missing/uncertain status |
| lookup_sources | Resolve producing records and source-figure links |

The actual model selects tools. Mandatory ingest/dependencies and deterministic fallback are recorded separately. The Task 5 adapter reuses the existing local model transport; it does not modify the patient-coordinator prompt. A filled JSON template preserves labeled evidence and status while the model supplies bounded possible-cause explanations. The target is 3-8 words, with a hard cap of 12; summary stays capped at 8 words. Exact evidence, source-driver direction, identifiers, numerical grounding and privacy are checked before use. One validated retry is allowed. Placeholders, invented figures, unsupported volume/efficiency claims and truncated JSON are rejected. Code labels accepted causes `Hypothesis (not proved causality)`; model prose is never proof of causation.

## Workflow and review

`POST /financial-close/run` queues a job and returns 202 with minimal job metadata. Durable period/source claims prevent duplicate drafts. Rejection atomically inserts a successor and advances the saved report reference. Replay also reconciles legacy references so an approved successor cannot resolve to its rejected parent.

Only the active named Tom identity, supervisor role and revenue-cycle department together can decide. Approval binds version/hash/nonce and atomically creates seven unique internal notices. Named recipients can read the approved report; ordinary employees cannot. No real email or SMS is sent. Human leadership and Daniel's branch review remain pending.

The scheduler uses 06:00 America/Chicago on the third business day. Weekdays are the explicit default; holidays are configurable. Later-day execution is marked catch-up. Enable the daily due-check with `FINANCIAL_CLOSE_ENABLE_CRONTAB=1`; the isolated acceptance run used a 10-second sweep to observe real worker/beat behavior. Original services and real data were preserved.

Tracker route: `/backoffice/financial-close`. It renders seven sections, missing/subtotal labels, source hashes and producing figure IDs, reviewer feedback and version-bound decisions.

## Deliverables and evidence

- [Canonical model-generated example](examples/canonical-october-2026.md) and matching JSON.
- [Additional missing-operations example](examples/missing-operations-october-2026.md), explicitly deterministic fallback, and matching JSON.
- [Validation evidence](examples/validation.json) and [source compliance](SOURCE-COMPLIANCE.md).
- Three canonical fictional CSVs and their byte-level `fixture-manifest.json` in `data/raw/healthcore-financial-close/`. The narrow Git attributes rule preserves tested CSV bytes.

Final checks: 89 non-live tests; six UI behavior tests; scoped lint and production TypeScript; source-identical isolated production build; actual local Qwen2.5-3B planner/writer and FX proof; real worker/beat/restart/replay; normal browser reject/revise/approve/source lookup and employee denial. Full UI TypeScript (including tests), scoped ESLint and isolated production build pass (exit 0); the complete UI Jest suite passes 69/69 tests. The shared TS2352 auth fixture is corrected with a real plain-text 503 Response, preserving the non-JSON safe-error assertions. Production sources and configuration are unchanged. Overlapping test runs are not added.

Run tests only with isolated raw/process/auth/database/broker paths. Live generation is separately opt-in with `FINANCIAL_CLOSE_LIVE_GENERATION=1` and the existing local GGUF; it must prove actual tool selection, used conversion results and both grounded model explanations. Do not load real `.env` files or use real identities for acceptance fixtures.
