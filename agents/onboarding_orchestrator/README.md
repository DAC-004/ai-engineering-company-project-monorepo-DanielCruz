# Onboarding orchestrator

Single LangGraph agent that runs HealthCore **non-clinical corporate** onboarding.

Identity: `onboarding-orchestrator` (automated process). It can read official onboarding material, record comprehension results, request a human decision, record safe paperwork/background-check **completion flags**, enqueue internal notices, and propose system-access requests. It cannot approve a stage, change accounts or permissions, provision real systems, read payroll or background-check contents, bypass compliance, or send external mail or chat.

Official material lives in `data/raw/healthcore-onboarding/`. Runtime checkpoints and the projection store are gitignored under `data/process/onboarding/` or an injectable test path.

See `ARCHITECTURE.md` for the single-agent rationale and the stage graph.

## Evidence (2026-11-06, not Git publication)

Source-stable reviewed runner `run-20261106T021003592-a0f15471`: graph 35 passed, API 4 passed, both JUnit clean, `CONTENT_IDENTITY_CHANGED=false`. Tracker client tests 6 passed; lint exit 0 with one unused-import warning in test code; final production build exit 0 with source unchanged. Rendered Austin seven-stage journey completed on isolated 3020/8020, including Claire rejection/comment/retry/approve, assigned-manager gate, Diane closure, early US EHR denial, and post-compliance access. London hire Q&A cited UK GDPR material; wrapping matched viewport width 1265. Autonomous Celery beat/worker proof `task3-autonomous-deadline-76_8s15z` passed with 0 HTTP, exactly three expected internal-outbox notices, no duplicate or compliance bypass. Shared Celery 8 contract checks passed via an in-memory fixture-only adapter; original validator and production authorization unchanged.

Guarded owned refresh `refresh-20261106T022029504`: API starter 10656 (listener 46024), worker 5680, beat 46612, UI 3020 unchanged, Redis 6381. Refresh logs confirm scheduled sweep received/succeeded; live unlabeled NI rejection verified and not persisted. Original 3000/6379 owners unchanged. Fixture states preserved: Austin complete, London stage 2, Early stage 1.

Local PR draft: [`PR-DRAFT.md`](PR-DRAFT.md). Detailed findings: `C:\Users\cruzd\Documents\Codex\2026-11-04\task\healthcore-task3-review-findings.md`.

This is not real People-team signoff and not a Git commit, merge, or publication. Calendar sweep cadence is local operational config, not approved HR policy. Internal outbox only; no real communications.
