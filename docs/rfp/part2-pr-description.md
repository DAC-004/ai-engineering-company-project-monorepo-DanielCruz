## Summary

Part 2 drafts the pricing proposal from the ticket Part 1 already stored. `POST /rfp/tickets/{ticket_id}/response` accepts only `intake_complete` plus a matching `part2_handoff`, returns 202 with status `drafting`, and does not read the PDF.

Revenue, clinical, and compliance each generate from shared metadata and that department's `key_aspects`. Readability, relevance, and compliance evaluate a section in parallel. Each department has three attempts. Feedback goes back to the matching generator. An exhausted section stays on the ticket with its latest redacted draft, its evaluation, and `needs_human_review`. `part3_handoff` is written only after all three departments finish, with `response_complete` true. A fully passing ticket stays `under_evaluation`. If any section is provisional, that completion write sets the ticket to `needs_human_review`. Part 3 approvals, a final document, and arbitration are not implemented.

Drafts and `evaluation_results` are columns on the existing department-section rows. The same FastAPI service under `services/api` persists them through SQLModel. There is no second HTTP service.

## How to test

From the repository root, with Python 3.13:

```text
uv run --project services/api --python 3.13 python -m pytest tests/pipelines/test_rfp_classifier.py tests/pipelines/test_rfp_worker.py tests/pipelines/test_rfp_grounding.py tests/pipelines/test_rfp_phi.py tests/pipelines/test_rfp_response_readiness.py tests/pipelines/test_rfp_generator.py tests/pipelines/test_rfp_evaluator.py tests/pipelines/test_rfp_response_loop.py services/api/tests/test_rfp_intake_api.py -q
```

That command was run once and 51 tests passed. That run happened before the UK compliance test and the second database-URL test were added. It is not a combined rerun of every later check.

A later focused run passed these three tests only. It is separate from the 51-test run:

- `tests/pipelines/test_rfp_evaluator.py::test_uk_compliance_requires_gbp_and_a_dpa_referencing_uk_gdpr`
- `services/api/tests/test_rfp_intake_api.py::test_database_url_quotes_a_reserved_character_in_the_password`
- `services/api/tests/test_rfp_intake_api.py::test_database_url_preserves_valid_ports_and_an_encoded_password`

A separate API check, `test_exhausted_revenue_section_sets_ticket_needs_human_review`, then confirmed the stored ticket. It uses the SQLite service path. It is not part of the 51-test run and it is not the PostgreSQL read-back. The response starts as `drafting`. After the revenue section exhausts three attempts, the ticket is `needs_human_review`, that draft and its failed evaluation remain, and clinical and compliance still pass. `waiting_for_approval` and `done` are not set.

PostgreSQL persistence used the real SQLModel path: `begin_response` and `run_response`, then a new session after the engine was disposed. The dialect was `postgresql`. Status was `under_evaluation`, `response_complete` was true, and revenue, clinical, and compliance each had a draft and a structured evaluation. The draft text came from the test completion function. This was not a live GGUF run. The local model file was not present. The probe ticket was deleted after the read-back.

The ticket page was checked with controlled fixtures, not the local model. A completed ticket showed the three drafts and passing evaluations, then stopped polling. A ticket with one provisional section and two unfinished sections kept polling. After `response_complete` was stored, the page showed `needs_human_review`, kept the provisional section, and stopped polling. A missing model file produced `processing_failed` with code `model_asset_missing` while status stayed `drafting`. That failure run is not a successful generation.

More detail is in `docs/rfp/part2-testing.md`.

## Passing section

This revenue draft is the passing fixture in `tests/pipelines/test_rfp_evaluator.py`. Its Flesch-Kincaid grade is 9.0. For a US client it states USD and the twelve-month term, and it does not invent a headcount. Evaluation `overall_pass` is true.

```text
HealthCore proposes a twelve month occupational health agreement for Meridian Manufacturing in Austin. Revenue Cycle will quote the commercial terms in USD. Payment is due monthly in arrears after each service month under the written schedule. The contract term is twelve months, and the client may review renewal only after that term ends. No separate budget figure was stated in the request, so the price remains an open question rather than an assumed amount. The covered workforce is the group described in the request, and this section does not add people beyond that description. Tom Callahan owns these financial terms for the proposal. The payment structure is a monthly invoice in USD, with no alternative currency. This language stays with the institutional client and the workforce program. It does not describe an individual clinical case. The section repeats the twelve month term so the commercial offer matches the request. HealthCore will confirm the invoice calendar with the client before release.
```

## Failing section

This compliance draft is the US fixture in `test_us_compliance_fails_when_gbp_replaces_the_baa_clause`. It quotes GBP and does not include a Business Associate Agreement. Compliance fails with `HC-US-BAA` and `HC-CURRENCY`. It contains no patient information.

```text
This US proposal quotes GBP and does not include the required clause.
```

UK coverage is in `test_uk_compliance_requires_gbp_and_a_dpa_referencing_uk_gdpr`. A GBP revenue section passes. A USD revenue section fails `HC-CURRENCY`. A compliance section passes only with a Data Processing Agreement that references UK GDPR. A missing clause fails `HC-UK-DPA`. A Business Associate Agreement quoted with USD fails both `HC-UK-DPA` and `HC-CURRENCY`.
