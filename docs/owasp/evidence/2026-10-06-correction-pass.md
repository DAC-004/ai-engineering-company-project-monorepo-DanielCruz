# Correction pass, 2026-10-06

This file corrects overclaimed rows. It does not replace the earlier captures. No secret value and no response body is copied here. Later isolated requests, the generated RFP sample, frontend logout and denied-page events, logging durability, and the ecdsa, diskcache, and PyJWT caller inspection are in `docs/owasp/evidence/2026-10-06-remaining-verification.md`. The response-path readback and formatted log records are in `docs/owasp/evidence/2026-10-06-bounded-corrections.md`. Sentences below that say those checks were not run are historical.

Guest checks used the already running API on `127.0.0.1:8000`. SSH, firewall, certificate, HTTPS, WSS, renewal, the GGUF hash, and the retrieved-document fixture were not repeated. The MCP HTTP service was not started. Synthetic users created for this pass were deleted (`204`).

## 1. Secrets

Scope: 481 tracked paths, of which 416 text files with source, example, markdown, or JSON suffixes were read. The same assignment pattern was applied to `git diff -U0` and to untracked text files outside `docs/owasp`. Method: a local scan for assignment names ending in `API_KEY`, `SECRET_KEY`, `PASSWORD`, `CLIENT_SECRET`, `DATABASE_URL`, `ACCESS_TOKEN`, or `API_PASSWORD`. The scan records the filename, the assignment name, and a class. It does not record the value.

Settings fields that require an environment value and have no default were read separately in `services/api/app/core/config.py` (`SECRET_KEY`, `DATABASE_URL`) and `mcps/healthcore-tools/src/healthcore_tools/config.py` (`HEALTHCORE_API_PASSWORD` as `SecretStr`).

| Location | Assignment | Class |
| --- | --- | --- |
| `.env.example` | `LLM_API_KEY`, `EMBEDDING_API_KEY`, `GENERATION_API_KEY`, `QDRANT_API_KEY` | empty |
| `services/api/.env.example` | `LLM_API_KEY`, `MCP_AGENT_ACCESS_TOKEN`, `MCP_AGENT_CLIENT_SECRET` | empty |
| `services/api/.env.example` | `SECRET_KEY`, `DATABASE_URL` | non-empty unquoted placeholder, not a live credential |
| `mcps/healthcore-tools/.env.example` | `HEALTHCORE_API_PASSWORD` | empty |
| `shared/healthcore_rag/config.py` | `EMBEDDING_API_KEY`, `GENERATION_API_KEY`, `QDRANT_API_KEY` | environment lookup |
| `services/api/app/services/inventory_seed.py` | `SEED_USER_PASSWORD` | non-empty literal, length 16 |
| `services/api/app/services/rfp_demonstration_accounts.py` | `DEMONSTRATION_ACCOUNT_PASSWORD` | non-empty literal, length 19 |
| `mcps/healthcore-tools/tests/test_mcp_acceptance.py` | `TEST_API_PASSWORD` | non-empty literal, length 19 |

The uncommitted diff and the untracked files outside this evidence tree added no credential assignment. The three non-empty literals are seed, demonstration, and test passwords. They are not model, MCP, or database keys.

Deployed frontend: 140 `.js`, `.json`, and `.html` files under `/opt/healthcore/app/uis/talent-pipeline-tracker/.next` were read on the guest. File counts for `SECRET_KEY`, `DATABASE_URL`, `MCP_AGENT_CLIENT_SECRET`, `DEMONSTRATION_ACCOUNT_PASSWORD`, `SEED_USER_PASSWORD`, `HEALTHCORE_API_PASSWORD`, and `BEGIN PRIVATE` were all 0. Names present were `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_INVENTORY_API_URL`, `NEXT_PUBLIC_TELEMETRY_ENDPOINT`, and `NEXT_PUBLIC_TRACKER_API_BASE_URL`. Those are public client settings. Their values were not printed.

## 2. PHI surfaces

Clinical means one of these phrases was present: social security, medical record, date of birth, diagnosis, prescription, patient id, mrn. A miss is limited to that phrase list and to the sample that was actually read.

| Surface | Sample | Fields inspected | Clinical content |
| --- | --- | --- | --- |
| Events | Earlier synthetic telemetry batch in `docs/owasp/evidence/2026-10-06-remaining-checks.md`. Not repeated. | Envelope names from `services/api/app/schemas/telemetry.py`. The API logs `event_type` and does not persist the batch. | The batch was a synthetic event name. No clinical field was stored. |
| Tables | Column names from the earlier store read. This pass created and deleted one synthetic user. | Users: `created_at`, `email`, `hashed_password`, `id`, `is_active`, `role`. Profile response: `address`, `id`, `name`, `phone`, `user_id`. Inventory product keys from a list of 6: `category`, `clinic_current_stock`, `country`, `current_stock`, `expiry_date`, `id`, `minimum_stock`, `name`, `sku`, `unit`. | User and profile values were not copied. Product values were not copied. RFP text tables had 0 rows in the earlier read, so no RFP row was sampled. An empty table is not proof about a future row. |
| Responses | This pass, plus the phase 4a agent response. | Login: `access_token`, `token_type`. Profile: keys above. Knowledge: `answer`, 262 characters. Agent, phase 4a lines 54-62: `answer`, `memory_proposal`, `thread_id`, `trace_id`. | Knowledge answer: phrases absent. Agent prefix already filed: phrases absent. Token values were not copied. |
| Logs | Journal sample after the bad-bearer and accepted-chat requests. `audit.py` lines 14-20. | Journal booleans only. Audit fields: `guardrail`, `action`, `failure_type`. | The fixture password was absent from the journal. The audit fields are not clinical text. |
| AI outputs | Knowledge answer above. Chat sample below. Phase 4a agent answer. Earlier trace keys. | Chat events and token fields below. Trace keys from the earlier file: `answer`, `context`, `error`, `lookup_failure`, `node_order`, `nodes`, `probe`, `question`, `sources`, `thread_id`, `ticket_id`, `ticket_status`, `trace_id`. | Knowledge and the 61 chat characters: phrases absent. Trace values were not re-read. |

Chat sample, this pass, synthetic user deleted afterward. Events received, with data keys: `session_snapshot` (`messages`, `session_id`); echoed `user_message` (`session_id`, `text`); nine `token_chunk` events (`sequence`, `session_id`, `token`). `CHAT_TOKEN_CHARS 61`. `CHAT_CLINICAL False`. `generation_completed` was not in that 12-event window.

RFP output was not sampled. `FinalDocumentPublic` fields in source are `ticket_id`, `sections`, `currency`, and `generated_at`. No ticket row exists. Creating one would persist a business record, so it was not created. That missing sample stays a limitation. It is not evidence that RFP output is free of clinical text.

## 3. Access control

A `422` from an empty or invalid body is validation. It is not used below as proof that the action enforces authorization. Anonymous `401` shows the dependency rejected a missing credential. A `200` or `403` shows the request reached an authorization result.

| Route | Role and boundary in source | Request that establishes it |
| --- | --- | --- |
| `POST /auth/login` | Public. | Earlier failed login `401`. |
| `POST /users` | Public registration. Role is set to `user`. | This pass `201`, then deleted. |
| `GET /auth/me` | Current user only. | Earlier authenticated `200` with keys `email`, `profile`, `role`. |
| `GET /users` | Any authenticated user. No ownership filter. | Earlier authenticated `200`. |
| `GET /users/{id}` | Any authenticated user. `require_self_or_admin` is not called. | Earlier cross-user `200` with keys `created_at`, `email`, `id`, `is_active`, `role`. |
| `PUT /users/{id}` | Self or admin. A non-admin cannot set `role=admin`. | Earlier self role change `403`. |
| `DELETE /users/{id}` | Self or admin. | This pass deleted the synthetic user `204`. A delete of a different user was not sent. |
| `GET /profiles/me`, `PUT /profiles/me` | The path is the current user. | This pass `GET` `200` with the profile keys above. `PUT` was not sent. |
| `GET /inventory/products` | Any authenticated user. The list is not filtered by the caller clinic. | This pass `200`, six products, keys listed above. |
| `GET /inventory/orders` | Any authenticated user. No caller-clinic filter. | Earlier `200`. Clinic ids present: 1, 2, 4, 10, 11. |
| `POST /inventory/products`, inbound, outbound | Authenticated user. `clinic_id` comes from the body. `user_uuid` is the caller. | Earlier authenticated calls returned `422`. That is validation only. A valid write was not sent because it would insert a business row. The clinic boundary is the source, not the `422`. |
| `GET /inventory/products/{id}` | Authenticated user. `clinic_id` is an optional query, not the caller clinic. | Not requested with a foreign clinic. Source is `inventory.py`. |
| Incident manager list, get, summary, create, status | Any authenticated user. The handler does not compare the incident with the caller. | Earlier authenticated list `200` with an empty list. No stored incident, so a cross-user read was not executed. |
| `POST /api/incidents/analyze` and results routes | Authenticated user. Delete uses `_require_analysis_owner_or_admin`. | Earlier empty upload `422` is validation only. No stored analysis, so the `403` owner branch was not executed. |
| RFP ticket routes | Authenticated user. Approval raises `not_department_owner` when the user has no department binding. | Earlier empty create `422` is validation only. No ticket exists, so the `403` branch was not executed. Source: `rfp_service.py` around the binding lookup. |
| `POST /knowledge/query` | No bearer. | This pass `200`, field `answer`. |
| `POST /telemetry/events` | No bearer. | Earlier `200`, key `received`. |
| `GET /suppliers` and the other supplier handlers | No `get_current_user` in `suppliers.py`. | Earlier anonymous `GET` `200`. |
| `GET /agent/guardrails/summary` | No bearer. | Earlier anonymous `200`. |
| `POST /agent/query` | Optional bearer. | Phase 4a `200` with `answer`, `memory_proposal`, `thread_id`, `trace_id`. |
| `GET /docs`, `GET /openapi.json` | No bearer. | Earlier anonymous `200`. |

Findings that remain medium, from the `200` and `403` results and the source: any authenticated user can read another user's public account fields; inventory reads are not limited to one clinic; suppliers and the guardrail summary do not require a credential. No authorization code was changed.

## 4. MCP families and logging

Probe: `docs/owasp/evidence/2026-10-06-mcp-families.py`, run with the API virtualenv. The MCP service was not started. Sanitized result:

| Family | Payload | Result |
| --- | --- | --- |
| `query_medical_supply_inventory` | `stock=1` | `inventory_write_forbidden` |
| `query_medical_supply_inventory` | `clinic_id=99` | `validation_failed` |
| `attempt_inventory_modification` | `action=not-a-real-action` | `validation_failed` |
| `attempt_inventory_modification` | `action=update_product` | `inventory_write_forbidden` |
| `create_incident` | `category=not-a-category` | `validation_failed` |
| `update_incident_status` | `incident_id=HC-100001` | `validation_failed` |
| `query_incidents` | `incident_id=not-a-uuid` | `validation_failed` |

`create_incident` paths were `/auth/login` and `/api/incidents`. `EVIL_HOST_REQUESTED False`. The unknown-action result is the same `INVENTORY_WRITE_ACTIONS` membership the tool uses. The incident-id results execute `_require_incident_id` from `server.py`.

Logging events named by the plan:

| Event | Class | Basis |
| --- | --- | --- |
| Failed login | Source absence, and the line was missing from the earlier journal sample | `auth.py` login raises `HTTPException` and has no logger. |
| Inactive user | Source absence. Runtime not executed | The same login function raises for an inactive user and has no logger. The live TinyDB handle caches `auth.json`, so an out-of-band edit was not used. |
| Credential denial | Source absence. Runtime `401` observed | `deps.py` has no logger. `GET /auth/me` with a non-JWT bearer returned `401`. The following journal sample did not contain the credential detail. |
| Rejected chat socket | Log call exists. Observed missing from the journal | `chat.py` logs the rejection. The earlier close `1008` sample had count 0. |
| Accepted chat socket | Log call exists. Observed missing from the journal | This pass received `session_snapshot`. The following 80 journal lines contained 0 copies of that sentence. |
| Telemetry ingest | Log call exists. Observed missing from the journal | `telemetry.py` logs `event_type`. The earlier batch's journal count was 0. |
| Frontend `user_login_failed` | Observed sent. Not durable | A browser sign-in on `https://150.136.171.59/login` with an unknown account stayed on `/login` and showed `Incorrect email or password`. The page `fetch` to `/auth/login` returned `401`. A following `fetch` to `/telemetry/events` returned `200` and the event types were `api_request_completed` and `user_login_failed`. `telemetry.py` does not persist the batch. The password was not copied. |
| Logout | Source and built name. Emission not observed | `AppShell.tsx` and `lib/auth/api.ts` call `track` for `user_logout_completed`. The name is in 10 built files. No browser logout was captured. |
| Denied page | Source absence on the guard | `AuthGuard.tsx` redirects to `/login` and does not call `track`. `authorization_denied` is sent only from `api.ts` after HTTP `403`. |
| Knowledge or agent exception | Log call exists. Runtime not executed | `knowledge.py` and `agent.py` call `logger.exception` on failure. This pass's knowledge query returned `200`, so that branch did not run. |
| Denied tool call after restart | Runtime not executed | `invocation_log.py` would log tool, client, and result. The MCP server is not running. The in-process probe does not write that log. The guardrail counter reset does not cover it. |
| Generation failure after restart | Runtime not executed | A generation failure was not triggered. The guardrail counter reset does not cover trace files or this exception log. |

## 5. Service privilege

`id healthcore` returned `uid=997(healthcore) gid=986(healthcore) groups=986(healthcore)`. `sudo -n -l -U healthcore` exited 0 and printed `User healthcore is not allowed to run sudo on healthcore-vcn.` The account was not changed. The earlier recapture `sudo -n -l` is `ubuntu`, not `healthcore`.

## 6. Requirement reading and unfinished applicability

REQ-PHI-02 asks for the stored field names compared with the rule that the log records the action and not the clinical content. The stored names are `guardrail`, `action`, and `failure_type`. Those names are not clinical text. That comparison meets REQ-PHI-02. It does not meet actor, action, and time.

REQ-CLIN-05 keeps the actor, action, and time comparison. The same three fields fail it. Severity remains low. No audit feature was added.

REQ-CLIN-04 stays the phase 4a cancellation answer against the 24-hour corpus rule. Severity medium. The prompt was not changed because REQ-REM-01 fixes only critical findings. This is not a critical finding.

`ecdsa` 0.19.2 is installed and is a dependency of `python-jose`. A call from a request into `sign_digest` was not traced. `diskcache` 5.6.3 is installed. No repository Python file imports it, and an unpickle of its cache was not traced. MCP lock pin `pyjwt` 2.14.0 was not installed; the running API has `pyjwt` 2.15.1. Those three stay applicability-unverified. That label is not proof they are non-applicable. The unresolved prerequisite is a traced vulnerable call, or an installed MCP environment for the lock pin. The A06 rows are finished with that label, the advisory id, the range, and the relationship. They are not unfinished inspections, and they are not exclusions.
