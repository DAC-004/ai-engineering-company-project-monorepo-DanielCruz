# Supplier and contract supervisor

Operations needs price history and contract terms in one answer. Prices and
contracts are different sources and tools, so a supervisor consults two
specialists with typed I/O. The consultation cap of four is an implementation
limit, not HealthCore policy. There is no send-to-supplier tool.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the graph and specialist contracts.
The published draft is PR #42. Its review description is maintained in [PR-DRAFT.md](PR-DRAFT.md).

## Identities and tools

- Supervisor `supplier-contracts-supervisor`: consult pricing/contracts, compose a brief, draft an internal communication, enqueue internal alerts.
- Pricing `supplier-contracts-pricing`: Decimal CSV tools only. Never reads Supplier Directory `monthly_rate` floats.
- Contracts `supplier-contracts-contracts`: sanitized PDF terms with clause, page, and SHA-256.
- Alerts `supplier-contracts-alerts`: internal outbox only. Immediate missing-DPA enqueue on a blocked brief/draft; beat/worker ticks remaining notice, expiry, and price alerts. External transports stay off.

Named approvers are resolved from authenticated identity (`marcus.clinical@`,
`claire.compliance@`, `sandra.executive@`). Payload names are rejected.
Department access is not named approval. Employee accounts cannot approve.
Drafts bind version, content SHA-256, and a rotating nonce. Authenticated
`GET /supplier-contracts/drafts` and `GET /supplier-contracts/drafts/{id}`
return only drafts the caller is a required named approver for. The tracker
page loads that list after login or refresh and sends CAS fields internally.

## Model planner and deterministic specialists

The model interprets the staff question and selects fact IDs. It does not
perform arithmetic, invent citations, or author DPA/approval outcomes.

- Plan and write go through `generation.py` to the existing configured
  transport `data.pipelines.rag._run_generation_model` with a Task 4 system
  prompt. The adapter does not call `generate_answer` and does not change the
  patient-coordinator RAG prompt.
- Valid model JSON can choose allowlisted tools and optional fact-id order.
  Mandatory compliance, approval, and source blocks are always retained.
  Unknown catalog IDs fail closed to canonical specialist order.
- Decimal price math, PDF extraction, DPA status, and named-approval gates
  stay in deterministic code. Keyword routing in `routing.py` is a fallback
  when no transport is injected or the plan is unusable. Fallback is not live
  model evidence.
- Patient-labeled and out-of-scope input is rejected before the model,
  context assembly, or audit write.

## Local data

- Raw CSV and four English PDFs: `data/raw/healthcore-supplier-contracts/`
- Isolated projection/audit: `data/process/supplier-contracts/` (gitignored)
- Override with `SUPPLIER_CONTRACTS_RAW_DIR`, `SUPPLIER_CONTRACTS_PROCESS_DIR`, `SUPPLIER_CONTRACTS_LOAD_DATE`

Owned local Task 4 runtime (not original/Task 2/Task 3 listeners) used
`127.0.0.1:8030` API, `127.0.0.1:3030` tracker, and Redis
`healthcore-task4-redis-6382` on `127.0.0.1:6382`. That store is separate from
isolated pytest destinations.

## Current review (2026-11-07)

[SOURCE-COMPLIANCE.md](SOURCE-COMPLIANCE.md) maps all 23 implementation items and ten evaluation criteria to code and evidence. [review-validation.json](review-validation.json) records current source-bound executions. The corrected Task 4 suite passes 65 tests; separate actual local GGUF and real worker/beat checks pass. Combined UI verification passes full TypeScript, full ESLint, all 72 Jest tests and isolated production build. Compatibility results are recorded separately. Existing services remain untouched. Historical browser results below are not current-code browser evidence. Operations sign-off and Daniel Task 4 merge approval remain pending.

## Historical evidence (2026-11-06; superseded for current source)

Current full non-live pytest, isolated bootstrap, no live model, no real
broker: `C:\Users\cruzd\Documents\Codex\2026-11-04\task\task4-api-review-lkz7mnx3\result.json`,
53 passed in 44.17s, exit 0, `source_changed[]`, JUnit 0 fail / 0 error / 0 skip,
runner SHA256 `9f1075ed4db59c30e816da5db1109f25724d119db0b9f2267fe887cfacfc1193`.
That selection supersedes earlier narrower non-live pytest counts for current
behavior (including the 46-test run, the 53-test run that had one fixture
failure, the 30-test affected run, and the overlapping 14-test mocked
model-boundary run). Do not add those counts together.

Separate evidence, not included in the 53:

- Live GGUF Supervisor notice proof: host TEMP
  `healthcore-task4-reviewed-live-generation/run-20261106T140710Z-074e81ef`,
  1 passed, exact HC-S01 `notice_deadline` `2027-03-06`, `plan_source=model`,
  `write_source=model`, contracts consulted. Not a browser or worker claim.
- Fixture/PDF extraction: `task4-fixture-review-ta8kz_a5`, 25/25. Visual page
  inspection, not the pytest suite above.
- Browser, owned runtime `task4-live-services-91576a3e`: HC-S03 comparison
  returned Lone Star Diagnostics quote `17.20` and hypothetical annual
  difference `61800`. HC-S07 internal draft two-person named approval through
  normal login switch, `sent=false`, screenshot `browser-s07-approved.jpg`.
- DPA and remaining-role browser, same runtime, now closed:
  `browser-dpa-marcus-evidence.json` (Marcus S06 brief blocked, zero Confirm
  controls); `browser-dpa-claire-evidence.json` and
  `browser-dpa-confirmed-claire.jpg` (fictional Claire explicit confirmation,
  post-confirm brief returned, `missing_dpa` remains true, no signed-DPA
  claim); `browser-employee-evidence.json` (Employee zero Approve/Confirm and
  no assigned drafts).
- Autonomous worker on owned 6382: 211+ ticks, first 9 alerts then 0
  duplicates, no HTTP `/tick`. External transports disabled.

Backend hashes for the 191 Task 4 sources still match the 53-pass run. Full UI TypeScript (including tests), scoped ESLint and isolated production build pass (exit 0); the complete UI Jest suite passes 63/63 tests. The shared TS2352 auth fixture is corrected with a real plain-text 503 Response, preserving the non-JSON safe-error assertions. Production sources and configuration are unchanged.