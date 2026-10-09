# Remaining checks, 2026-10-06

Guest `date -u` was not printed on these commands. They ran after the 03:33:13Z permission-bits file. No certificate, firewall, SSH, TLS, WSS, or renewal command was repeated. The MCP server was not started. No model file was downloaded. Probe accounts `audit.a01a.20261006@example.com`, `audit.a01b.20261006@example.com`, and `audit.routes.20261006@example.com` were deleted. After the first pair, TinyDB counts were `USERS 4` and `PROFILES 0`. Row values, tokens, and the synthetic password are not in this file. The filename-only secret note, the keyword-only PHI conclusion, and the applicability-unverified labels in this file are historical. The correction is `docs/owasp/evidence/2026-10-06-correction-pass.md`. The later caller inspection is `docs/owasp/evidence/2026-10-06-remaining-verification.md`. A `422` in the route table below is validation, not authorization.

## GGUF identity

Two different statements were about two different facts.

The deployed file `/var/lib/healthcore/models/qwen2.5-3b-instruct-q4_k_m.gguf` already has an identity comparison in `docs/owasp/evidence/2026-10-06T011150Z-phase4a-command-capture.txt` lines 132-134. SHA-256 `626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d`. Size `2104932768`. The same line says that digest equals the Hugging Face `paths-info` LFS oid for `Qwen/Qwen2.5-3B-Instruct-GGUF` filename `qwen2.5-3b-instruct-q4_k_m.gguf`. The HEAD etag was the xet hash, not the LFS oid. That comparison is reused. The file was not hashed again.

The loader in `data/pipelines/rag.py` `_ensure_local_gguf` still returns the file when it exists and its size is greater than zero. It does not compute a digest at load time. That missing check is a separate code fact. It does not erase the earlier comparison of the deployed bytes.

## AVIF, GHSA-2xp9-vwfh-vxw4

Local URLs that start with `/` are accepted when `localPatterns` is unset. Remote `http:` and `https:` URLs are rejected when `domains` and `remotePatterns` are empty. The tracker config sets neither. `fetchInternalImage` does not join the URL onto a filesystem path. It calls `handleRequest` for that href and passes the response bytes to `detectContentType`, which calls `sharp` metadata before the `image/` check.

Deployed responses that this handler can return:

- `public/`: `file.svg`, `globe.svg`, `next.svg`, `vercel.svg`, `window.svg`. No other public files.
- `.next/static`: included in the earlier 52-file scan, which found no `ftypavif` or `ftypavis` magic.
- App routes: HTML and JavaScript pages. `route.ts` count is 0. `next.config.ts` has no rewrites.
- No API writer targets the tracker `public` tree.

No deployed response path returns attacker-supplied bytes, and none of the static bodies are AVIF. The advisory prerequisite is therefore not met on this host. The result is not applicable to the current deployment. It is not a confirmed critical finding. Reopen the row if a served body can be AVIF or if `images.remotePatterns` or `images.domains` is set.

## Route requests

Loopback `127.0.0.1:8000` only. Anonymous status, then one `role=user` token. Empty JSON was used for write calls so no business row was created.

| Request | Anonymous | Authenticated user |
| --- | --- | --- |
| GET /suppliers | 200, list 0 | 200, list 0 |
| GET /inventory/products | 401 | 200, 6 products |
| GET /inventory/orders | 401 | 200, clinic ids 1, 2, 4, 10, 11 |
| GET /users | 401 | 200, 6 rows at that moment |
| GET /users/{other id} | not separately anonymous | 200, keys created_at, email, id, is_active, role |
| PUT /users/{self} role admin |  | 403 |
| GET /profiles/me | 401 |  |
| GET /auth/me | 401 | 200, keys email, profile, role |
| GET /api/incidents | 401 | 200, list 0 |
| GET /rfp/tickets/{uuid} | 401 |  |
| POST /telemetry/events | 200, key received |  |
| POST /knowledge/query | timeout at 8 seconds |  |
| POST /inventory/products | 401 | 422 |
| POST /inventory/orders/inbound | 401 | 422 |
| POST /inventory/orders/outbound | 401 | 422 |
| POST /rfp/tickets | 401 | 422 |
| POST /api/incidents | 401 | 400 |
| POST /api/incidents/analyze | 401 | 422 |
| GET /agent/guardrails/summary | 200 | 200 |
| POST /agent/query empty question | 400 | 400 |
| GET /docs | 200 | 200 |
| Chat `ws://127.0.0.1:8000/ws/chat/audita01` with no token | closed 1008 |  |

`GET /users/{id}` does not call `require_self_or_admin`. `list_medical_supplies` does not filter by clinic. Those are the access-control findings. Severity is medium. They are not critical, and no authorization change was made.

## PHI surfaces

Clinical needles searched, without printing matches: `social security`, `medical record`, `date of birth`, `diagnosis`, `prescription`, `patient id`, `mrn`.

- Events: one synthetic `user_login_failed` batch returned `received`. The route does not persist the batch.
- Tables: inventory, RFP, TinyDB users and profiles, and the three sqlite stores. Clinical hit count 0. RFP text tables `rfp_metadata`, `rfp_department_section`, and `rfp_final_document` have 0 rows.
- Responses: field names are the keys in the route table above. `POST /knowledge/query` did not return before the timeout. The earlier synthetic answer remains the knowledge sample.
- Logs: `/var/log/healthcore/certbot-deploy-hook.log` clinical hits 0. The failed-login marker was absent from the last 80 API journal lines. `event_type=` count in the last 50 lines was 0.
- AI outputs: 4 trace files. Keys: `answer`, `context`, `error`, `lookup_failure`, `node_order`, `nodes`, `probe`, `question`, `sources`, `thread_id`, `ticket_id`, `ticket_status`, `trace_id`. Clinical hits 0. Checkpoint and write blobs in the scanned rows also had clinical hits 0.

## MCP tool boundaries

The MCP process was not started. `mcpauth` is not installed in the API virtualenv. These functions were executed from the source tree:

- `clinic_id` 99: `validation_failed`. `None` is allowed.
- Incident id `HC-100001`: `validation_failed`. A UUID is allowed.
- `PATCH /inventory/products/1`: `inventory_write_forbidden`.
- Allowlist accepts `/inventory/products` and `/inventory/orders` and rejects `https://evil.example/inventory/products`.
- `create_incident` with category `not-a-category` and a description that contained `https://evil.example/hook` was sent only to `/auth/login` and `/api/incidents` on the mock base `http://127.0.0.1:8000`. The mock returned HTTP 400. The client mapped that to `validation_failed`. `EVIL_HOST_REQUESTED False`.

`create_incident` does not apply a local enum before that upstream call. The configured base URL is not taken from the tool body.

## Dependency labels

The API virtualenv has 123 distributions. Live versions: `diskcache` 5.6.3, `ecdsa` 0.19.2, `nltk` 3.10.3, `python-jose` 3.5.0, `pyjwt` 2.15.1. Those match `docs/owasp/evidence/2026-10-05-pip-audit-api.json` except that the MCP lock, not this virtualenv, is the `pyjwt` 2.14.0 pin.

- `python-jose` is runtime-used. CVE-2026-85394 stays not applicable while `algorithms` is explicit and `JWT_ALGORITHM` is HS256.
- `nltk` is imported by `data/pipelines/rfp_intake/readability.py` for the local data path. `TransitionParser` and the other named vulnerable helpers are not referenced. The advisory's vulnerable API is not called.
- `ecdsa` 0.19.2 is installed. A direct `sign_digest` call was not traced. Label: applicability-unverified. The advisory is a timing issue the project marks out of scope. It is not critical.
- `diskcache` 5.6.3 is installed. This repository has no direct import. Label: applicability-unverified for whether a dependency unpickles the cache. The cache directory is writable by `healthcore` and is not world-writable. A remote user does not have that write.

Frontend audit totals are in the npm JSON files. Tracker, deployed: 1 critical and 11 high. The critical package is `next`, range `9.3.4-canary.0 - 16.3.5`, locked 16.2.9. Website and backoffice, not started: the same critical `next` range. Root, not started: critical `tar` `<=7.5.20`. High ranges stay in those JSON files. They were not remediated.

## Logging

Failed login returned 401. The journal slice did not contain the password marker or the words `Incorrect email or password`. `Rejected chat socket` count in the last 50 lines was 0 even though the socket closed 1008. `auth.py` `login` still has no logger call. `deps.py` raises `HTTPException` and has no logger call. These absences are the A09 finding. No monitoring process was added.

## Secrets filenames

`git ls-files` for env and key names returned only `.env.example`. Its key assignments are empty placeholders. `.project_specs/` remains ignored.
