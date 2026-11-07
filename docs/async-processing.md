# Enhance Your Platform 4: Asynchronous Processing

The supplied Task4 project_specs.md and full assignment screenshot were both read and reconciled. The required branch is feature/async-processing, based on main b93a51c. This remains separate from Audit Log, Security Hardening and held PR44; no merge is implied.

## Existing operation and message contract

Password-reset email previously called the external Resend provider synchronously inside POST /auth/forgot-password. A provider outage could lose delivery while the API returned its enumeration-safe generic response. This task migrates that existing operation, rather than adding an unrelated example.

The queue contract is exactly one opaque operation UUID. Recipient, reset URL and one-time token never enter broker arguments, results, logs or status responses. A dedicated durable SQLite outbox stores an authenticated Fernet-encrypted payload; a purpose-separated HMAC derivation from the private runtime SECRET_KEY supplies its key. Operational reset-token records continue to contain only token hashes. Restrict filesystem access to the outbox and keep runtime credentials outside Git.

The API creates a durable pending operation before publishing. If publication fails, pending work survives for periodic reconciliation. Worker and beat run independently from the API; the public response stays identical for absent/inactive accounts. Never enable CELERY_TASK_ALWAYS_EAGER in a real async deployment: it is only for explicitly isolated unit tests.

## Worker, retry, idempotency and dead letters

The email worker claims an operation atomically with BEGIN IMMEDIATE and a bounded lease. Duplicate delivery of a completed job performs no provider call; concurrent claims have one owner. Actual provider requests use a stable `healthcore-reset-<UUID>` idempotency key. This also protects uncertain success where a provider accepted a message but its response was lost. The Python SDK adapter is tested to pass the key and require a provider acknowledgement.

There are three total attempts, with 2-second and 4-second exponential backoff. Pending retry times are durable. Exhaustion, expiry, invalidated resets or undecryptable payloads enter the dedicated persistent email_dead_letters queue/table, with safe reason code and attempt count. No failed task vanishes. Terminal payload ciphertext is removed; the original reset token expires or is invalidated under its existing lifecycle. No automatic manual-resend API is introduced.

Resend documents a 24-hour idempotency retention window: https://resend.com/docs/dashboard/emails/idempotency-keys. Delivery expires at the shorter of the reset lifetime and23 hours, preventing automatic retry beyond that provider guarantee. Expired/used/replaced tokens and inactive/changed accounts are rejected before delivery.

## Observability and authorization

Admin-only GET /tasks/email/{operation_id} exposes pending/in_progress/completed/failed, attempts, safe error code and timing metadata. GET /tasks/email/dead-letters lists at most100 permanently failed operations. Neither exposes recipients, ciphertext, credentials or reset URLs. Logs contain operation ID, attempts and state only.

## Runbook

Use the same isolated/private configuration and durable outbox/auth paths in API and worker. Set CELERY_TASK_ALWAYS_EAGER=0 and a configured REDIS_URL. Run:

- API: python -m uvicorn app.main:app
- Worker: python -m celery -A app.celery_app:celery_app worker --pool=solo --queues=celery,email --loglevel=INFO
- Scheduler: python -m celery -A app.celery_app:celery_app beat --loglevel=INFO

The dispatch-pending-email schedule runs every 15 seconds on the email queue, reclaiming due pending work or expired leases after broker/worker interruption. The existing incident/onboarding/supplier/financial schedules and queues are preserved. The API and worker must share the same runtime signing key while encrypted work is outstanding; drain this bounded outbox before rotating it, or supply a planned migration. Never change private keys during a pending delivery and assume it succeeded. Use a restricted durable volume and monitor dead-letter counts. TinyDB identity writes retain the baseline supported single API-process model; the email worker reads identities and writes only the dedicated outbox.

## Evaluation evidence

- Queue plus independent worker: actual separate Celery worker/beat on owned Redis; no in-request provider call. Controlled requests returned in0.116s and0.014s before the provider responded.
- Retry/backoff: first recovered job completed on attempt2; terminal job failed after3 attempts;2s/4s retry evidence is retained in worker logs and job state.
- Dead-letter visibility: the exhausted job remains queryable with attempts3 and a safe provider_unavailable code.
- Idempotency: the controlled provider deliberately accepted an effect before returning503; retry made one effect per key. Subsequent duplicate broker delivery caused no extra provider request. Concurrent claim unit test also passes.
- Broker recovery: a durable unpublished job was picked up by the real 15-second beat dispatcher and completed independently.
- Unit/API tests:11 focused tests pass, including Admin-only status/dead-letter privacy and invalidated-reset delivery rejection. Final full API168passed with zero failures/errors/skips. The initial two RFP failures came from a fixture overriding configured offline NLTK assets; honoring that configuration resolved them without weakening evaluator thresholds or assertions. The new outbox fixture also now owns/reset its SQL engine and seed flags; its combined approval-regression check passes9tests.

Machine-readable results are in async-processing-evidence/. The worker proof uses a controlled local provider and synthetic accounts, not a new real Resend message. It does not claim live delivery of this changed worker; no additional external email was authorized or sent. Existing real email delivery was established separately, before this branch.

CTO signoff and separate explicit merge approval remain pending. Do not close the PR until Daniel confirms submission.
