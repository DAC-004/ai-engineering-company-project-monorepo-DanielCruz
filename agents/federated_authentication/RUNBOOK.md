# Federated authentication runbook

Reviewer-facing. No client secrets, tokens, or tenant identifiers are recorded here.

## What to verify

1. Flow 1: an already provisioned staff user links Microsoft from a traditional session.
2. Flow 2: that linked identity receives the existing HealthCore session and role.
3. An unlinked Microsoft identity is rejected, audited, and creates no user.

See the two-flow diagram in [ARCHITECTURE.md](ARCHITECTURE.md).

## Synthetic isolation (no live Microsoft)

API module: `services/api/tests/test_federated_auth.py`.
Isolation helper: `services/api/tests/federated_isolation.py` (no `app.*` imports).

Set disposable `FEDERATED_ISO_ROOT` / TinyDB / sqlite paths **before** collection. Clear live seed and provider credentials from the child environment. `FEDERATED_OIDC_MODE=synthetic` is tests only.

Current isolated API evidence: 32 federation tests plus 55 login/me/token/roles/password-reset tests, zero failures/errors/skips. The 15 added early-rejection cases each failed for a missing event before the fix and pass afterward. See [rejection-audit-validation.json](rejection-audit-validation.json). UI: 3 Jest tests; affected lint, full lint, and production build exited 0. Last-method warning copy is asserted in source; rendering was verified separately.

Do not treat synthetic JWKS as actual Microsoft integration.

## Live Microsoft (already executed; do not reprint secrets)

Authoritative sanitized report:
`C:\Users\cruzd\Documents\Codex\2026-11-04\task\healthcore-task2-live-evidence.md`

Isolated frontend `http://localhost:3011` and API `http://127.0.0.1:8011` used a restricted private Entra configuration **outside** the repository, account-only consent, and a disposable copied store. Observed:

- Traditional Priya login, real Microsoft link, logout, federated login to the same app identity and role.
- Unlink retained password access; the next Microsoft login was rejected with `federated_login_rejected` and `user_id` null; user count stayed two.
- Password fallback and relink succeeded.

That maps a real Microsoft identity onto a **fictional** staff fixture. It is not real employee provisioning. Private credentials stay out of Git, chat, logs, and this runbook.

Original listeners on 3000/8010 were preserved. Do not duplicate those services.

## Publication

Draft PR text: [PR-DRAFT.md](PR-DRAFT.md) and the Codex copy named above.
CTO signoff is a human review gate. Task 1 approval does not substitute. Daniel explicitly authorized the supervising Codex agent to commit and push the reviewed task branch. Cursor must never commit. No merge is authorized until Daniel reviews and approves.


The final Task 2 review adds direct password/Microsoft expiry and deactivation parity, matching-email rejection, and 40 concurrent rejected-request audit preservation. Full UI TypeScript/lint/Jest (66 tests)/production build and offline lock checks pass. See SOURCE-COMPLIANCE.md for the four supplied sources and limitations.
