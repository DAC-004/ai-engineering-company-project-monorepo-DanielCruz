# Obligation inspection, 2026-10-06

The AVIF and GGUF paragraphs below are the state at the time of this file. `docs/owasp/evidence/2026-10-06-remaining-checks.md` supersedes them. The deployed GGUF digest was already recorded in the phase 4a capture. The AVIF result is not applicable to the current responses.

This file records the correction pass. It does not replace earlier dated captures. Guest clock was not printed on the AVIF or field-name commands. Those commands ran after the path stat at Tue Oct 6 03:25:53 UTC 2026. No image request and no exploit payload was sent.

## AVIF advisory GHSA-2xp9-vwfh-vxw4

The earlier statement that no `.avif` filename means no local URL can supply AVIF bytes is withdrawn. It is not supported.

Deployed tracker config `/opt/healthcore/app/uis/talent-pipeline-tracker/next.config.ts`: `rewrites`, `redirects`, `images`, `remotePatterns`, and `localPatterns` are all absent. Repository `uis/talent-pipeline-tracker` has no `next/image` import and no `rewrites` function. `uis/website` imports `next/image` in Hero, Services, WhyHealthCore, and Contact. That app is not installed or started on this host.

Installed `node_modules/next/dist/server/image-optimizer.js`:

- `hasLocalMatch` allows every local path when `localPatterns` is unset.
- `hasRemoteMatch` is false when `domains` and `remotePatterns` are empty, so a remote URL is rejected before fetch.
- `detectContentType` calls `sharp(buffer).metadata()` on the accepted buffer. The filename is not the content check.
- Local bytes are loaded by `readFile` and by `fetchInternalImage`. An internal fetch can ask the Next server for a local URL. The response body, not the extension, is what `sharp` inspects.
- `optimizeImage` calls `transformer.avif` only when the selected output type is AVIF. Decoding of an accepted AVIF input is a separate step.

Benign byte scan of `/opt/healthcore/app/uis/talent-pipeline-tracker/public` and `.next/static`: 52 files, first 64 bytes, needles `ftypavif` and `ftypavis`, hits 0. `assets` is not a directory. A search of `services/api` found no writer that places bytes into the tracker `public` tree.

This scan does not exclude the advisory. `fetchInternalImage` can request a local path that was not one of those 52 files, including a file whose extension is not `.avif`. Applicability remains unverified. The advisory is not classified as a confirmed critical finding.

## PHI-01 surfaces

Source inspection and deployed column names are separate from runtime values. Row values were not printed.

Events. Envelope fields in `services/api/app/schemas/telemetry.py`: `eventId`, `timestamp`, `sessionId`, `userId`, `event_type`, `schemaVersion`, `requestId`, `properties`. The module says the API validates the envelope and does not persist per-event properties. Tracker allowlist in `uis/talent-pipeline-tracker/lib/telemetry/schema.ts` includes `user_login_failed` with `failure_reason`. The earlier coverage sample accepted one synthetic `user_login_failed` and returned `{"received":1}`. That sample is not the whole event catalog.

Tables. Deployed column names, printed by `/tmp/healthcore-field-names.py` as `healthcore`, after 03:25:53Z:

- TinyDB `/var/lib/healthcore/auth/auth.json` table `users`: `created_at,email,hashed_password,id,is_active,role`, 4 rows. Table `profiles`: 0 rows, so no stored field names. Source `ProfilePublic` fields are `id,user_id,name,phone,address`.
- `inventory.sqlite`: `medical_supply` (`id,name,sku,category,unit,country,minimum_stock,expiry_date`), `supply_delivery` (`id,supply_id,quantity,vendor_name,clinic_id,created_at,user_uuid`), `supply_consumption` (`id,supply_id,quantity,consumption_type,department,clinic_id,created_at,user_uuid`).
- Same database, RFP tables: `rfp_ticket`, `rfp_metadata` (includes `client_name`, `covered_population`, `budget_range`), `rfp_department_section` (includes `draft_content`, `key_aspects`), `rfp_department_account`, `rfp_final_document` (`sections`).
- `approvals.sqlite` contains only the audit probe tables `audit_path_probe_20261006` and `audit_probe`.
- `support_agent.sqlite` contains those probe tables plus LangGraph `checkpoints` (`thread_id,checkpoint_ns,checkpoint_id,parent_checkpoint_id,type,checkpoint,metadata`) and `writes` (`thread_id,checkpoint_ns,checkpoint_id,task_id,idx,channel,type,value`).
- `support_agent_memory.sqlite` contains only the two probe tables.

Free-text columns `draft_content`, `sections`, `checkpoint`, and `writes.value` were not read. Their names do not prove the stored bytes are free of clinical text.

Endpoint response families, from source schemas: `Token`; `UserPublic` (`id,email,is_active,role,created_at`); `ProfilePublic`; `IncidentPublic` (`id,title,description,category,status,origin,branch,created_at,updated_at`); `KnowledgeQueryResponse.answer`; `AgentQueryResponse` (`answer,trace_id,thread_id,memory_proposal`); inventory public models; `TelemetryIngestResponse.received`; `SupplierResponse` (`id,name,country,categories,monthly_rate,currency,updated_at,status,compliance_agreement,contract_renewal_date,contact_email,notes`). One earlier inventory response listed commercial stock keys. That is not a sample of every family.

Logs. `services/api/app/agent/guardrails/audit.py` `record()` logs `guardrail`, `action`, and `failure_type` only. Counts are in-process. `routers/auth.py` login has no logger call. The journal evidence in the coverage and phase 4b files shows uvicorn access lines. It does not show a durable security-event record for every named event.

AI outputs. Phase 4a captured a synthetic appointment answer. The comparison with the corpus is under CLIN-04 below. Chat token events, RFP generation, traces, and checkpoint blobs were not each sampled at runtime.

## PHI-02 and CLIN-05

`audit.py` stores and logs `guardrail`, `action`, and `failure_type`. It does not store actor, action, and time as an access record, and it does not store clinical text. The in-process summary was emptied by the API restart recorded in the phase 4b file. This is not a referral or clinical access log.

## CLIN-04

Synthetic question and captured answer are in `docs/owasp/evidence/2026-10-06T011150Z-phase4a-command-capture.txt`. The answer prefix says a cancellation must be made at least 2 hours before the appointment. It does not cite a file.

Opened corpus file `docs/company-knowledge-base/healthcore-appointment-policy.en.md`:

- Lines 9-10: cancelling more than 24 hours in advance has no charge. Less than 24 hours, or a no-show, is a charge.
- Line 15: reminders are sent at 48h, 24h, and 2h before the appointment.
- Line 17: reschedule from the reminder is available up to 4 hours before the appointment.

The captured answer does not match the 24-hour cancellation sentence. The "2h" in the corpus is a reminder time, not a cancellation deadline. The comparison fails. It is not reclassified as a critical finding.

## A01 route boundaries

Source `Depends(get_current_user)` is present on inventory, incident manager, incident analyzer, users except create, profiles, auth `/me`, and RFP ticket routes. These routes have no bearer dependency: every handler in `routers/suppliers.py`, `POST /knowledge/query`, `POST /telemetry/events`, and `POST /auth/login`. `POST /agent/query` uses `optional_bearer`. `GET /suppliers` returned 200 in the phase 4b file. Inventory clinic columns exist, and the list handlers do not filter by the caller's clinic. Runtime requests were not repeated for every protected route, role, object owner, or cross-clinic pair. A single anonymous 401 does not close A01-BE.

## A08

GGUF path and mode are in the phase 4b file. The file's SHA-256 was not compared with a Hugging Face identity, and the model was not downloaded for that comparison. MCP tool source is `mcps/healthcore-tools/src/healthcore_tools/server.py` (`query_medical_supply_inventory`, `attempt_inventory_modification`, `create_incident`, `update_incident_status`, `query_incidents`). The API caller that is wired is `query_incidents` in `services/api/app/agent/mcp_tickets.py`. The MCP server is not installed or started. Coverage checked one malformed incident payload and the inventory allowlist. It did not send one malformed payload for each tool family. PyJWT advisories stay applicability-unverified for a process that is not running. They are not critical scores.

## A09

Present: uvicorn access lines for login 200/401 and telemetry 200, and the in-process guardrail summary that resets on restart. Absent: a logger in `routers/auth.py` for failed login and inactive user, a durable credential-denial record, a rejected-chat-socket security event, an `event_type=` journal line, and a post-restart record of a denied tool call or generation failure. No monitoring platform was added.

## A10

A keyword search of `page.tsx` and `layout.tsx` is not the result used here. The fetch modules are `lib/api/client.ts`, `lib/auth/api.ts`, and `src/services/telemetry.ts`. Their importers are `"use client"` components and hooks (`LoginForm`, `AuthGuard`, `AppShell`, candidate hooks, inventory components, RFP components, telemetry bootstrap). Server `page.tsx` and `layout.tsx` files import those client components or `Link`. They do not import the fetch modules. No dynamic `import()` was found under the tracker. `lib/api/client.ts` reads `NEXT_PUBLIC_TRACKER_API_BASE_URL`, which was not set in the deployed build. This is static import tracing, not an SSR request log.

## Human confirmation and status audit

REQ-HUMAN-01. Searches of `services/api` and `uis` found no SOAP sign-and-send workflow.

REQ-HUMAN-02. The same search found no patient notifier. `memory_policy.py` and `streaming_release_gate.py` mention withholding lab-result text. They are not a sender.

REQ-HUMAN-03. `docs/company-knowledge-base/healthcore-referral-process.en.md` is the policy file. No share function was found. The file is not a runtime control.

REQ-HUMAN-04. No referral or appointment status-changing route was found. `DepartmentSection.needs_human_review` is an RFP field, not that route.

REQ-AUDIT-STATUS. No status-change audit record exists. `audit.py` is a guardrail counter.

Each absence is not a demonstrated human gate.

## Regulatory comparisons

The four comparisons are separate. Sources are `docs/owasp/evidence/2026-10-06-cfr-excerpts.txt` and `docs/owasp/evidence/2026-10-06-regulatory-excerpts.txt`.

- Deadline: 45 CFR § 164.404 says 60 calendar days. legislation.gov.uk Article 33 says 72 hours and names the Commission. The ICO page is a separate UK practical source for 72 hours. The assignment text is a third source and is not applied as one deadline for both regimes.
- Authority: § 164.408 is notification to the Secretary. Article 33 as opened notifies the Commission. The assignment names the ICO. Those authorities are not interchangeable.
- Access: § 164.524 is access to PHI in a designated record set. Article 15 is confirmation of whether personal data are being processed. This product has no designated-record-set workflow.
- Contract: § 164.504 is the business associate contract. Article 28 is the processor contract. A BAA and a DPA are different instruments. Neither contract is in this repository.

## Component inventory

| Component | Owner named by the assignment | Implementation on this host |
| --- | --- | --- |
| Clinical documentation assistant | Dr. Marcus Reid | Not implemented |
| Automated referral workflow | Dr. Marcus Reid | Policy file only. No notifier. |
| Clinical RAG | Claire Whitfield | No separate service. Deployed retrieval is the compliance corpus. |
| Compliance agent | Claire Whitfield | Knowledge and support-agent paths are deployed. |
| Access audit log | Claire Whitfield | Not implemented. `audit.py` is a guardrail counter. |
| Clinical KPI dashboard | Dr. Sandra Okonkwo | Not present |
| Staff frontend | James Osei | Tracker Knowledge chat is deployed. |

## Protect checklist

REQ-NIST-05 is its own item: logs, events, and outputs were checked for PHI. Printed synthetic samples have no clinical content. Free-text store values were not read, so the item stays open. It is not an access-control finding.
