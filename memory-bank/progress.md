# Progress

## Milestones completed
- Milestone 1 completed: public HealthCore landing page and care request form implemented at repository root.
- Milestone 2 completed and imported: TypeScript business-logic module present under src/.
- Milestone 3 completed: talent pipeline tracker app present under uis/talent-pipeline-tracker/.

## Current Milestone 4 state
- Branch: milestone-4.
- Prior milestone sources are available in the current working tree per branch source map.
- Human decisions for integration boundaries and operational handling have been recorded.
- Public website migration completed at uis/website with Next.js + TypeScript.
- Backoffice integration completed at uis/backoffice with visible Milestone 2 output rendered on /.

## Work completed in this phase (Agent Infrastructure)
- Created memory-bank/ with projectbrief.md, techContext.md, and progress.md.
- Created root AGENTS.md with repository-specific agent operating rules.
- Created one scoped rule under .agents/rules/.
- Created one reusable skill under .agents/skills/.

## Work completed in this phase (Website Migration)
- Created uis/website as a standalone Next.js + TypeScript app.
- Migrated all approved Milestone 1 landing sections to reusable React components rendered at /.
- Migrated the care request form to /application with client-side validation aligned to Milestone 1 rules.
- Reused authoritative root assets by importing from assets/backgrounds without duplicating files.
- Added website-local build/lint configuration and package scripts.
- Verified runtime rendering for / and /application in the browser.

## Remaining phases
1. Compliance validation and submission preparation.

## Work completed in this phase (Backoffice Integration)
- Created uis/backoffice as a separate Next.js + TypeScript internal app with its own layout and / entry view.
- Imported authoritative Milestone 2 module inputs from src/data/sample and reporting logic from src/utils/transformations.
- Imported and rendered Milestone 2 care-request summaries from src/types/models using getCareRequestSummary.
- Displayed report outputs visibly on screen (metrics, summaries, status distribution, clinic activity, and rendered JSON).
- Kept business logic in one authoritative location under src/ with no duplicated implementation in backoffice source files.

## Validation results (Backoffice Integration)
- npm --prefix uis/backoffice run typecheck: passed.
- npm --prefix uis/backoffice run lint: passed.
- npm --prefix uis/backoffice run build: passed; static / route generated.
- npm --prefix uis/backoffice run dev: started successfully; app served at http://localhost:3000.
- Browser inspection: backoffice-specific layout and visible Milestone 2 output confirmed on /.
- npm --prefix uis/backoffice run test: not available (no test script defined in backoffice package.json).
- Regression check: npm --prefix uis/website run build still passes.

## Validation results (Website Migration)
- npm install in uis/website: completed successfully (warnings about peer dependencies and audit vulnerabilities).
- npm run lint in uis/website: passed.
- npm run build in uis/website: passed; static routes generated for / and /application.
- npm run dev in uis/website: started successfully; HTTP 200 responses confirmed for / and /application.
- Browser inspection: required Milestone 1 landing sections and care request form fields are visible.

## Known blockers or risks
- Risk of accidental modification of Milestone 3 artifact if boundaries are not enforced.
- Risk of accidentally staging .project-input/ if operational files are not filtered before commit.
- Next.js emits a non-blocking warning about multiple lockfiles when running/building uis/website.
- Next.js emits a similar non-blocking multiple-lockfile warning for uis/backoffice.

## Next steps
1. Keep agent infrastructure rules active for all subsequent phases.
2. Start compliance validation phase and fix only approved requirement gaps.
3. Keep .project-input operational files unstaged for submission workflow.
4. Update this file whenever project state changes.

## Milestone 10 streaming-release gate (2026-10-04)
- Branch: `feature/websocket-chat` at `4292180bb851138826085b48f33b5a793a2c6af2` (fast-forward of `origin/feature/support-agent-prerequisite`; no new merge commit).
- Added `services/api/app/services/streaming_release_gate.py`. It evaluates the existing PHI and disclosure detectors character by character. Completed matches stop the gate and drop the open suffix. `interrupt()` and `complete()` also stop the gate and do not flush held text.
- Detector definitions, agent routing, tools, memory, and prompts were not changed.
- `python -m pytest tests/services/test_streaming_release_gate.py -p no:cacheprovider --tb=short`: 13 passed.
- This gate-test result does not establish model streaming, actual generation cancellation, or overall no-PHI compliance.
- Socket integration, tracker UI, and model runs were not started.

## Milestone 10 gated generation stream (2026-10-04)
- `generate_from_context` still calls `generate_answer`. Local sampling in `_local_llm_complete` now uses llama-cpp `stream=True` and `StreamingReleaseGate`. Routing, tools, memory policy, and detector definitions were not changed.
- An interrupt sets a same-thread stop flag, calls `gate.interrupt()`, and closes the llama iterator before another sample chunk is pulled. Grounding retry is skipped after that interrupt.
- Gate tests plus fake-iterator wiring tests: `python -m pytest tests/services/test_streaming_release_gate.py tests/pipelines/test_gated_generation_stream.py -p no:cacheprovider --tb=short` with the API 3.13 environment: 15 passed. The fake iterator does not prove the real model.
- Live check: `PART2_LIVE_GATED_GENERATION=1` and `python -m pytest tests/pipelines/test_live_gated_generation.py -p no:cacheprovider --tb=short -s`. 1 passed in 37.77s. `GENERATION_API_KEY` was unset. The local GGUF was the cached `qwen2.5-3b-instruct-q4_k_m.gguf`.
- First real sampling loop: 55 gate releases, then 63 more content chunks, `finish_reason=stop`, withheld suffix empty because the finished answer closed every open prefix. `generate_answer` then ran one grounding retry, also through the same stream function.
- Interrupt during the same node path: 9 sampled characters, 2 released, unfinished word `covered` dropped, `finish_reason` absent, 0 content chunks after the first release, raw text shorter than the completed sample. This is not universal PHI detection.
- After the pass, interpreter shutdown printed llama `TypeError` in `Llama.__del__`. The pytest result was already success.
- Socket and UI work were not started.

## Milestone 10 backend WebSocket (2026-10-04)
- Backend only. Tracker UI was not started. No commit, push, or pull.
- Added `services/api/app/routers/chat.py` (`/ws/chat/{session_id}`) and `services/api/app/services/chat_channel.py` (in-memory `chat.<session_id>` fan-out, one generation worker). `services/api/app/main.py` registers the router and calls `release_local_llm()` on shutdown.
- `data/pipelines/rag.py` keeps the first grounding sample unpublished. A retry publishes only the replacement while that iterator is still running. A single sample is replayed after the iterator closes. Prior turns are prompt context on the WebSocket worker only.
- Deterministic: `python -m pytest tests/services/test_streaming_release_gate.py tests/pipelines/test_gated_generation_stream.py tests/services/test_chat_websocket.py -p no:cacheprovider --tb=line` with the API 3.13 environment: 28 passed in 7.33s. The chat tests use a stand-in agent.
- Live socket: `PART2_LIVE_CHAT_WS=1` and `python -m pytest tests/pipelines/test_live_chat_websocket.py::test_live_socket_streams_and_interrupt_stops_the_model -p no:cacheprovider --tb=short -s`: 1 passed in 28.56s. Qdrant storage is absent, so `retrieve` was patched to the compliance chunk. Generation and cancellation used the local GGUF. Events were `user_message`, `token_chunk`, `generation_interrupted`. Kept attempt index 1, replayed false, discarded 361 characters, published 2, kept attempt interrupted with `finish_reason` absent and one content chunk after the first release. Reconnect's first event was `session_snapshot`, and the next model prompt contained the prior question, the interrupted partial, and the new question.
- Llama lifecycle: a plain process exit after load did not print `TypeError`. Clearing `llama_cpp.llama_cpp.llama_model_free` and then calling `close()` printed `TypeError: 'NoneType' object is not callable`. `release_local_llm()` before that pointer is cleared, followed by a second `close()`, printed `SECOND_CLOSE_OK` and no `TypeError`.
- UI work and overall project completion were not claimed.

## Milestone 10 publication correction (2026-10-04)
- Ordinary samples now publish each gate release during sampling. The post-completion replay was removed. An interrupt no longer flushes unpublished releases.
- A grounding retry still runs. Its replacement is not appended to tokens already published for the first sample, and no new public event was added. The stored answer can therefore differ from the token stream. That mismatch is recorded as `replaced_kept_text`.
- Deterministic: `python -m pytest tests/services/test_streaming_release_gate.py tests/pipelines/test_gated_generation_stream.py tests/services/test_chat_websocket.py -p no:cacheprovider --tb=short`: 30 passed in 7.99s. The scripted tests do not prove the GGUF.
- Live no-retry, `PART2_LIVE_CHAT_WS=1`, `test_live_no_retry_streams_before_the_iterator_finishes`: 1 passed. One attempt, 22 content chunks after the first release, `published_before_iterator_close` true, `finish_reason=stop`, 17 `token_chunk` events before `generation_completed`. The interrupt of a second session published 2 releases and withheld 11 characters, then `generation_interrupted`, with no later `token_chunk`. Retrieval was patched because Qdrant storage is absent.
- Live retry, `test_live_retry_is_not_concatenated_onto_the_streamed_attempt`: 1 passed in 34.04s. First sample streamed 55 releases and 63 later content chunks. Second sample produced 64 releases and published none of them. Token count stayed 55. Stored text was 434 characters and was not the 361-character stream.
- The earlier Llama cleanup result was not re-run. UI work was not started.

## Milestone 10 retry transcript consistency (2026-10-04)
- The chat worker no longer replaces the assistant message with the agent return when that return was not published. Subscribers, stored history, `session_snapshot`, and the next turn's conversation keep the streamed text. The grounding retry still runs. Its answer is recorded as `unpublished_agent_answer` and is not a new public event.
- Scripted check: `python -m pytest tests/services/test_chat_websocket.py -p no:cacheprovider --tb=line`: 11 passed in 8.32s. Both sockets received `STREAMED_TURN.`. The snapshot and the next conversation used that text, not `UNPUBLISHED_REPLACEMENT.`
- Live retry: `PART2_LIVE_CHAT_WS=1` and `test_live_retry_is_not_concatenated_onto_the_streamed_attempt`: 1 passed in 37.96s. Two subscribers received the same 55 tokens. Stored text and the reconnect snapshot were 361 characters. The unpublished replacement was 434 characters and was not the next turn's assistant history. Attempt 2 still produced 64 releases and published none. Retrieval remained patched because Qdrant storage is absent.
- The prior no-retry streaming and interruption results were not re-run. That path already stored the published text.

## Milestone 10 knowledge assistant WebSocket UI (2026-10-04)
- The tracker Knowledge assistant now uses `/ws/chat/{session_id}` with the backoffice JWT and a `sessionStorage` session id. It renders `token_chunk` text as it arrives, sends `interrupt_requested` with `new_input` while streaming, keeps the partial answer marked Interrupted, and shows the redirected reply as a separate assistant message. Reconnect waits 0.5s, 1s, 2s, 4s, then 8s, and replaces the transcript with `session_snapshot` before later tokens.
- Browser session `chat_4f2f775cda63456c`. Generation used the local GGUF. Retrieval was substituted with the referral timing chunk because `data/process/qdrant_storage` is absent. That substitution is not end-to-end retrieval.
- Streaming and interrupt: the first assistant grew `The` then `The internal` then `The internal referral`, stayed visible as Interrupted, and a second assistant message grew separately through `source_document.`
- Same-process drop: status showed `Reconnecting in 0.5s…`, then Connected, with the same two messages and the same session id. A later question left the restored 125-character answer in place while a new assistant message grew from 4 characters to 291.
- While the API process was stopped, the same session id showed reconnect delays of 0.5s, 1s, 2s, and 4s. After that process started again, the snapshot was empty because the chat transcript is in memory. The UI replaced the screen with that empty snapshot. Process restart does not restore the thread.
- `npx eslint` on the two new client files exited 0. Qdrant remains missing. This UI stage is not overall project completion.

## Milestone 10 real retrieval path (2026-10-04)
- `scripts/setup_knowledge_base.py` indexed the existing local Qdrant collection `healthcore_knowledge` at `data/process/qdrant_storage` (gitignored). Summary: 47 chunks, including `compliance-reference` 32. `QDRANT_URL` was unset, so the established embedded-storage path was used. No retrieval substitute was used for the application run.
- The unpatched API and tracker served session `chat_58b5026898b34b43` with local GGUF generation. `GENERATION_API_KEY` was unset.
- The HIPAA question retrieved three `compliance-reference` chunks, including the minimum-necessary rule and the HIPAA permitted-uses rule. The UI grew the assistant text from 2 to 10 to 17 to 21 characters, then kept `A covered entity may ` marked Interrupted.
- The UK GDPR `new_input` retrieved five `compliance-reference` chunks, including the Article 9 rule. A separate assistant message grew and remained `Under UK GDPR, processing health information requires both a lawful basis under Article 6` through 827 characters. The trace answer is 987 characters; the screen was not replaced with that longer return.
- Closing the socket on the same API process recorded `Connected`, then `Reconnecting in 0.5s…`, then `Connected`. The same session id and the same four messages were still on screen, including the Interrupted partial.
- Chat history is still in memory. This stage did not add persistence across an API process restart.
- Tracker checks from `uis/talent-pipeline-tracker`: `npm run lint` exited 0, and `npm run build` (`next build --webpack`) exited 0 after `Finished TypeScript in 3.1s`. There is no separate typecheck script.
- This retrieval run is not overall project completion.

## Milestone 10 final audit (2026-10-04)
- Rerun this audit: `python -m pytest tests/services/test_streaming_release_gate.py tests/pipelines/test_gated_generation_stream.py tests/services/test_chat_websocket.py -p no:cacheprovider --tb=line -q` with the API 3.13 environment: 31 passed in 8.54s.
- Earlier live GGUF, two-subscriber retry, browser streaming, and real-retrieval evidence was reused. Those code paths were not changed after the accepted runs. Frontend `npm run lint` and `npm run build` were not rerun.
- The worktree extends `run_support_agent` through `/ws/chat/{session_id}` and the existing Knowledge assistant. Agent graph, routing, tools, and memory files are unchanged in the worktree.
- Privacy controls do not amount to universal PHI detection. Chat history remains in memory for the life of the API process.
- Audit conclusion: ready for the user to commit and prepare the pull request. No commit, push, pull, or pull request was made.

## Milestone 10 auth-frame log correction (2026-10-04)
- The normal Knowledge assistant and the successful chat tests connect to `/ws/chat/{session_id}` with no query string, then send one `auth` frame. Query-string JWT validation remains available. The invalid-query test still uses the placeholder `not-a-backoffice-jwt` and expects HTTP 403. A client that disconnects during the auth wait is closed without an ASGI traceback.
- Focused rerun after that change: `python -m pytest tests/services/test_chat_websocket.py -p no:cacheprovider --tb=line -q` with the API 3.13 environment: 12 passed in 9.07s. Missing credentials, an invalid query placeholder, and an invalid auth frame are still rejected before chat events.
- Browser session `chat_1b6e7530299d4497` showed Connected. The open chat socket path was `/ws/chat/chat_1b6e7530299d4497` with no search string. The API access log accepted that path three times. Counts in that log: `token=` 0, `eyJ` 0, ASGI traceback or `WebSocketDisconnect` 0.
- `tests/pipelines/test_live_chat_websocket.py` now sends the same auth frame. Those live GGUF tests were not rerun. Gate, generation, and publication code were not changed.
- The earlier audit's query-string token-logging limitation is closed for the normal connection and verification workflow. `4292180` remains the inherited prerequisite commit. The user's later commit will be the submission HEAD. No commit, push, pull, or pull request was made. PR #35 was left open.

## Milestone 10 retry context-window correction (2026-10-04)
- Published HEAD `a7cb5f19bcd0a9e3784b49fda178f6ecb8a82ec1` left the Knowledge assistant in the streaming state when an unpublished grounding retry exceeded the local 2048-token window. The first sample had already been published.
- `generate_answer` now keeps that published text when the retry raises the sampler's context-window `ValueError`. The same error on the first sample still raises. Other retry errors still raise. Conversation history is not discarded, and retries are not disabled.
- Focused tests: 37 passed in 12.09s. Browser session `chat_1b6e7530299d4497` interrupted the first answer, completed the UK GDPR redirection, reconnected, kept a 660-character follow-up after the retry overflow, completed a later question, and restored all eight messages on a second reconnect. No generation-worker exception was logged. This correction is not staged.

## OWASP audit (2026-10-05)
- Branch `feature/owasp-top10-audit` at `d37ac3a3020e5c4d34ee42fddf73097ea03adc7c`. Implementation is approved. No commit, push, or pull.
- Before-state guest recapture is filed at `docs/owasp/evidence/2026-10-05T234354Z-guest-readonly-recapture.txt`. Workstation TCP results are in `docs/owasp/evidence/2026-10-05T234219Z-workstation-tcp-reachability.txt`. REQ-START-04 before-state inspection is recorded. Hardening is not complete.
- Later firewall edits must retain the OUTPUT jump to `169.254.0.0/16` and the `InstanceServices` chain from that `iptables-save`.
- Source-based classification is revised in `docs/owasp/owasp-top10-audit.md`. It is not runtime-final. Genuine critical count on that source evidence remains zero. REQ-SUB-02 stays escalated. Submission readiness stays blocked.
- Excluded critical advisories are recorded with identifier, locked version, exploitation prerequisites, source, and non-applicability evidence. `/_next/image` is treated as implicitly mounted. Demonstration-account severity uses the full privilege map. Absence of a patient-record field is not the severity basis.
- `runtime_data_path` selects the host store only when that store's own directory exists. A parent such as `/var/lib/healthcore` does not select `agent-traces` or `rfp-checkpoints`. Local checkouts without the store directory keep the repository path.
- The 2026-10-05 guest recapture is unchanged. A UTF-8 derivative is `docs/owasp/evidence/2026-10-05T234354Z-guest-readonly-recapture.utf8.txt`. `2026-10-06T004400Z-loopback-runtime.txt` is a summary, not a transcript.
- Current command capture: `docs/owasp/evidence/2026-10-06T011150Z-phase4a-command-capture.txt`, guest clock 01:11:50Z through 01:12:37Z. Both services run as `healthcore` on loopback. `QDRANT_URL` is unset. The four runtime stores resolve under `/var/lib/healthcore`. `sshd` is still `permitrootlogin prohibit-password`. `InstanceServices` is retained. The image-route HTTP 400 does not exclude the AVIF advisory.
- Coverage checks are in `docs/owasp/evidence/2026-10-06T012032Z-audit-coverage.txt`. The hidden-instruction fixture returned the fixed refusal. Website, backoffice, and MCP advisory comparisons are filed. Zero confirmed critical findings. Classification is incomplete while `GHSA-2xp9-vwfh-vxw4` is applicability-unverified. REQ-SUB-02 stays escalated.
- Phase 4b modes are applied. Evidence: `docs/owasp/evidence/2026-10-06T013216Z-phase4b-permissions.txt`. The GGUF is `root:healthcore` `640`, and an append open as `healthcore` was denied. Supplier records use `/var/lib/healthcore/suppliers/suppliers.json`. Statements that `healthcore` does not exist are historical baseline only.
- Guest firewall reload is verified after setting `IPTABLES_RESTORE_NOFLUSH=no`. Evidence: `docs/owasp/evidence/2026-10-06T021622Z-firewall-reload-and-acme.txt` and the four rule files with that timestamp. Live rules match the persistent files. `InstanceServices` has 17 lines and one OUTPUT jump. Ubuntu SSH printed `UBUNTU_AFTER_RELOAD`.
- Public TCP 80 reached the guest. Synchronized evidence: `docs/owasp/evidence/2026-10-06T024540Z-public-http-reachability.txt`. Workstation 2026-10-06T02:45:40Z received HTTP 200 and `healthcore-acme-probe`. Guest tcpdump showed the SYN, handshake, GET, and HTTP 200. Daniel confirmed the missing OCI fields were TCP 80 and TCP 443 ingress on Default Security List for healthcore-vcn. Both are now stateful from `0.0.0.0/0`, source ports All, destination ports 80 and 443. A retest at workstation 2026-10-06T03:01:58Z again returned HTTP 200 and `healthcore-acme-probe`. The guest firewall was not changed. Staging certificate was issued and deleted. Production certificate issuer is `CN=YE1`, SAN `IP Address:150.136.171.59`, valid 6 days. Deploy hook at 02:51:46Z passed `nginx -t` and reload. Timer is enabled and active. `certbot renew --dry-run` exited 0. Public HTTPS and authenticated WSS passed. Evidence: `docs/owasp/evidence/2026-10-06T025146Z-certificate-and-tls.txt`.
- Retrieved-document fixture passed at guest 02:56:05Z. Script and output: `docs/owasp/evidence/2026-10-06-retrieved-document-fixture.py` and `docs/owasp/evidence/2026-10-06T025605Z-retrieved-document-fixture.txt`. New path probe passed at guest 02:51:47Z. Script and output: `docs/owasp/evidence/2026-10-06-path-probe.py` and `docs/owasp/evidence/2026-10-06T025147Z-path-probe.txt`. The earlier `SELECTION_CHECKS_PASSED` script remains unretained.
- Tracker rebuilt at guest 02:58:44Z through 02:59:04Z with the public HTTPS origin. `BUILD_EXIT 0`. `.next` remains `root:healthcore` `750`. The public login page serves the new chunk, and `127.0.0.1:8000` is absent from `.next/static`.
- Public verification at workstation 2026-10-06T03:09:05Z is `docs/owasp/evidence/2026-10-06T030905Z-public-verification.txt`. Default TLS verification succeeded, the SAN is the public IP, the served scripts use the HTTPS origin, and authenticated WSS returned `session_snapshot`. The synthetic account was removed. No second certificate was requested.
- Renewal proof at guest 03:09:23Z is `docs/owasp/evidence/2026-10-06T030923Z-renewal-proof.txt`. `certbot-renew.timer` is enabled and active. Next trigger is Tue 2026-10-06 12:12:46 UTC. The service command is `/opt/certbot/bin/certbot renew --quiet --non-interactive`. The deploy hook passed `nginx -t` and reload at the same second.
- `GHSA-2xp9-vwfh-vxw4` applicability is complete for this host: remote image URLs are rejected and no AVIF file is deployed. Confirmed critical count remains zero. REQ-SUB-02 stays escalated. No commit, push, pull, or submission.
- Correction after guest 03:25:53Z: the bullet above overclaims the AVIF exclusion. No `.avif` filename does not mean no local URL can supply AVIF bytes. `hasLocalMatch` allows every local path, and `sharp(buffer).metadata()` ignores the extension. A benign scan of 52 files under the deployed tracker `public` and `.next/static` found no AVIF magic bytes. Applicability is unverified again. Confirmed critical count remains zero. The inspection is `docs/owasp/evidence/2026-10-06-obligation-inspection.md`. The matrix is `docs/owasp/requirement-matrix.md`. Path stats are `docs/owasp/evidence/2026-10-06T032553Z-path-stats.txt`. The sanitized deploy hook is `docs/owasp/evidence/sanitized/healthcore-nginx`. CLIN-04 comparison failed against `docs/company-knowledge-base/healthcore-appointment-policy.en.md` lines 9-17 and is not a critical finding. REQ-SUB-02 stays escalated. No commit, push, pull, or submission.
- Later remaining checks are `docs/owasp/evidence/2026-10-06-remaining-checks.md`. The deployed GGUF SHA-256 in the phase 4a capture lines 132-134 already matches the Hugging Face LFS oid. That file was not hashed again. AVIF is not applicable to the current responses because local URLs are accepted and those responses are not AVIF. Loopback route, PHI keyword, MCP boundary, and journal checks were run. Probe users were removed. Confirmed critical count remains zero. REQ-CLIN-04 stays a medium finding and was not remediated. REQ-SUB-02 stays escalated. No commit, push, pull, or submission.
- Correction pass: `docs/owasp/evidence/2026-10-06-correction-pass.md` and `docs/owasp/evidence/2026-10-06-mcp-families.py`. The secret check read assignment contents and the deployed `.next` tree. `healthcore` is not allowed to run sudo. Knowledge and chat samples did not contain the listed clinical phrases. The RFP output sample is missing. A `422` is not authorization proof. REQ-PHI-02 meets the no-clinical-content rule. REQ-CLIN-05 still fails actor, action, and time. `ecdsa`, `diskcache`, and the uninstalled MCP PyJWT pin stay applicability-unverified, which is not non-applicability. Confirmed critical count remains zero. REQ-SUB-02 stays escalated. No commit, push, pull, or submission.
- Self-audit correction: a browser failed sign-in on `/login` stayed on the page, showed the incorrect-credentials message, and sent `user_login_failed` to `/telemetry/events` with HTTP 200. The API still does not persist that batch. The report sentences that said the schema has no failed-login event, that MCP advisories do not apply, and that the guardrail counter is the only detection mechanism are corrected. Logout, a denied page, inactive-user login, RFP output, and generation-failure durability remain unexecuted. Confirmed critical count remains zero. REQ-SUB-02 stays escalated. No commit, push, pull, or submission.
- Remaining verification: `docs/owasp/evidence/2026-10-06-remaining-verification.md`. Valid inventory, incident, and RFP requests ran against temporary databases. Anonymous writes returned `401`, the other user read clinic `3` and the incident, and the other user's RFP decision returned `403` `not_department_owner`. A real `complete_local` draft was 372 characters, the clinical-phrase boolean was false, and the draft was not retained. The browser sent `user_logout_completed` and, for an unauthenticated `/` visit, only `page_viewed`. The synthetic account was deleted. A generation-failure trace file was readable by a second process. `log_tool_invocation` created no file. `ecdsa` stays on the EC backend, `diskcache.Cache` is constructed only by `LlamaDiskCache`, and the MCP `pyjwt` `2.14.0` pin is called by `mcpauth` but that environment is not installed. Inactive-user login remains unexecuted. Confirmed critical count remains zero. REQ-SUB-02 stays escalated. No commit, push, pull, or submission.
- Stage 2 isolation: `docs/owasp/evidence/2026-10-06-stage2-results.md`. Inactive login against a temporary TinyDB returned `401` `Inactive user` with no log record. Inventory inbound and outbound for clinic `3` were readable by the other user. A `complete_local` draft was stored in temporary SQLite, re-read at 231 characters, and removed. A real `generate_answer` chat reached `generation_completed`; retrieval was substituted. The loopback MCP denied-write test passed. The live auth file was not edited. Confirmed critical count remains zero. REQ-SUB-02 stays escalated. No commit, push, pull, or submission.
- Bounded corrections: `docs/owasp/evidence/2026-10-06-bounded-corrections.md`. One new `complete_local` draft was stored with `_store_department_outcome` and read back by `GET /rfp/tickets/{ticket_id}` at 231 characters. PHI and clinical-phrase booleans were false, and the temporary database was removed. An isolated inactive login returned `401` `Inactive user`. Application auth loggers emitted no record. The graph error record has no traceback. The route `logger.exception` record includes the synthetic marker and a traceback. Trace files do not. `healthcore-api` reports `StandardOutput=journal` and `StandardError=inherit`. The MCP unit was not started. Confirmed critical count remains zero. REQ-SUB-02 stays escalated. No commit, push, pull, or submission.
- Logging follow-up: `docs/owasp/evidence/2026-10-06-logging-followup.md`. `Formatter.format` shows the agent and knowledge exception records include the synthetic marker and a traceback. `getMessage()` does not. The denied-write line was in pytest `caplog` and was not saved as a file. Nine leftover `api.log` files did not contain that line. A removal attempt left them locked. They were not copied into the package. The API unit journal is a separate collector. PHI conclusions stay limited to the inspected samples. Confirmed critical count remains zero. REQ-SUB-02 stays escalated. No commit, push, pull, or submission.
- Test cleanup at `2026-10-06T22:13:44Z`: `docs/owasp/evidence/2026-10-06T221344Z-test-cleanup.md`. The nine `healthcore-mcp-*` directories were held by leftover local `uvicorn app.main:app --host 127.0.0.1 --log-level warning` trees. Those trees were stopped. The directories, listeners, and processes were absent afterward. The earlier lock sentence is historical. Production services and the workstation SSH session were not stopped. Confirmed critical count remains zero. REQ-SUB-02 stays escalated. No commit, push, pull, or submission.
- Renewal-log boundary at guest `2026-10-06T22:32:14Z`: `docs/owasp/evidence/2026-10-06T223214Z-renewal-log-boundary.txt`. The deploy hook now appends to `/var/log/healthcore-renewal/certbot-deploy-hook.log`, owned by `root:root`. `healthcore` could not replace the file or the directory. The hook run recorded `NGINX_TEST_EXIT 0` and `NGINX_RELOAD_EXIT 0`. Certificate dates, firewall hashes, nginx site, timer command, and `permitrootlogin no` stayed the same. No new certificate was requested.
- Runtime-path test isolation: `uv run pytest tests/pipelines/test_runtime_data_path.py -q` reported `4 passed in 0.06s`. Evidence: `docs/owasp/evidence/2026-10-06T223200Z-runtime-path-pytest.txt`. The dotenv stub no longer remains after the module load. Application behavior was not changed for the test. Confirmed critical count remains zero. REQ-SUB-02 stays Pending for assignment authority. No commit, push, pull, or submission.
- Final candidate audit: `docs/owasp/evidence/2026-10-06T230641Z-final-audit.md`. Deployed application content matches the uncommitted candidate. Five host files are CRLF and `config.py` is LF. Services stayed active. HTTP 301, trusted HTTPS, public login assets, unauthenticated inventory `401`, owner chat `session_snapshot`, and cross-user close `1008` were current. The first close `1002` was a client frame-length error. `POST /knowledge/query` returned `200` with 241 characters and no listed clinical phrase. Embedded Qdrant is the configured store. Synthetic users were deleted. Root SSH was denied and Ubuntu access continued. The renewal hook, certificate, and `InstanceServices` rules were unchanged. `uv run pytest tests/pipelines/test_runtime_data_path.py tests/pipelines/test_agent_graph.py -q` reported `16 passed in 13.20s`. Confirmed critical count remains zero. REQ-SUB-02 stays Pending. No commit, push, pull, or submission.
- Commit preparation: the proposed staging list is file-by-file. It includes the six runtime-path files, `memory-bank/progress.md`, `tests/pipelines/test_runtime_data_path.py`, `docs/owasp/owasp-top10-audit.md`, `docs/owasp/requirement-matrix.md`, and `docs/owasp/evidence/`. It excludes `docs/owasp/review/`, the root review ZIP, and the root review diff and status exports. Matrix rows that cited those exports now cite the final audit file. No tests were rerun. No application code, host configuration, or production service was changed. No commit, push, pull, or submission.
