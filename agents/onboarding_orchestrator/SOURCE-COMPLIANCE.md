# Task 3 source compliance review

Task 3 only; `feature/onboarding-orchestrator`, draft PR #40. Reviewed 2026-11-07 against the supplied `.project_specs/Task 3` in the original checkout. Source files remain untouched and untracked operational material. Their exact names and SHA-256 hashes are in [review-validation.json](review-validation.json): `project_specs.md`, `healthcore-BRIEFING.en.md`, and the original Agentic Engineering – Onboarding Agent image. The Markdown assignment and original image agree; the specialized briefing supplies HealthCore's exact rules. No Task 4/5 requirements were substituted.

## Seven-stage contract

| Stage | Exit | Deadline |
| --- | --- | --- |
| 1 Welcome/paperwork | People confirms signed-document receipt and external background-check completion; no outcome/details | Business day 2 |
| 2 Company | Comprehension at least 80% | Day 3 |
| 3 Operations | Comprehension at least 80% | Day 4 |
| 4 Compliance | 100% check plus Claire approval | Day 6 |
| 5 Role | At least 80% plus assigned direct-manager approval | Day 8 |
| 6 Ways of working | Comprehension at least 80% | Day 9 |
| 7 Access/closure | Diane approves closure | Day 10 |

The business-day policy, holiday list, timezone, cutoff and start-day counting are injectable operational settings because the supplied sources do not choose those details. The reminder is 24 elapsed hours, including DST transitions. Compliance cannot be skipped if the 10-day target is exceeded.

## All 24 implementation requirements

| ID | Requirement | Implementation / executed evidence |
| --- | --- | --- |
| F1 | Explicit graph, verifiable exits | `graph.py` LangGraph nodes/conditional edges; [ARCHITECTURE.md](ARCHITECTURE.md); full seven-stage test reaches completion only after Diane. |
| F2 | Company, operations, role, working practices and guidelines | Seven official documents cover five content stages, including both jurisdiction and role variants. Content catalogue checked. |
| F3 | Administrative paperwork, signatures and system access | People receipt records completion booleans only; gated access proposals and Diane closure. API tests and historical browser journey. |
| F4 | Named human approval points | People, Claire, assigned manager and Diane interrupts; identity/role/department rejection tests. |
| F5 | Briefing deadlines | `STAGE_DEADLINE_DAY` 2/3/4/6/8/9/10; timing and DST tests; autonomous deadline proof. |
| F6 | Index official material for lookup | `content.py` indexed sections and fixed document catalogue; `qa.py` searches only allowed official documents. |
| F7 | Adapt content to hire role/jurisdiction | Digital engineer and Revenue Cycle analyst variants; HIPAA for Austin, UK GDPR for London; no cross-framework notification-window answer. This meets the explicit minimum of two role variants. |
| F8 | Checks, reinforcement, different retry questions | Each of seven catalogues has two distinct five-question banks; 80% general/100% compliance; missed topics and official content remain visible; retry switches bank; second failures notify manager or Claire. |
| F9 | Cited answers only | Grounded official paragraph with document/heading citation, or uncovered result; unsupported-fine test refuses lexical-overlap speculation. |
| F10 | Acknowledge and route uncovered questions | Compliance to Claire, others to Diane. Punctuation-aware classification. Internal handoff now contains the privacy-checked question and resolved recipient user ID, not just an empty template. [Executed example](uncovered-question-example.json). |
| F11 | One framework-backed agent | One sequential LangGraph per hire; architecture rationale explains why coordination among several agents is unnecessary. |
| F12 | Persistent restart-safe checkpointer | SQLite saver with per-onboarding thread; fresh prepare/resume child processes restored exact pending stage, attempts and nonce and then progressed. |
| F13 | Several isolated onboardings | Austin/London/early-access fixtures; parallel projection/thread tests, separate thread IDs and checkpoint lock; no cross-hire state leak. |
| F14 | Background work | HTTP 202 Celery enqueue and job status; current real non-eager worker/beat proof, without HTTP or external communications. |
| F15 | Human gates are real interruptions | `interrupt` and resume commands; no graph continuation without an authorized decision. Concurrent copies now revalidate nonce under the checkpoint lock. |
| F16 | Verify approver role and department | Exact configured identity plus department and supervisor/admin role for Claire/manager/Diane; wrong identity/role/department tests and API capability check. Paperwork belongs to the People team. |
| F17 | Rejection returns to stage start with visible comment | Compliance/role restart and closure wait; hire view exposes the rejection comment. Fresh full journey tests Diane rejection then approval. |
| F18 | Remind hire before deadline | 24 elapsed-hour timing tests plus autonomous reminder to resolved hire ID. |
| F19 | Escalate overdue stage appropriately | Manager normally; delayed compliance notifies Diane with no bypass. Real beat/worker emits exactly expected hire/manager/Diane notices, no duplicate. |
| F20 | People active/blocked/stage view | Scoped People API list and `PeopleOnboardingBoard`; five current API tests plus prior rendered journey. |
| F21 | Hire progress and remaining work | Own-record API, content/check/rejection data and `HireProgressPanel`; other hire cannot read the record. Prior rendered Austin and London views retained. |
| F22 | Separate, narrower automated identity | `onboarding-orchestrator` / `automated_process`, allowlisted read/check/receipt/notice/propose capabilities; no human approval, user-permission changes, real provisioning or external transport tools. |
| F23 | Agent actions attributable as automated | `AuditLog` adds fixed automated actor identity; transition, notice, answer/routing, reminder/escalation and early-access security events are recorded. Questions are not copied to the audit. |
| F24 | Exclude sensitive new-hire data | No raw document/payroll/background-result fields; completion flags only. Recognizers and tests cover SSN, NI, passport/bank formats, salary/compensation and background details; API rejects without echo or store mutation. Generated decision UUIDs remain valid. Official patient-journey material contains only generic examples. |

## All nine evaluation criteria and submission deliverables

| Criterion | Evidence |
| --- | --- |
| E1 Complete explicit process graph | F1–F5; graph diagram, exact stage constants and full seven-stage closure test. |
| E2 Resume after service restart | F12; two different child PIDs, exits 0/0, same pending state/attempt/nonce and successful continuation. |
| E3 No content completion without passing check | F8/F15; threshold, failed retry, compliance 80%-rejection and graph path tests. |
| E4 Official citations or explicit human routing | F6/F9/F10; framework-aware answers, unsupported example, actionable internal handoff. |
| E5 No bypass of human approval/authorization | F4/F15/F16; negative role/department/identity/nonce tests and Diane closure checks. |
| E6 Overdue escalation to manager | F19; deterministic timing and real autonomous worker/beat proof, with HealthCore's compliance-to-Diane exception preserved. |
| E7 Automated audit identity | F22/F23; audit actor assertions and implementation review. |
| E8 No sensitive data in logs/prompts/messages/responses | F24; privacy exceptions before persistence, redacted audit, byte-for-byte unchanged checkpoint/store/audit/outbox on rejected API ingress, named-class examples. |
| E9 Written single-agent rationale | [ARCHITECTURE.md](ARCHITECTURE.md), also summarized in PR #40. |
| Feature branch and own company fork | Existing `feature/onboarding-orchestrator` and PR #40, main target. |
| PR graph, rationale, restart evidence and uncovered example | PR text and these linked deliverables. |
| People-team signoff before merge | Still a human review gate; fictional Diane test approval is not real signoff. Daniel must explicitly approve PR #40 before merge. |

## Supplied HealthCore details

English only; Spanish is optional and no official Spanish material exists, so no runtime translation is offered. Scope is non-clinical corporate onboarding in Austin/London; clinical licensure/credentialing and patient onboarding are excluded. The minimum two requested role-content variants are implemented; additional role content and any mapping outside the existing six-department platform catalogue require People configuration rather than invented policies.

The seed contains three fictional onboardings, two managers in different departments and a Compliance approver. Every known patient-information system request before Claire's compliance approval is denied, audited as a security event and routed to Claire. Unknown systems are denied, not provisioned. Access records are proposals only, not real EHR/claims-account creation.

## Gaps found and closed in this review

1. Two queued copies of one check could both pass nonce/authorization before the durable lock. Validation now occurs inside the mutation lock; only one copy is accepted.
2. A concurrent deadline sweep could overwrite a newly completed stage (projection 2 vs checkpoint 3). Sweep projection/notice flags now share the graph lock.
3. Punctuated uncovered questions such as `HIPAA?` went to Diane. Classification uses normalized word tokens and routes them to Claire.
4. Unlabeled fictional passport/bank identifiers escaped the privacy filter. Conservative common-format recognition and API no-echo/no-store-mutation checks cover them.
5. Uncovered-question notices had no question text or resolved user ID. The internal handoff now supplies both after privacy validation; checkpoint/audit remain free of the question.
6. PR #40 conflicted with newly merged Task 2. The feature branch incorporates the approved main baseline, preserves both tasks' test isolation and progress records, and retains Task 2 auth code unchanged. This is feature-branch integration, not a merge of PR #40 into main.

The first five issues have reproduced failing counterexamples and passing regressions. The original image's checked boxes are source material, not accepted as proof of these results.

## Verification and limits

Current evidence: 41 agent tests; five onboarding API tests; full UI TypeScript, full ESLint, all 72 UI Jest tests and production build; fresh real Celery beat/worker; fresh two-process restart; Python syntax and offline dependency-lock check. Combined federation/shared-auth integration ran 32 federation plus 60 mixed API tests before the final notice-payload-only correction; the five affected onboarding API tests were rerun afterward. The remaining 55 auth tests and Task 2 auth modules are unchanged. Counts overlap and are not added together.

[review-validation.json](review-validation.json) records runs, source hashes, counterexamples and scope. Current onboarding UI source is unchanged from its already rendered seven-stage Austin/London journey; the shared UI integration has fresh build/Jest/type/lint evidence. The new backend checks are API/worker/agent evidence, not a newly recorded browser journey. Existing long-lived service processes were preserved and are not claimed to have been redeployed to this revision.

Calendar defaults/cadence are explicit operational/test settings, not approved HealthCore holiday policy. Internal outbox notices are not real email/Slack delivery or real access provisioning. Privacy checks demonstrate the named source classes and synthetic formats; this is not a formal certification of every possible arbitrary sensitive string. Earlier installed dependency-audit findings are recorded in the existing review boundaries; no dependency upgrade is hidden in this PR.

No evidenced functional requirement above remains unaddressed in the implemented minimum scope. This is a requirement/evidence review for Daniel, not an unconditional production or “100% security” certification. Real People-team signoff and Daniel's explicit PR #40 merge approval remain outstanding. No Task 4/5 PR was changed or merged.
