# Remaining verification, 2026-10-06

This file records the checks that were still open after `docs/owasp/evidence/2026-10-06-correction-pass.md`. It does not replace that file. No password, token, generated draft, or response body is copied here. Inactive-user login, stored RFP generation, the chat terminal event, and the loopback denied-tool test are in `docs/owasp/evidence/2026-10-06-stage2-results.md`. Sentences below that say those checks were not run are historical. The response-path RFP readback, formatted log records, and journal settings are `docs/owasp/evidence/2026-10-06-bounded-corrections.md`.

The guest API, web service, nginx, and `certbot-renew.timer` were active after these checks. The public MCP service was not started. No package was upgraded.

## 1. Isolated valid requests

Script: `docs/owasp/evidence/2026-10-06-isolated-fixtures.py`.

Real application components: FastAPI app and lifespan, inventory router and `inventory_service`, incident manager router and `incident_service`, RFP approval router and `submit_approval_decision` / `begin_approval`, user registration, and login.

Substituted dependencies: a temporary SQLite file and a temporary TinyDB file outside the repository, `rfp_service.complete_override_fn`, and `rfp_service.checkpoint_override`. The completion function returned a fixed commercial sentence. That substitution is authorization evidence only. It is not the generated-output sample in section 2.

Observed results:

| Check | Result |
| --- | --- |
| Temporary database | `ISOLATED_DIR_IS_TEMP True`, `DATABASE_IS_TEMP_SQLITE True`, `OPERATIONAL_PATH_USED False`, `TEMP_DB_REMOVED True` |
| Anonymous valid product | `401`, clinical-phrase boolean false |
| Anonymous valid incident | `401` |
| Two registrations and two logins | `201`, `201`, both logins `200`, token present and not printed |
| Authenticated product | `201`. Keys: `category`, `clinic_current_stock`, `country`, `current_stock`, `expiry_date`, `id`, `minimum_stock`, `name`, `sku`, `unit`. Clinical-phrase boolean false |
| Authenticated inbound order | `201`. Keys: `clinic_id`, `created_at`, `id`, `quantity`, `supply_id`, `user_uuid`, `vendor_name`. Clinic id `3` |
| Other user's order list | `200`. Clinic ids `1, 2, 3, 4, 10, 11`. Ids `1, 2, 4, 10, 11` come from the temporary seed. Id `3` is the synthetic inbound. The second user can read the first user's clinic |
| Authenticated incident | `200`. Keys: `branch`, `category`, `created_at`, `description`, `id`, `origin`, `status`, `title`, `updated_at`. Description matched the submitted text. Clinical-phrase boolean false |
| Other user's incident read | `200` with the same keys |
| RFP approval start | `202`. Keys: `status`, `ticket_id` |
| Other user's approval decision | `403`, detail `not_department_owner` |

The live `/var/lib/healthcore` stores were not written by this script.

## 2. Generated RFP sample

The guest script loaded the deployed GGUF through `generate_revenue_section` and `complete_local`. `GENERATOR complete_local`. `MODEL_IS_DEPLOYED_FILE True`. Output object fields: `text`, `detected`, `blocked_values`. `DRAFT_CHARS 372`. `PHI_DETECTED False`. `REDACTED False`. `CLINICAL_PHRASES False`. `BLOCKED_VALUE_COUNT 0`. `BODY_RETAINED False`. A later count of files under `/tmp/healthcore-rfp-iso` was `0`. The draft was not copied into this repository.

This is the generated-output sample. The substituted sentence in section 1 is not that sample.

The stored RFP tables on the host were not given this draft. An empty operational RFP table is still not a sample of a stored generated row.

## 3. Frontend events

The login failure already recorded in the correction-pass file was not repeated. The browser sent `user_login_failed` to `/telemetry/events` and received `200`. `services/api/app/routers/telemetry.py` logs `event_type` and does not write the batch.

Logout was captured from the running frontend. The register form created `audit.fe2.20261006@example.com`. The page hook recorded `POST /users` `201`, `POST /auth/login` `200`, and `POST /auth/me` `200`. After Log out, the same page hook recorded `POST /telemetry/events` `200` with event types `user_logout_completed` and `page_viewed`. The token was then absent. The account was deleted with `DELETE` status `204`. A later count of that email in `/var/lib/healthcore/auth/auth.json` was `SYNTHETIC_UI_USER_ROWS 0`.

The denied page was an unauthenticated client navigation to `/` with the hook already installed. The browser finished on `/login` with no token. The hook recorded only `page_viewed` on `POST /telemetry/events` `200`. It did not record `authorization_denied`, `/auth/me`, or `session_expired`. `AuthGuard.tsx` redirects when no token is present and does not call `track`. `authorization_denied` is sent from `lib/auth/api.ts` only after HTTP `403`. This navigation did not produce a `403`.

## 4. Tool-call and generation-failure logs

`tests/pipelines/test_agent_graph.py::test_failed_generation_persists_completed_nodes` passed: `1 passed in 2.78s`.

`docs/owasp/evidence/2026-10-06-logging-isolation.py` then ran the real `run_support_agent` and `persist_trace` path. Retrieval and answer generation were patched. Results: `FAILURE_RAISED True`, `LOG_RECORD_COUNT 1`, `LOG_CONTAINS_SECRET False`, `LOGGER_HAS_FILE_HANDLER False`, `TRACE_FILE_COUNT 1`, `TRACE_ERROR_IS_FAILURE_CODE True`, `TRACE_CONTAINS_SECRET False`. Trace keys: `answer`, `context`, `error`, `lookup_failure`, `node_order`, `nodes`, `question`, `sources`, `thread_id`, `ticket_id`, `ticket_status`, `trace_id`. A second process read the same file: `SECOND_PROCESS_ERROR_IS_FAILURE_CODE True`, `SECOND_PROCESS_HAS_SECRET False`. The temporary trace directory was removed afterward.

The trace file is durable across processes. The logger record is not a file. `audit.py` counters remain a separate in-process mechanism.

`log_tool_invocation` was called directly. The message contained `tool=attempt_inventory_modification`, `client=isolated-reader`, and `result=inventory_write_forbidden`. `INVOCATION_FILE_CREATED False`. `configure_invocation_logging` names `StreamHandler` and does not name `FileHandler`. This call did not execute the FastMCP wrapper or `tests/test_mcp_acceptance.py`. The tool-call line is an in-process log from that direct call. A later sentence that treats the missing `FileHandler` as the absence of every durable store is historical. The API journal and trace files are in `docs/owasp/evidence/2026-10-06-bounded-corrections.md`.

## 5. ecdsa, diskcache, and MCP PyJWT

Guest script: `docs/owasp/evidence/2026-10-06-dependency-callers.py`. Installed versions from the API virtualenv: `ecdsa` `0.19.2`, `diskcache` `5.6.3`, `pyjwt` `2.15.1`, `python-jose` `3.5.0`, `mcp` `1.30.0`. `healthcore-api` was active.

### ecdsa

Locked and installed version: `0.19.2` in `services/api/uv.lock`. `python-jose` `3.5.0` depends on it. Advisory `PYSEC-2026-1325` / `GHSA-wj6h-64fc-37mp` / `CVE-2024-23342` is the Minerva timing issue in ECDSA signing. No fixed release is recorded for that advisory.

Callers: application code calls `jose.jwt.encode` and `jose.jwt.decode` in `services/api/app/core/security.py` with `settings.jwt_algorithm`. The guest inspection shows `HS256` is in the HMAC algorithm set and is not in the EC set. `ES256` is in the EC set. `ECDSAECKey` is `jose.backends.ecdsa_backend`. The HMAC key class is `jose.backends.cryptography_backend`.

Inspection of this dispatch is complete. The unresolved exploitation prerequisite is an ECDSA sign or verify, such as `ES256`. The current application path and the isolated run use `HS256`, which does not select the ecdsa backend.

### diskcache

Locked and installed version: `5.6.3`. `llama-cpp-python` `0.3.35` depends on it. Advisory `PYSEC-2026-2447` / `GHSA-w8v5-vhqr-4h9v` / `CVE-2025-69872` has no fix. The vulnerable operation is unpickling a cache.

Callers: no repository Python file imports `diskcache`. In the installed `llama_cpp` tree, only `llama_cache.py` contains `diskcache`. That file imports `diskcache` and does not contain `pickle`. Classes: `BaseLlamaCache`, `LlamaRAMCache`, `LlamaDiskCache`. `diskcache.Cache` is constructed in `LlamaDiskCache`. `llama.py` imports `llama_cache` and names those classes. `Llama.__init__` has no cache assignment and no cache call (`LLAMA_INIT_CACHE_USES none`). `complete_local` constructs `Llama` without a cache argument.

Inspection of this path is complete. The unresolved exploitation prerequisite is a caller that constructs `LlamaDiskCache` and loads an untrusted cache. The generation path in section 2 did not do that.

### MCP PyJWT

Two pins exist. The running API lock and virtualenv have `pyjwt` `2.15.1`. `GHSA-42vr-xj54-vc7v` / `PYSEC-2026-4141` were introduced in `2.0.0a1` and fixed in `2.15.0`. `GHSA-x33g-cr3x-6449` was introduced in `2.1.0` and fixed in `2.15.0`. The installed API version is outside both ranges.

`mcps/healthcore-tools/uv.lock` pins `pyjwt` `2.14.0`, which is inside both ranges. That environment is not installed. The published `mcpauth` `0.2.0b1` wheel was read without installing it. `mcpauth/auth/token_verifier.py` calls `jwt.decode` with `options={"verify_signature": False}`. `mcpauth/utils/_create_verify_jwt.py` imports `PyJWKClient` and calls `get_signing_key_from_jwt`. Those are the functions named by the recursion advisory. The scanned wheel files did not contain the literal `OKP`.

Repository callers: `mcps/healthcore-tools/src` does not import `jwt`. `server.py` passes the string `"jwt"` to the mcpauth bearer middleware. `tests/oidc_fixture.py` imports `jwt` and calls `jwt.encode` with `RS256`. The API virtualenv's `mcp` `1.30.0` package calls `jwt.encode` with `RS256` in `client/auth/extensions/client_credentials.py`, against the installed `2.15.1`.

Inspection of these callers is complete. The unresolved prerequisite for the `2.14.0` pin is running the healthcore-tools environment, which is not installed. The OKP advisory's inconsistent OKP JWK was not found in the scanned caller. The pin remains in the affected range. It is not labeled non-applicable.

## 6. Limitations that remain

The three sentences that follow in the original draft of this section are historical. Inactive login, the response-path RFP row, and formatted exception records are in `docs/owasp/evidence/2026-10-06-bounded-corrections.md`.

The knowledge exception result is in `docs/owasp/evidence/2026-10-06-logging-followup.md`. Operational RFP tables still have no generated row. The public MCP service was not started.

No remediation was applied. REQ-SUB-02 stays escalated. Confirmed critical count remains zero.
