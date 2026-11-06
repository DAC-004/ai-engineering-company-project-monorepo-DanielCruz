## Summary

Task 4 adds a supplier-contract supervisor in this worktree on
`feature/supplier-contracts`. A supervisor consults pricing and contracts
specialists, then answers Operations questions without a send-to-supplier
tool.

The model plans allowlisted tools and selects specialist fact IDs through the
existing configured transport `data.pipelines.rag._run_generation_model` and a
Task 4 system prompt. It does not call `generate_answer` and does not change
the RAG coordinator prompt. Decimal math, PDF extraction, DPA status, and
named-approval gates stay deterministic. Keyword routing is fallback only.

Named approvers Marcus, Claire, and Sandra resolve from authenticated
identity plus existing role/department helpers. Drafts persist with version,
content SHA-256, and a rotating nonce. `GET /supplier-contracts/drafts` and
`GET /supplier-contracts/drafts/{id}` return only drafts the caller is
required to approve. The tracker page reviews body/state/granted and sends
CAS fields internally. Missing DPA blocks brief/draft immediately and
enqueues an internal Claire alert. Beat/worker ticks remaining internal
alerts. External transports stay off.

This local description supports the authorized supervisor commit/push and draft PR for Daniel review. Real Operations sign-off and Daniel approval remain required before merge. Cursor must never commit.

## How to test

Isolated non-live pytest uses the reviewed precollection bootstrap (owned
SECRET_KEY, DATABASE_URL, TINYDB_PATH, supplier-contract stores, eager
Celery, no live credentials, no real broker). Current result:

`C:\Users\cruzd\Documents\Codex\2026-11-04\task\task4-api-review-lkz7mnx3\result.json`

53 passed in 44.17s, exit 0, `source_changed[]`, JUnit 0 fail / 0 error / 0
skip. Runner SHA256
`9f1075ed4db59c30e816da5db1109f25724d119db0b9f2267fe887cfacfc1193`. Do not
rerun that selection unless source changes. Do not add earlier overlapping
pytest counts (46-test run, 30-test affected run, 14-test mocked
model-boundary run, or the 53-test run that had one fixture failure) to this
53.

Live GGUF is a separate one-question Supervisor proof, not those 53 tests:
host TEMP `healthcore-task4-reviewed-live-generation/run-20261106T140710Z-074e81ef`,
plan and write `source=model`, exact HC-S01 notice deadline `2027-03-06`.

Owned local runtime (do not start a duplicate): API `127.0.0.1:8030`, UI
`127.0.0.1:3030`, Redis `healthcore-task4-redis-6382` on `127.0.0.1:6382`.
Preserve original 3000/8010, Task 2 3011/8011, Task 3 3020/8020, and Redis
6379/6381.

Browser on that runtime (already collected, do not duplicate here):

- HC-S03 alternatives: Lone Star Diagnostics quote 17.20 and hypothetical
  annual difference 61800.
- HC-S07 internal communication: Marcus approve pending, logout, Claire
  retrieves the same persisted draft, Claire approve, state approved,
  `sent=false`. Evidence
  `task4-live-services-91576a3e/browser-s07-approved.jpg` and
  `browser-s07-approval-evidence.json`.

Autonomous worker on owned 6382: 211+ ticks, first 9 unique internal alerts,
then 0 duplicates, no HTTP `/tick`.

DPA and remaining-role browser on the same runtime is closed:

- `browser-dpa-marcus-evidence.json`: Marcus HC-S06 brief blocked, zero
  Confirm controls.
- `browser-dpa-claire-evidence.json` and `browser-dpa-confirmed-claire.jpg`:
  fictional Claire explicit confirmation; post-confirm brief returned;
  extracted DPA remains missing; no signed-DPA claim.
- `browser-employee-evidence.json`: Employee zero Approve/Confirm and no
  assigned drafts.

Worked HC-S06 brief sources: `prices.csv` data rows 71/72 excluding header,
`(14.79-14.50)*700*12 = 2436` GBP, FX 1.27 => 3093.72 USD; CT-HC-03 page 1
clause 4 cap 3 percent allows 14.935 GBP; clauses 2/3 expiry 2027-06-04,
notice 90 days, deadline 2027-03-06; clause 5 exit 90 days no penalty;
clause 6 DPA missing despite fictional proceed; clause 8 annual 121800 GBP
=> 154686 USD, required Marcus and Claire.

Backend hashes for the 191 Task 4 sources still match the 53-pass run. Full UI TypeScript (including tests), scoped ESLint and isolated production build pass (exit 0); the complete UI Jest suite passes 63/63 tests. The shared TS2352 auth fixture is corrected with a real plain-text 503 Response, preserving the non-JSON safe-error assertions. Production sources and configuration are unchanged.

## Out of scope for this PR

- Git commit, push, or opening the pull request
- Real Operations sign-off
- Copying Task 3 production changes
- Weakening DPA or Sandra-on-unknown-annual gates
- Treating model-source flags alone as live acceptance
