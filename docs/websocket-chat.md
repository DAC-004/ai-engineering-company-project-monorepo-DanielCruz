# Strengthen Task 2: WebSocket chat streaming

## Source and review scope

All three files supplied in `.project_specs/STRENGTHEN YOUR AGENT ENGINEERING/Task 2` were read, including the full screenshot. Hashes are in `websocket-chat-sources.json`. The company briefing governs the Compliance assistant, internal staff identities, entity names and prohibition on patient identifiers/PHI.

The original implementation was already merged in PR #36 (`d37ac3a`), and is present in main `b93a51c`. The existing `feature/websocket-chat` branch was fast-forwarded to that main in a separate worktree. This follow-up audits and verifies that implementation rather than introducing a second app. No agent logic, tools or memory policy changed. Held PR #44 and the unmerged Enhance branches are not silently integrated.

## Reproduced gap and correction

The socket sent `session_snapshot` before subscribing to `chat.<session_id>`. A producer publishing during that awaited send had no subscriber, so the client could miss a token immediately after reconnect. `test_chat_snapshot_order.py` deterministically publishes a fictional policy token during snapshot transmission. Before the fix it times out because the event is lost; afterward it receives snapshot then token. Subscription now happens before snapshot I/O, and the existing `finally` unsubscribes on failure/disconnection. No schema or model change is needed.

The real-model retry test also reproduced a second gap: an unpublished retry replaced stored assistant text after subscribers had seen the original stream. Three focused assertions failed before correction. Finalization now preserves the published transcript and sends any eligible safe extension through the same gate/callback before storing it. The existing correction from held PR #44 was applied only to this chat finalization function; that PR and its unrelated changes were not merged.

A later independent built-UI check exposed a third real gap: reconnect reset the running flag and redirected input was sent as user_message, which the busy backend ignored. The snapshot now exposes the existing generating boolean; the approved UI preserves it, marks a submitted/echoed turn busy before its first token, and synchronizes the interrupt ref with terminal/disconnect events. The same browser case changed from user_message/fail to interrupt_requested/pass. It also checks visible partial preservation/interrupted marking, a separate redirected reply, incremental text, completion to idle, same session, progressive backoff and snapshot-before-token gating. This is an actual code fix, not an explanatory waiver.

## Requirement mapping

| Requirement | Implementation and verification |
|---|---|
| Existing monorepo, named branch, normal layout | `feature/websocket-chat`; socket in services, existing UI in uis and tests in tests. |
| Existing Compliance assistant, no redesigned agent/tools | `chat_channel.py` invokes existing `run_support_agent`; `agent_id=compliance_assistant`. This follow-up changes socket subscription ordering, transcript finalization and reconnect generation-state propagation. |
| Same backoffice JWT, reject before chat events | `authenticate_backoffice_token` uses shared decoder and active staff lookup; missing/invalid token/frame tests. UI uses first auth frame, keeping JWT out of URLs. |
| Bind session/thread identity at handshake | `/ws/chat/{session_id}`, session owner binding, session_id reused as thread_id; contract and second-user rejection tests. |
| Named structured events and entity fields | ChatSession retains session_id, agent_id, staff user_id, status and created_at; event-name contract tests; no RFP/SSE schemas mixed in. |
| Stream while generating, not final-answer replacement | Existing kept-release callback publishes token_chunk with sequence; deterministic streaming/release-gate tests and separate live-model checks. |
| Genuine abort and preserved partial turn | LocalGenerationWatch stop request closes the running model iterator; generation_interrupted keeps partial text/status; redirected input becomes a distinct user/assistant turn. Contract tests assert no old-generation continuation and preserved prior context. |
| Pub/sub, one generation for multiple consumers | SessionHub owns a channel and subscriber queues; two-subscriber test proves one generation and shared events. In-memory, single-process scope is explicit. |
| Existing UI renders incremental tokens and interrupt | KnowledgeQueryForm appends token chunks, marks partial turns interrupted and sends interrupt_requested/new_input while streaming. Daniel explicitly approved the scoped KnowledgeQueryForm.tsx generation-state fix; no other protected UI source was edited. |
| Progressive reconnect and restored history before tokens | UI keeps sessionStorage session_id, backs off 500ms to 8s, waits for session_snapshot, then accepts live tokens. Server restores owner-bound in-process transcript; contract test verifies snapshot precedes next turn. Regressions close snapshot-send event loss and restore the generation-running state so immediate redirects become interrupts. |
| No patient identifiers or PHI in emitted flow | Existing input/event screening and streaming release gate remain unchanged; focused gate tests cover withholding. New regression uses only fictional staff metadata and generic policy text. No patient records or real identities were used. This is bounded test evidence, not a claim of infallible detection. |
| Unit and interruption/reconnect tests | Current deterministic suite and separate local-model suite are recorded in websocket-chat-evidence. |
| Own PR and design answers, tech-lead review | This follow-up PR describes reproduction, testing and answers below; Daniel is asked to review before any merge. |

## Design answers

**Why WebSocket instead of Part 1 SSE?** A staff member must send an interrupt/new_input while the backend is still streaming. The existing socket handles both directions on one session-bound connection. Part 1's RFP notification channel is one-way and its payload contract remains separate.

**How do multiple consumers avoid duplicate agent calls?** Socket handlers subscribe to SessionHub queues. Only start_user_turn schedules one generation for an idle session; the producer fans the same events to all subscribed connections. The current owner restriction allows multiple connections for the same staff identity; it does not grant an unrelated supervisor access. An in-memory backplane is supported by the assignment for one API process. Multiple workers or process-restart recovery would require a shared session/backplane design and are not claimed here.

**Abort versus LangGraph HITL?** request_interrupt sets the active generation watch's stop signal. The local model iterator is stopped/closed, not merely hidden after completion. This path does not use LangGraph interrupt() as a substitute. The already-published partial message remains interrupted, and pending new_input starts a separate turn with prior conversation context. Agent graph behavior and tools remain unchanged.

## Reviewer reproduction

Use the API's existing compatible Python environment with this repository and services/api on PYTHONPATH, offline model/tokenizer assets configured, and disposable identity/SQL/checkpoint/Qdrant paths. Do not use real runtime stores. Run:

```text
python -m pytest tests/services/test_chat_snapshot_order.py tests/services/test_chat_transcript_consistency.py tests/services/test_chat_websocket.py tests/services/test_streaming_release_gate.py tests/pipelines/test_gated_generation_stream.py
```

For real local-model checks, set PART2_LIVE_CHAT_WS=1 and RAG_MODELS_DIR to the existing local GGUF directory, with remote generation keys unset, then run `tests/pipelines/test_live_chat_websocket.py`. This suite substitutes public compliance retrieval context; it proves the real model/socket/cancellation path, not live Qdrant retrieval.

For the UI, install locked dependencies in uis/incidents and uis/talent-pipeline-tracker, then run TypeScript, eslint, Jest and the webpack production build. Use the existing staff Knowledge interface for incremental rendering, interrupt/new question, and reconnect with the same tab session. The current built UI has now passed the controlled headless-browser interaction test in `tests/ui/websocket-chat-interaction.cjs`. Set CHAT_UI_BASE_URL/CHAT_API_BASE_URL to the local built test app/API origins, CHAT_PLAYWRIGHT_MODULE to an installed Playwright module if it is outside normal module resolution, and optionally CHAT_BROWSER_EXECUTABLE/CHAT_UI_EVIDENCE_DIR. The fixture uses fictional authentication and controlled socket events: this proves real UI behavior, while authentication/model behavior is verified in the separate contract/live suites.

## Verification and review state

Current deterministic selection: **96 passed**, zero failures/errors/skips. Real local-model selection: **4 passed**, zero failures/errors/skips, including actual model cancellation, restored context and retry/history consistency. Separate Part 1 SSE compatibility: **9 passed**. Existing UI: **78 Jest tests / 10 suites**, full TypeScript, lint and webpack production build passed. Evidence includes the failed-before assertions and live retry failure, plus final results/JUnit. After the approved UI correction, current types/lint/78 Jest/build and the four real-model tests were rerun and passed.

`websocket-chat-evidence/validation-summary.json` records exact counts and limitations. No new implementation gap is established by these checks; this is bounded evidence, not a claim of universal correctness. Daniel's review and explicit merge approval remain pending. Only the test harness's own failed sandbox run was stopped; existing services and original checkout WIP were preserved. No cleanup, deployment, external communication or merge is authorized by this preparation.
