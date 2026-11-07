# Enhance Your Platform Task 5: Security Hardening

Prepared for Daniel's review and submission from recorded implementation and test evidence. This report does not claim 100% compliance, CTO signoff, merge approval or an exhaustive security certification.

## Source and scope

The supplied `Task 5/project_specs.md` and full assignment screenshot were read and reconciled; their hashes are in security-hardening-sources.json. This is branch `feature/security-hardening`, based on main b93a51c. The current OWASP reference used is [Top 10:2025](https://owasp.org/projects/top-ten), with the [official category list](https://top10.owasp.org/2025/0x00_2025-Introduction/).

Scope follows the assignment: assess existing high-risk flows, record at least three real before/after findings, fix identified issues, enforce explicit 429 throttles, review secrets/history and document a rotation mechanism. No new EHR, payments system, deployment or unrelated feature was introduced. Audit Log and Asynchronous Processing were submitted and closed without merging as PRs #45/#46; their branches remain separate, not silently merged here.

## High-risk inventory

Existing authentication/recovery endpoints: /auth/login, /auth/forgot-password, /auth/reset-password and /auth/change-password; Microsoft linking/login/unlink and transaction validation; JWT decoding and inactive-staff checks. Existing critical writes include users/assignments, roles/departments, profiles, incidents, inventory, suppliers, RFP approvals, onboarding and financial close. The existing chat socket authenticates staff before session access. There is no payment processor or operational clinical-record/claims API in this baseline.

## Findings, before evidence and corrections

| Finding | Reproduced before | Implemented correction and saved after evidence |
|---|---|---|
| S1: Unlimited password guessing, A07/A06 | Twelve incorrect logins returned 401 without any 429. `before-auth-junit.xml` records the failing limit assertion on unchanged code. | Durable SQLite counters throttle login/recovery/critical writes. API tests trigger429 and Retry-After. Final full API166 passed, including six hardening tests. The isolated runtime also returned explicit 429 with positive Retry-After. |
| S2: Account-existence timing oracle, A07 | An unknown account performed zero password-verifier calls; a known account performed bcrypt despite identical rejection bodies. | Unknown accounts perform one bcrypt verification against a random startup dummy hash. The HTTP-boundary regression verifies one call and401. This removes the dominant skipped-bcrypt difference; perfect network wall-clock timing is not claimed. |
| S3: Concurrent reuse of one-time reset, A06/A08 | Two concurrent requests using the same unused reset credential both succeeded and invoked two instrumented password-update calls. | The existing reentrant identity lock covers token creation/invalidation, validation, password mutation and consumption. The same race accepts one request, rejects one and performs one update. This matches the existing single API-process TinyDB architecture; it does not claim a distributed identity database. |
| S4: Vulnerable dependencies, A03 | Recorded npm graphs contained52 root-tool and 31 tracker vulnerable-package records, including critical findings. These counts are dependency/advisory records, not52/31 independent application exploits. | Root Vercel65.12.1, Next.js/eslint-config-next16.4.5 and reviewed overrides resolve the recorded findings. Final root and tracker npm scans both report zero findings at all severities. Exact locked installs, root checks, Vercel command-load/help checks, an actual esbuild transform, and full UI checks passed. No Vercel deployment was run. |


### Rate-limit implementation boundaries

Fixed 60-second windows allow 10 login attempts,5 recovery requests,10 reset/change operations,60 other critical writes and600 telemetry submissions per observed client. Counters are process-safe, persistent and atomic; stored client keys are hashed. Rejections are 429 with Retry-After; unavailable counter storage fails closed with 503. Forwarded headers are not trusted by the middleware. Existing server/proxy configuration determines the observed client address; shared-NAT clients share a budget. These are documented implementation boundaries, not added assignment acceptance gates.

### Dependency-patch provenance

The tracker uses private local package `deepmerge@4.3.2-healthcore.1`. This is a reviewed derivative of upstream4.3.1, not an upstream release. The [reviewed advisory](https://github.com/advisories/GHSA-gcqx-w48m-w2h4) lists no upstream patched version; the [upstream issue](https://github.com/TehShrike/deepmerge/issues/273) describes the bypass and remediation. The original license, bundle hash and patch explanation are retained in vendor/deepmerge/PATCH.md and license.txt. The local patch is disclosed as dependency maintenance; recorded application/tooling compatibility checks passed. No advisory suppression rule was added.

Remaining major-version dependency changes were first installed in an isolated candidate and checked against actual Vercel command modules before adoption. The final installed graph and application checks then passed. Vercel build/deploy/dev/env/project checks were `--help` compatibility checks, not builds or deployment through a real account. The actual root Milestone2 TypeScript/tests/build and tracker production build also passed.

## OWASP Top 10:2025 applicability

| Category | Application-specific assessment |
|---|---|
| A01 Broken Access Control | Existing staff dependencies, role/department/object restrictions and federation allowlists apply; their API regressions pass. No nonexistent payment/EHR surface is represented as tested. |
| A02 Security Misconfiguration | Required private signing/database configuration, explicit local CORS and safe error handlers were reviewed. Test listeners were loopback-only; no production configuration was changed. |
| A03 Software Supply Chain Failures | Actual root/tracker lockfiles were assessed and remediated, with saved before/final graphs, reproducible locked installs and compatibility checks. The unpatched-upstream dependency has a licensed, tested local fix. |
| A04 Cryptographic Failures | Existing bcrypt, signed JWT algorithm restrictions and hashed reset credentials were retained. Private keys remain external; overlapping-key rotation is implemented and tested with fictional keys. |
| A05 Injection | Typed request validation, parameterized limiter SQL, identifier boundaries and public-safe errors were reviewed. Auth/recovery inputs do not construct shell commands. |
| A06 Insecure Design | S1 and S3 were reproduced and fixed; the supported TinyDB concurrency boundary is explicit. |
| A07 Authentication Failures | S1/S2 are corrected. Existing federation transaction/tenant/staff-link and inactive-user checks remain covered; recovery limits and consumption are tested. |
| A08 Software/Data Integrity Failures | The reset race and dependency prototype issue are corrected. Existing state/nonce/binding/JWT checks remain covered; no unsigned-token fallback is introduced. |
| A09 Security Logging and Alerting Failures | Existing sanitized authentication/federation rejection logs remain; throttles return explicit status. The separate Audit Log PR is not falsely claimed present in this branch. |
| A10 Mishandling of Exceptional Conditions | Recorded behavior includes503 for unavailable rate control,429 for throttling,401 for invalid credentials and400 for invalid resets. Existing safe-error contracts remain tested. |

## Secrets/history review and rotation procedure

The saved read-only source/history scan inspected 3564 reachable Git objects / 1885 blobs (44,568,371bytes) with six high-confidence provider-token/JWT/private-key signatures and found no matches. Configuration review confirmed required private SECRET_KEY injection and external provider credentials. This scan covers its recorded snapshot and finite signatures; it is not universal proof of absence. No secret values were emitted in the evidence, and private runtime configuration is excluded from the staging scope.

Rotation signs only with the active SECRET_KEY and can verify up to three retired keys via JWT_PREVIOUS_SECRET_KEYS during a bounded overlap. The saved test mints an old token, verifies it during overlap, mints/verifies a new token, then retires the old key and confirms rejection while new tokens continue working.

For planned rotation, securely distribute verification overlap to serving instances; switch signing to the new key; roll and health-check instances behind the existing serving endpoint; retain old verification for the maximum outstanding token TTL plus clock allowance; then remove the retired key everywhere. Keep values in private runtime configuration, never Git, chat or command arguments. Uninterrupted serving requires the existing deployment's rolling/blue-green mechanism; restarting a single process is not presented as zero interruption. Immediate retirement of a compromised key intentionally revokes its sessions. No real key rotation or deployment was performed, and neither is an added completion requirement.

## Recorded verification

- Before-fix reproduction: three genuine authentication assertions failed; the initial malformed-fixture attempt is excluded.
- Final API:166 passed, zero failures/errors/skips, including all six hardening cases.
- Tracker:78 Jest tests across 10 suites, full TypeScript, lint and production build passed with the updated dependencies.
- Root: exact install, Vercel version/command-help checks, esbuild transform, Milestone2 checks passed.
- Final npm graphs: root 0 and tracker 0 findings at every severity in the saved scans.
- The two initial RFP failures were traced to a fixture replacing configured offline NLTK assets. Honoring that configuration resolved them without weakening evaluator logic, thresholds or assertions. Test-only rate-counter and short federation paths preserve real controls while isolating cases.
- Normal synthetic staff login and workspace rendering succeeded in the built app. The independent runtime API check recorded429 and Retry-After.

Machine-readable results and necessary before/final evidence are in security-hardening-evidence/. validation-summary.json distinguishes completed checks from the limitation below. These are saved completed results.

## Requirement-to-evidence mapping

| Supplied assignment requirement | Existing implementation or recorded evidence |
|---|---|
| Own company monorepo and feature/security-hardening branch | This branch in the existing fork, based on b93a51c; source hashes retained. |
| Inventory high-risk endpoints/flows and record the before state | High-risk inventory above; before-auth-junit.xml and original dependency graphs. |
| Review each current OWASP Top 10 category and applicability | All ten application-specific rows above, using the official2025 reference. |
| At least three real vulnerabilities, reproducible evidence and impact | S1-S3 are existing application flaws; their before assertions and current named API tests are preserved. S4 documents dependency audit findings. |
| Rate limits on login, recovery and critical writes | SensitiveRateLimitMiddleware and persistent counters; six hardening API tests include endpoint limits and concurrent budgets. |
| Explicit429 without an ambiguous API failure | Saved automated endpoint assertions and live-rate-limit.json show429 and Retry-After. No specific manual browser method is required by the source. |
| Audit secrets in source/history | Recorded source/history scan plus configuration review; its finite signatures and snapshot boundary are disclosed. Private runtime files are excluded from the publication manifest. |
| Implement/verify rotation and document uninterrupted rotation procedure | Active/retired JWT-key verification, saved overlap/retirement test and the procedure above. No live key rotation is added as an acceptance criterion. |
| Fix every vulnerability identified in this audit | Recorded corrections for S1-S4; final npm graphs0/0 and named API regressions plus compatibility checks. The local dependency patch is disclosed and licensed; recorded application/tooling checks passed. |
| Before/after evidence for each finding | Before-auth-junit.xml, final-api-junit.xml, original/final advisory graphs; no source assertion or threshold was weakened. |
| Full audit report in the PR description | This report will be included in full, with links to the checked-in evidence. |
| CTO signoff before merging | Pending Daniel's review. Submission preparation does not imply signoff or merge approval. |

No additional unmet implementation requirement is established by the recorded checks. The following limits qualify that evidence; they are not invented assignment gates or a claim of 100% compliance.

## Review and submission state

The three primary application findings S1-S3 already satisfy the source's minimum of three. No additional fault or verification method is introduced as an acceptance criterion. The assignment permits screenshots, logs or automated tests for before/after evidence; the retained required evidence is linked above.

This PR is prepared for Daniel's review and submission from recorded results. CTO signoff and separate merge approval remain pending. No 100% compliance certification, merge or closure is implied. No deployment, real credential rotation or service interruption was performed; these are not additional assignment requirements.


## Approved Audit/Async/WebSocket integration

Integrated main0be67f3 while preserving all task histories and configuration examples. Daniel explicitly approved preserving both the known-user audit target and exactly one real-or-dummy password verification, with audit middleware outside the rate limiter so classified429 responses remain audited. The new HTTP-boundary composition regression verifies known401 target attribution and auditable429 rejection. Current combined fullAPI196, separate chat/streaming/SSE105, and tracker80Jest/types/lint/productionbuild pass. The new test fixture was corrected to an accepted fictional email domain, a100-row ledger page and its own audit file; no application assertion was weakened. Results are in integrated-*-result.json and composition-result.json. This is an integration check, not a newly invented finding. No previously excluded optional operation was retried. Final end-to-end verification and conditional PR44 merge remain pending.
