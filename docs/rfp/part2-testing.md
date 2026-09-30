# Part 2 response generation: testing

Part 2 starts from a ticket that Part 1 already stored as `intake_complete` with `part2_handoff`. `POST /rfp/tickets/{ticket_id}/response` returns 202 and status `drafting`. It does not read the PDF. Revenue, clinical, and compliance each draft from shared metadata and that department's `key_aspects`. Readability, relevance, and compliance run in parallel for a section. A section gets three attempts. An exhausted section stays on the ticket as `needs_human_review` with its latest redacted draft and evaluation. `part3_handoff.response_complete` is written only after all three departments finish. A fully passing ticket stays `under_evaluation`. A ticket with any provisional section becomes `needs_human_review` in that same completion write. Part 3 approvals, a final document, and arbitration are not implemented.

The local model file `qwen2.5-3b-instruct-q4_k_m.gguf` was not present for this audit. Pipeline tests inject a completion function. The PostgreSQL read-back used that same service path, not a live model call.

## Checks

From the repository root, with Python 3.13:

```text
uv run --project services/api --python 3.13 python -m pytest tests/pipelines/test_rfp_classifier.py tests/pipelines/test_rfp_worker.py tests/pipelines/test_rfp_grounding.py tests/pipelines/test_rfp_phi.py tests/pipelines/test_rfp_response_readiness.py tests/pipelines/test_rfp_generator.py tests/pipelines/test_rfp_evaluator.py tests/pipelines/test_rfp_response_loop.py services/api/tests/test_rfp_intake_api.py -q
```

Recorded run of that command, before the UK test and the second URL test existed: 51 passed. That count is not a later combined rerun.

A separate run then passed these three tests only: `test_uk_compliance_requires_gbp_and_a_dpa_referencing_uk_gdpr`, `test_database_url_quotes_a_reserved_character_in_the_password`, and `test_database_url_preserves_valid_ports_and_an_encoded_password`.

A later API check, `test_exhausted_revenue_section_sets_ticket_needs_human_review`, uses the same SQLite service path as the other API tests. It is not part of the 51-test run and it is not the PostgreSQL read-back. The response starts as `drafting`. After revenue exhausts three attempts, the stored ticket is `needs_human_review`, the revenue draft and failed evaluation remain, and clinical and compliance still pass. `waiting_for_approval` and `done` are not set.

`services/api/.env` is gitignored. `DATABASE_URL` is loaded from that file and is not printed. The configured host is the direct Supabase database host. Port 6543 on that host timed out. The direct host accepts connections on port 5432, and `_normalize_database_url` uses 5432 for that host only. A transaction-pooler host on port 6543 is left unchanged.

The read-back opened `init_databases`, ran `begin_response` and `run_response` through SQLModel, disposed the engine, and read the ticket in a new session. Dialect was `postgresql`. Status was `under_evaluation`, `response_complete` was true, and revenue, clinical, and compliance each had a draft and an evaluation with `department_id`, `readability`, `relevance`, `compliance`, `overall_pass`, `feedback_for_generator`, and `contains_phi`. The probe ticket was deleted after that read.

## Passing section

This revenue draft is the passing fixture in `tests/pipelines/test_rfp_evaluator.py`. Flesch-Kincaid grade is 9.0. For a US client it states USD, the twelve-month term, and no invented headcount. Evaluation `overall_pass` is true.

```text
HealthCore proposes a twelve month occupational health agreement for Meridian Manufacturing in Austin. Revenue Cycle will quote the commercial terms in USD. Payment is due monthly in arrears after each service month under the written schedule. The contract term is twelve months, and the client may review renewal only after that term ends. No separate budget figure was stated in the request, so the price remains an open question rather than an assumed amount. The covered workforce is the group described in the request, and this section does not add people beyond that description. Tom Callahan owns these financial terms for the proposal. The payment structure is a monthly invoice in USD, with no alternative currency. This language stays with the institutional client and the workforce program. It does not describe an individual clinical case. The section repeats the twelve month term so the commercial offer matches the request. HealthCore will confirm the invoice calendar with the client before release.
```

## UK compliance

`test_uk_compliance_requires_gbp_and_a_dpa_referencing_uk_gdpr` checks the UK rules. A revenue section priced in GBP passes. A revenue section priced in USD fails `HC-CURRENCY`. A compliance section passes only when it includes a Data Processing Agreement that references UK GDPR. A missing clause fails `HC-UK-DPA`. A Business Associate Agreement quoted with USD fails both `HC-UK-DPA` and `HC-CURRENCY`.

## Failing section

This compliance draft is the US rule fixture in `test_us_compliance_fails_when_gbp_replaces_the_baa_clause`. It quotes GBP and does not include a Business Associate Agreement. Compliance fails with `HC-US-BAA` and `HC-CURRENCY`. It contains no patient information.

```text
This US proposal quotes GBP and does not include the required clause.
```
