# Branch and tip disposition (campaign worktree)

**Campaign HEAD reference:** `6a4e821` on `integration/campaign` (I07-SSE merge parents `bdff629` + `969e5d2`).
**Rule:** no branch deletion. Archive and feature tips remain. Ancestry below is relative to this campaign HEAD.

| Tip (short) | Branch / note | In campaign HEAD ancestry? | Destination / label |
| --- | --- | --- | --- |
| `acbc91fe` | `origin/feature/infra-40-docker-dev` | Yes (via I04 `b4af4f9`) | Integrated as Docker packaging |
| `ea31b75a` | `origin/feat/pipeline-subflows-tests-dashboard` | Yes (via I05 `0cdf678`) | Integrated telemetry/reporting |
| `039b0d46` | `origin/feat/nightly-telemetry-script` | Yes (via I06a `6b3b642`) | Integrated nightly export |
| `35a539b2` | `origin/feat/async-task-queue` | Yes (via I06b `bdff629`) | Integrated Celery/Redis async |
| `969e5d2` | `origin/feature/sse-notifications` | Yes (via I07 `6a4e821`) | Integrated RFP SSE arrivals |
| `4255287` | `integration/i08-security-deliveries` tip (narrow I09) | Yes | Suppliers + security ancestry |
| `831ebff` | Auth / I02 published line | Yes | Auth baseline |
| `7c0ba64` | Incidents + analyzer | Yes | Incidents + analyzer |
| `4303dba` | `integration/i36-websocket-chat` | Yes (via earlier main line) | Knowledge WebSocket |
| `fca599d` | local `main` at campaign branch point | Yes (first-parent ancestor) | Promotion target remains separate |
| `24c32113` | `origin/feat/telemetry-report-endpoint` | Contained in I05 rollup path | Historical tip; content via I05 |
| `5394ce4` | `origin/feat/telemetry-event-capture` | Yes | Historical capture tip |

## Historical evidence (labeled)

| Evidence | Label |
| --- | --- |
| `services/api/data/i04-campaign/` through `i07-campaign/` | Campaign unit gates; gitignored |
| `services/api/data/f05-main-4255287/` (if present on other checkouts) | Historical F05 on older SHA; not campaign HEAD certification |
| PR descriptions under `docs/rfp/`, `docs/owasp/`, `docs/nist/` | Historical delivery write-ups; not substitutes for campaign LIVE matrix rows |

## Unsupported claims (explicitly not made here)

- Remote merge or push of `integration/campaign` to `origin/main`
- Instructor certification or external email verification
- Deletion or retirement of any listed branch
