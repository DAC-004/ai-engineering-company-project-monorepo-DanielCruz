# Pre-submission corrections, 2026-10-07T01:44Z

Parent commit at the start of this pass: `91556493ddc9c9f0ae721f6705b47a24107d22b6`. These files are not in that commit. The live GGUF was not called. Production services were not changed.

## Cancellation notice

The sentence in `docs/owasp/evidence/2026-10-06-correction-pass.md` that says the prompt was not changed is historical. The phase 4a capture remains the before result. The model answer stated a 2-hour cancellation notice. The corpus cancellation threshold is 24 hours. Line 15 of `docs/company-knowledge-base/healthcore-appointment-policy.en.md` uses 2 hours as a reminder.

At this timestamp, `generate_answer` treated a claimed 2-hour cancellation notice as a grounding failure only when the retrieved text had cancellation lines and the answer did not already contain their hour count. That short-circuit is superseded. The current rule is in `docs/owasp/evidence/2026-10-07T0218Z-rag-deploy.md`, section "Cancellation deadline agreement". The asserted cancellation deadline is compared with the hour count on the retrieved cancellation lines. A reminder joined by a period, semicolon, newline, colon, or "and" does not make a different deadline agree. A 12-hour deadline against retrieved 24-hour lines is replaced with those lines. A 24-hour deadline against a retrieved 48-hour line is replaced with that line. A denial that cites the retrieved hour is kept. No cancellation hour line produces the insufficient-information answer.

Workstation, repository root, after 2026-10-07T01:44:44Z:

```text
uv run pytest tests/pipelines/test_rag.py::test_generate_answer_replaces_invented_two_hour_cancellation_notice tests/pipelines/test_rag.py::test_generate_answer_keeps_retrieved_twenty_four_hour_cancellation tests/pipelines/test_rag.py::test_generate_answer_invokes_local_llm_with_retrieved_context -q --tb=short
```

Exit code 0. Observed: `3 passed in 1.08s`.

The first test returns the invented 2-hour sentence twice. The final answer contains `24 hours` and does not contain `2 hours`. The second test returns a 24-hour answer and is called once. The existing 12-hour late-cancellation test still returns its patched answer unchanged. This does not prove that every other invented rule is rejected, and it does not rerun the live model.

## PHI surfaces

The positive fixture term is the detector category `medical record`. It is not a patient identifier. The negative fixture is `Cancelling more than 24 hours in advance has no charge.`

Workstation, `services/api`, before 2026-10-07T01:44:44Z:

```text
uv run pytest ../../tests/pipelines/test_phi_surfaces.py -q --tb=short
```

Exit code 0. Observed: `5 passed in 2.93s`. Temporary SQLite, traces, and the TestClient process ended with the test. No production store was opened.

Observed checks:

- The detector returns false for the cancellation sentence and true for the category term.
- `safe_output` replaces text that contains the category term with the fixed refusal, and returns the cancellation sentence unchanged.
- The guardrail log line contains `guardrail`, `action`, and `failure_type`, and does not contain the category term.
- A memory proposal that contains the category term is not stored. A proposal that contains the cancellation sentence is stored. The approval audit row has `actor_user_id`, event `approved`, and `occurred_at`. The temporary database text does not contain the category term.
- `POST /agent/query` with the category term returns 200 and the fixed PHI refusal. The response body and the temporary trace JSON do not contain the category term.

These checks do not guarantee later content. The root environment does not install FastAPI, so collecting this file from the repository root exits 2 with `ModuleNotFoundError: No module named 'fastapi'`. The API environment result above is the executed check.

## UK notification authority

Opened on 2026-10-07:

- https://ico.org.uk/about-the-ico/our-information/about-the-ico/ contains: "The Information Commissioner's Office transitioned to the Information Commission on 30 September 2026."
- https://www.legislation.gov.uk/ukpga/2018/12/section/3/2026-09-30 shows section 3(8) omitted on 30 September 2026, and section 3(8A): "The Commission" means the Information Commission (see section 114A).

The earlier excerpt that quotes Article 33 as notifying "the Commission" is preserved. That word, in the Data Protection Act 2018 as at that point in time, names the Information Commission. The ICO page identifies that body as the continued identity of the Information Commissioner's Office. It is one UK recipient. It is not a third notifier, and it is not the European Commission. Notification to the US Secretary under 45 CFR § 164.408 remains a separate US obligation.

## Scope reconciliation for section 3 and section 5

CONTEXT section 3 is an inventory to audit. CONTEXT section 5 says the named actions require human confirmation. CONTEXT section 6 says the report must confirm that requirement in the current implementation. CONTEXT section 1 separately says the audit logs this day asks you to implement must record that an action occurred, not clinical content.

A `/clinical` route set was added and then removed. It recorded a confirmation and did not sign a note, send a notification, share a history, or change a referral or appointment. That is not the section 5 action. The earlier command `uv run pytest ../../tests/pipelines/test_human_confirmation.py -q --tb=short` exited 0 with `6 passed in 1.88s`. That result is withdrawn with the routes. The searches under `services/api` and `uis` still find no sign, send, patient notification, history share, or referral or appointment status action. RFP `submit_approval_decision` remains a department decision on an RFP ticket.

## Cancellation comparison

The phase 4a capture remains the before result. The replacement quotes retrieved cancellation lines. It does not insert a fixed hour count. A reminder question that contains "cancellation" and whose answer says the reminder is sent 2 hours before the appointment is left unchanged. A chunk with no cancellation line does not supply a threshold. An unrelated wait-time question is left unchanged.

Workstation, repository root:

```text
uv run pytest tests/pipelines/test_rag.py -q --tb=line
```

Exit code 0. Observed: `41 passed in 1.07s`.

The host comparison that followed this local run is `docs/owasp/evidence/2026-10-07T0218Z-rag-deploy.md`.

## PHI surfaces

Workstation, `services/api`:

```text
uv run pytest ../../tests/pipelines/test_phi_surfaces.py -q --tb=short
```

Exit code 0. Observed: `6 passed in 2.30s`. Temporary files were removed with the test.

The checks are bounded:

- The detector assertion is only the detector.
- `safe_output` is the AI-output replacement function. A separate test calls `generate_answer` with a patched model that returns the category term. The returned text is the fixed refusal. A temporary file handler on `app.agent.guardrails.audit` contains `guardrail=output_validation` and does not contain the category term.
- The memory test writes and reads a temporary SQLite file. The category term is absent. The approval row has actor, event, and time.
- `POST /agent/query` returns the fixed refusal. The temporary trace file does not contain the category term.
- The guardrail file and the in-memory caplog check are the log surface for that logger. They do not prove every future log line.

REQ-SUB-02 is unchanged. Confirmed critical count remains zero.
