# Task 2 source compliance and review

Reviewed 2026-11-07 on `feature/federated-auth`, PR #41. All four supplied files were checked from the original checkout's `.project_specs/Task 2/`; their hashes are in [rejection-audit-validation.json](rejection-audit-validation.json). No source files were copied into or modified in `.project_specs`.

## Four-file reconciliation

| Supplied file | Authority and reconciliation |
| --- | --- |
| `Task 2-Platform - Federated Authentication.png` | Assignment, evaluation and submission requirements. Every rejected login must be auditable; expiry and revocation must match traditional sessions. |
| `healthcore-BRIEFING-FederatedAuthentication.md` | HealthCore access-rule authority: Microsoft only, internal staff, IT provision, explicit tenant, link fields, fictional fixtures and audit events. |
| `healthcore-BRIEFING.en.md` | Company context and privacy rationale. Department wish lists do not add Task 2 deliverables. |
| `federated-auth-checklist.md` | Local working aid, not a submission deliverable. Its transaction binding and no-Microsoft-token-persistence controls are retained. Its F13 unpublished and F14 no-live-IdP statuses, old process IDs/test counts and conftest-isolation description are historical snapshots. Current publication and separate live-provider evidence below supersede those status entries. Cursor never commits. |

The briefing forbids plaintext Microsoft token storage and does not require token storage; the checklist's stricter no-persistence control is implemented. Marcus/Priya are fully fictional linked/unlinked test fixtures, not permission to provision real people. No material access-rule conflict was found.

## Requirement-by-requirement review

API evidence below refers to `services/api/tests/test_federated_auth.py` (32 passing cases); shared auth evidence is 55 passing tests. API service paths are under `services/api/app/services/`. UI paths are under `uis/talent-pipeline-tracker/`.

| Requirement | Implementation and evidence | Result |
| --- | --- | --- |
| Own company fork and required feature branch | Existing repository, `feature/federated-auth`, draft PR #41 targeting main; only Task 2 changed. | Verified |
| Read company brief and specialized briefing | Both supplied Markdown files and original assignment inspected; this matrix reconciles the working checklist. | Verified |
| Diagram linking and login separately | [ARCHITECTURE.md](ARCHITECTURE.md) has both flows. Profile `purpose=link` and public `purpose=login` remain separate. | Verified |
| Microsoft only; no consumer providers | `federated_oidc.build_authorization_url` / `exchange_code_for_identity` reject other providers; start/callback provider regression cases. | Verified |
| Internal staff only; patients excluded | `_assert_can_link` and `_complete_login` enforce staff audience; patient/non-IT/missing/malformed eligibility tests fail closed. | Verified |
| Link only after IT provisioning and traditional authenticated session | `_optional_caller`, `_assert_traditional_session`, `_assert_can_link` and transaction caller binding; unauthenticated/federated/unknown-method and switched-caller tests reject. | Verified |
| Linking only from existing profile, not login screen | Profile mounts `FederatedLinkControls`; `MicrosoftSignInButton` starts login only. Source-inspection Jest and earlier actual browser evidence kept distinct. | Verified |
| User-to-provider relation, zero/one/multiple allowed in model | Separate `federated_links` rows keyed by user/provider/oid; multiple rows supported by the relation while Microsoft is the sole currently approved provider. | Verified |
| Required link fields, timestamp, email snapshot and IT flag | `_complete_link` stores user_id, provider, provider_user_id, email_at_link_time, linked_at, provisioned_by_it. Link test checks snapshot/IT status. No email join. | Verified |
| Provider+oid cannot be assigned twice | `_complete_link` checks and inserts under existing identity mutation lock; duplicate identity regression preserves original owner. Supported runtime is a single API process. | Verified within supported runtime |
| UI confirms linking and provider | Profile renders Microsoft heading, linked snapshot and unlink control; historical real Microsoft profile check also observed the link. | Verified |
| Unlink on same profile and warning/refusal for last method | Profile warning source test plus saved rendered warning evidence; API last-method 409 and password-holder unlink success test. | Verified |
| Login only to an already linked user | `_complete_login` looks up provider+oid and issues the existing user subject. Linked login preserves role and department protections. | Verified |
| Unlinked login explicitly rejected, audited, zero onboarding | Unknown-oid test plus new matching-existing-email test: 401, unchanged users/links, null audit user_id. Historical real Microsoft unlink/login rejection is recorded separately. | Verified |
| Every link, unlink and rejected federated login is auditable | Existing link/unlink/success and unlinked/inactive tests; 15 early rejection cases cover state, binding, replay, redirect, tenant, nonce, signature, issuer, audience, expiry and provider/start rejection. Each checks one sanitized event. | Verified |
| Concurrent rejection events are not lost | Counterexample before correction: 40 rejected requests saved only 11 events. Audit insert now holds the reentrant identity lock for the complete TinyDB read-modify-write. Same 40-request regression preserves 40 unique events. | Gap closed |
| Audit timestamp and identity fields without secrets | Verified identity rejects retain required fields; early failures have null unverified IDs, fixed provider/reason categories, and no request/claim/token values. Privacy assertions check full event shape and sentinels. | Verified |
| Signed OAuth state and exact allowlisted redirect | State signature/expiry/type and one-time transaction checks; invalid/tampered/expired state, foreign binding, URI mismatch and replay tests reject. | Verified |
| Transaction binding and explicit tenant | Hash-only browser transaction binding, nonce check and process-configured tenant/JWKS; signed token cryptographic and tenant tests. Unsupported algorithms/key URLs are rejected. | Verified |
| Do not persist Microsoft credentials or tokens | OIDC exchange validates then returns only oid/email/tenant; link stores identifiers/snapshot, transaction stores binding hash and transient nonce, and audit does not copy Microsoft token/code/state. Client secret is external private process configuration. | Verified by source and secret-omission assertions |
| Same session expiration as password login | New direct test obtains both tokens, compares same existing subject and configured 30-minute expiry within 5 seconds, then proves expired tokens for both methods receive 401. | Verified |
| Same revocation behavior as password login | New direct test accepts both active sessions, deactivates the existing user, then proves both previously issued tokens receive 401 from `/auth/me`. Both use common current-user validation. | Verified |
| Required fictional linked/unlinked staff seed | `_install_briefing_fixtures`: Marcus linked, Priya unlinked, IT-provisioned staff and unknown oid rejection fixture. Isolated stores only. | Verified |
| Actual Microsoft integration kept separate from synthetic proof | Earlier approved real single-tenant Microsoft link/login/unlink/reject/password fallback/relink on 3011/8011; no new live claim for this audit-only follow-up. See external sanitized report below. | Prior live verification retained |
| PR describes both flows and unlinked rejection evidence | Current PR text includes both flows, tests, privacy limits and source review. | Verified |
| CTO signoff before merge and Daniel review/approval | Task 2 CTO signoff is not supplied by Task 1 approval. PR remains a draft; no merge performed or authorized. | Human gate pending |

## Executed checks on this review's source

- 32 federation tests and 55 shared login/me/token/role/password-reset tests: exit 0, JUnit zero failures/errors/skips; source unchanged during execution.
- Full UI TypeScript, full ESLint, all 66 UI Jest tests (8 suites) and disposable production build: exit 0; UI source unchanged during checks.
- Python syntax and Git diff whitespace checks pass. Offline `uv lock --check` passes (202 packages); no dependency changes.
- Test stores, SQLite, Qdrant and synthetic provider configuration are run-owned; no live broker/provider calls, communications, identity changes or service restarts.
- Machine-readable current and historical records: [rejection-audit-validation.json](rejection-audit-validation.json).

## Real integration evidence and remaining boundaries

Historical real Microsoft report: `C:\Users\cruzd\Documents\Codex\2026-11-04\task\healthcore-task2-live-evidence.md` (2026-11-06). It proves actual account-only consent, linking, same fictional Priya app identity/role, unlink, unlinked rejection with audit/no new users, password fallback and relink. It is not a mock and is not real employee provisioning. Current audit locking/rejection logging is verified synthetically; the historical live flow is not relabeled as a test of this newer backend revision.

Rendered last-method warning / actual synthetic callback-page evidence: `%TEMP%\prompt13-affected-20261104\browser-prompt14-sanitized.md`. Its synthetic-provider limitation remains explicit.

Traditional and Microsoft app sessions are equally stateless JWTs. Logout clears the local token; there is no per-token server revocation endpoint/denylist for either method. Expiry and user deactivation are enforced identically and directly tested. Unlink prevents future Microsoft logins; it does not uniquely revoke an already-issued application JWT. This preserves the required parity instead of claiming a stronger baseline logout contract.

TinyDB identity/audit mutation locking is process-local, matching the supported single-process API runtime. Multi-worker or multi-host identity storage would require a different persistence/concurrency design and is not certified by these tests. Deployments also need their own registered exact callback, private credentials and properly provisioned staff; the local integration is not a production deployment certification. GitHub currently reports no status-check suite; recorded local evidence is the available automated verification.

No evidenced Task 2 code requirement remains open in this review. Real Task 2 CTO signoff, Daniel review and explicit merge approval remain outstanding. No other task/PR was changed.
