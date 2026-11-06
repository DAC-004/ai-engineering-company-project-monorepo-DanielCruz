# Microsoft staff federated authentication

Existing IT-provisioned staff can link Microsoft from their profile after password sign-in, then use that linked identity to receive the existing HealthCore session and retain their role and department. An unlinked Microsoft identity is rejected and audited without creating a user.

The implementation restricts the provider to Microsoft, excludes patients, validates explicit tenant, signed state, transaction binding, nonce and allowlisted callback, enforces unique identity links and rejects unlinking the last access method. It stores the identity link and email snapshot rather than Microsoft access/refresh tokens.

Two-flow diagram: [ARCHITECTURE.md](ARCHITECTURE.md). How to re-verify: [RUNBOOK.md](RUNBOOK.md).

## Validation

- Isolated API JUnit: 13 federation tests and 5 login tests passed, zero failures/errors/skips. The 15 source files in the evidence manifest still match current content, allowing for line endings.
- UI: 3 Jest tests passed; affected lint, full lint and build exited 0. Recorded UI source matches current content after LF normalization. The warning Jest assertion is source inspection; separate browser evidence verifies the rendered warning.
- Real Microsoft IdP: isolated frontend 3011/API 8011 completed traditional fixture login, account-only Microsoft consent, real linking, logout and federated login to the same Priya app identity and role.
- Live unlink/rejection: unlink retained password access; the next Microsoft login was explicitly rejected and audited with null user_id. User count stayed at two. Password fallback and Microsoft relinking succeeded.
- Sanitized execution report: `C:\Users\cruzd\Documents\Codex\2026-11-04\task\healthcore-task2-live-evidence.md`. Private credentials are outside the repository and absent from this description.

The live test maps an explicitly authorized real Microsoft identity to a fictional staff fixture in disposable copied storage. It does not establish real employee provisioning. Earlier synthetic tests cover state/replay, inactive-account and last-method rejection cases; those were not repeated as live Microsoft cases.

## Review gate

Request Task 2 CTO signoff before merge. Task 1 approval does not cover this task. Daniel authorized supervisor commits and pushes for review; Cursor must never commit. No merge is authorized.

The Codex folder copy of this draft remains the external sanitized publication text.
