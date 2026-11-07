# Microsoft staff federated authentication

Existing IT-provisioned staff can link Microsoft from their profile after password sign-in, then use that linked identity to receive the existing HealthCore session and retain their role and department. An unlinked Microsoft identity is rejected and audited without creating a user.

The implementation restricts the provider to Microsoft, excludes patients, validates explicit tenant, signed state, transaction binding, nonce and allowlisted callback, enforces unique identity links and rejects unlinking the last access method. It stores the identity link and email snapshot rather than Microsoft access/refresh tokens.

Two-flow diagram: [ARCHITECTURE.md](ARCHITECTURE.md). How to re-verify: [RUNBOOK.md](RUNBOOK.md).

## Validation

- Current isolated API JUnit: 32 federation tests plus 55 login/me/token/roles/password-reset tests passed, zero failures/errors/skips and no source drift. Fifteen added early-rejection audit cases first reproduced missing events, then passed after the fix. Evidence: `agents/federated_authentication/rejection-audit-validation.json`.
- UI: 3 Jest tests passed; affected lint, full lint and build exited 0. Recorded UI source matches current content after LF normalization. The warning Jest assertion is source inspection; separate browser evidence verifies the rendered warning.
- Real Microsoft IdP: isolated frontend 3011/API 8011 completed traditional fixture login, account-only Microsoft consent, real linking, logout and federated login to the same Priya app identity and role.
- Live unlink/rejection: unlink retained password access; the next Microsoft login was explicitly rejected and audited with null user_id. User count stayed at two. Password fallback and Microsoft relinking succeeded.
- Sanitized execution report: `C:\Users\cruzd\Documents\Codex\2026-11-04\task\healthcore-task2-live-evidence.md`. Private credentials are outside the repository and absent from this description.

The live test maps an explicitly authorized real Microsoft identity to a fictional staff fixture in disposable copied storage. It does not establish real employee provisioning. Earlier synthetic tests cover state/replay, inactive-account and last-method rejection cases; those were not repeated as live Microsoft cases.

## Rejection audit coverage

Early federated-login rejections now emit exactly one sanitized audit event for invalid/expired state, transaction binding/expiry/replay/redirect failures, and rejected provider/nonce/tenant/signature/issuer/audience/token validation. Login authorization-start provider/redirect rejections are also audited. Early events have null user_id and provider_user_id; only microsoft or the fixed unsupported provider category and fixed reason categories are stored. No request code, state, nonce, transaction identifiers, binding secret, redirect, token, email or unverified claims are copied. Signed link-purpose early failures use federated_link_rejected; an invalid state cannot establish purpose and is recorded as an unattributed login rejection. Existing verified-identity rejection events remain unchanged.

This audit-only backend follow-up was tested with synthetic OIDC and isolated stores. The historical live Microsoft results above were not rerun for this change; UI sources, security validations and running services are unchanged.

## Four-file source review

[Requirement-by-requirement review](agents/federated_authentication/SOURCE-COMPLIANCE.md) reconciles all four supplied Task 2 files. A 40-request regression exposed lost audit events (11 stored before correction); the complete audit insert is now serialized under the existing identity lock and preserves all 40. New direct tests prove matching-email rejection and password/Microsoft session expiry and deactivation parity. Full UI TypeScript, full ESLint, 66 Jest tests and isolated production build pass; offline lock check passes. Existing live Microsoft evidence is historical, not a new live test of this audit-only revision. Both session types retain the same stateless logout limitations; single-process TinyDB is the supported runtime.

## Review gate

Request Task 2 CTO signoff before merge. Task 1 approval does not cover this task. Daniel authorized supervisor commits and pushes for review; Cursor must never commit. No merge is authorized.

The Codex folder copy of this draft remains the external sanitized publication text.


Full UI TypeScript (including tests), scoped ESLint and isolated production build pass (exit 0); the complete UI Jest suite passes 66/66 tests. The shared TS2352 auth fixture is corrected with a real plain-text 503 Response, preserving the non-JSON safe-error assertions. That UI fixture correction changed no production UI sources or configuration.
