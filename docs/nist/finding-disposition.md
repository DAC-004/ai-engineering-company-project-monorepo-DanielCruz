# Nested OWASP finding disposition

Date: 2026-10-08. This record closes the nested findings that remained under checked audit rows. It does not rewrite the 2026-10-06 observations. The phrases "do not upgrade" and "do not add a control" in `docs/owasp/requirement-matrix.md` are that audit's next-action column. They are not a requirement in `project_specs.md` or `CONTEXT-healthcore.md`. Where the active path shows a defect, this pass changes the code. Where the cited contract or the caller inspection shows the behavior is intended or not reachable, this pass reclassifies it.

## Supplier authentication

| Record | Entry |
| --- | --- |
| Source | OWASP A01 Broken Access Control, recorded in `docs/owasp/owasp-top10-audit.md` A01-BE. The supplier router had no authentication dependency. |
| Component | `services/api/app/routers/suppliers.py`. Create, rate, status, and delete change the directory. List and get are the directory page used by `uis/backoffice` without a login. |
| Evidence | The route file previously accepted those writes with no `get_current_user`. Delete required only the confirmation header, which any caller can send. |
| Correction | Create, rate, status, and delete now require a bearer. Delete still requires the confirmation header after authentication. Anonymous delete returns 401. An authenticated delete without the header returns 428. List and get stay unauthenticated because that is the directory read used by the backoffice page. |
| Disposition | Corrected for mutations. `tests/pipelines/test_nist_protections.py` covers the anonymous 401 and the authenticated 428. |

## Incident-result access

| Record | Entry |
| --- | --- |
| Source | The same A01-BE row, plus A04-BE. A second authenticated user received HTTP 200 for an incident read in `docs/owasp/evidence/2026-10-06-remaining-verification.md`. |
| Component | `GET /api/incidents/results` in `services/api/app/routers/incidents.py`, and the incident manager list in `services/api/app/routers/incident_manager.py`. |
| Evidence | `get_results` documents the payload as aggregate metrics for authenticated operators. `AnalysisResult.to_dict()` returns counts and averages. It does not return `patient_id` or the CSV description. Delete calls `_require_analysis_owner_or_admin`. The manager routes document a shared queue for any authenticated user. |
| Correction | No owner filter was added to the reads. Shared operational output is the written contract. The patient field is omitted from the analysis response, which is covered by the analysis test in `tests/pipelines/test_nist_protections.py`. |
| Disposition | Reclassified. The 200 is authorized operator access, not a missing ownership boundary. |

## A04 records

| Record | Entry |
| --- | --- |
| Source | A04-BE asked for a missing server-side ownership boundary, or the search that found none. The audit named global incident results and global inventory stock. |
| Component | Inventory orders and incident analysis results. |
| Evidence | Inventory: `services/api/app/services/inventory_service.py` states that `clinic_id` does not partition stock. `GET /inventory/orders` returns the list to any authenticated user. `docs/nist/g07-access-correction.md` records that classification. Incident results: the section above. |
| Correction | No ownership filter was added to either read. |
| Disposition | Reclassified. Both reads match their contracts. The matrix sentence "do not add an ownership filter only to close the row" came from the audit next-action column. The contract evidence is what resolves it. |

## A06 dependency

| Record | Entry |
| --- | --- |
| Source | A06-BE, A06-FE, and A06-AG in the OWASP report and `docs/owasp/evidence/2026-10-06-remaining-verification.md` section 5. |
| Component | API virtualenv `ecdsa` 0.19.2 and `diskcache` 5.6.3. Tracker `next` 16.2.9. Uninstalled healthcore-tools lock pin `pyjwt` 2.14.0. Running API `pyjwt` 2.15.1. |
| Evidence | `ecdsa`: application JWT uses `HS256`, which selects the HMAC backend, not ECDSA. The advisory is a timing issue in ECDSA signing, and no fixed release is recorded. `diskcache`: `Llama.__init__` does not construct `LlamaDiskCache`. The advisory is unpickling an untrusted cache. Tracker `next`: the critical Windows image-optimization advisory does not match the Linux host, no `middleware.ts` exists for the middleware-bypass advisory, and `docs/owasp/evidence/2026-10-06-remaining-checks.md` records that served bodies are not AVIF. Website, backoffice, and root `tar` are not the started frontend. MCP `pyjwt` 2.14.0 is inside the range fixed in 2.15.0, and that environment is not installed. The running API pin is 2.15.1, outside the range. |
| Correction | No package was upgraded. An upgrade of an unreached library, or of `next` where the advisory prerequisite is absent, would be optional hardening. |
| Disposition | Reclassified as not exploitable on the active path. The uninstalled MCP pin stays a latent lock entry. It is not a defect in the running API. The audit sentence "no package upgrade was applied" remains true and is not a refusal to fix an active defect. |
| Residual gap | The healthcore-tools lock still pins `pyjwt` 2.14.0, and that environment is not installed. |
| Risk | Installing that environment later would run the pin that 2.15.0 fixes. |
| Proposed mitigation | Install `pyjwt` 2.15.0 or newer before that environment is used. This cycle did not upgrade it. No new severity is assigned here. |

## A08 integrity

| Record | Entry |
| --- | --- |
| Source | A08-FE and A08-AG. |
| Component | `src/index.html` loads `https://cdn.tailwindcss.com` with no integrity attribute. `data/pipelines/rag.py` `_ensure_local_gguf` accepts a non-empty file and does not hash it on read. |
| Evidence | The OWASP report states the CDN script is on the root static page, which is not the selected host frontend. The tracker is installed with `npm ci`. The deployed GGUF digest was compared with the Hugging Face LFS oid in `docs/owasp/evidence/2026-10-06T011150Z-phase4a-command-capture.txt`. That comparison did not show a substitution. |
| Correction | Subresource Integrity was not added to a page that is not the host frontend. A hash-on-read check was not added. Neither is a demonstrated substitution. |
| Disposition | Reclassified as optional hardening. The matrix sentences "do not add Subresource Integrity" and "do not download the model again" match that classification. |
| Residual gap | The root static page still loads the CDN script without an integrity attribute. The GGUF reader still accepts a non-empty file without hashing it on read. |
| Risk | A substituted script on that page, or a substituted model file on a later read, would not be rejected by an integrity check. The cited page is not the host frontend, and the 2026-10-06 digest comparison did not show a substitution. |
| Proposed mitigation | Add Subresource Integrity if that page becomes the served frontend, and compare the GGUF to the recorded digest on read if the file is fetched again. Neither was added in this cycle. No new severity is assigned here. |

## A09 logging

| Record | Entry |
| --- | --- |
| Source | A09-BE, A09-FE, and A09-AG. NIST Detect asks for a durable record of security-relevant failures on the paths this service already owns. It does not ask for a new monitoring product. |
| Component | `POST /auth/login` in `services/api/app/routers/auth.py`. `log_tool_invocation` in `mcps/healthcore-tools/src/healthcore_tools/invocation_log.py`. `services/api/app/routers/telemetry.py`. |
| Evidence | The 2026-10-06 record said inactive login produced no durable application auth record. Tool-invocation lines were in the pytest log buffer and were not a file. Telemetry returns 200 and does not persist the batch. Generation failures already persist in trace files, as recorded in `docs/owasp/evidence/2026-10-06-remaining-verification.md` section 4. |
| Correction | Rejected login and inactive login append a decision line with reason `credentials_rejected` or `inactive`. The line does not contain the account or the password. Tool invocation appends a JSONL file of tool, client, and result code. Telemetry was not given a new collector. Browser events are not the required agent log, and the audit's "do not add a collector" matches that boundary. |
| Disposition | Auth rejection and tool invocation are corrected. Telemetry persistence is reclassified. The gap-closure log records 69 passed and does not contain the pytest arguments. |
| Residual gap | `POST` telemetry still returns 200 and does not persist the batch. |
| Risk | A browser batch can be acknowledged and then discarded, so that batch is not available later as an agent decision record. |
| Proposed mitigation | Persist the batch only if a later requirement names telemetry as the agent log. The implemented agent record is `decision_log.py`. No collector was added. No new severity is assigned here. |
