# Chat worker failure: exception text stays off stderr, logs, and public output

Baseline pushed HEAD: `f11eec087bbddcaab1c0a5cfb1d2954c176cd0dc`.

`_generate_turn` in `services/api/app/services/chat_channel.py` previously let `run_support_agent` exceptions escape the worker thread. The thread printed the exception text and a traceback on stderr. The `finally` block cleared `generating` and left the assistant message `in_progress`. This file records the correction. Its technical severity is unchanged. REQ-SUB-02: Evidence prepared; PR publication verification pending.

## Correction

The worker catches `Exception`, calls `log_failure` with the fixed message `HealthCore chat generation failed`, and sets the assistant status to `failed`. It does not pass `exc_info`. It does not publish `generation_completed`. The existing public event list is unchanged. `finally` still clears the watch and `generating`.

## Local proof

Working directory: `services/api`.

`uv run pytest ../../tests/services/test_chat_websocket.py::test_worker_failure_omits_exception_text_from_stderr_logs_and_public_output ../../tests/services/test_chat_websocket.py::test_first_sample_context_overflow_does_not_complete_the_turn -q --tb=short`

Exit code 0. `2 passed in 5.38s`. The sentinel test drives the real worker thread through the chat socket. Sentinel `SYNTH_CHAT_WORKER_714` is absent from stderr, stdout, formatted logs, and public events. The log line is the fixed failure message. No `generation_completed` event. Assistant status is `failed`. `generating` is false. The watch is cleared.

The same command did not emit `PytestUnhandledThreadExceptionWarning`. That warning is not filtered. The exception no longer escapes the worker, so pytest has no unhandled thread exception to report. The earlier `2249Z` API suite capture that includes the warning remains historical for the pre-fix worker.

Affected suite, same working directory:

`uv run pytest ../../tests/pipelines/test_error_path_privacy.py ../../tests/pipelines/test_phi_surfaces.py ../../tests/pipelines/test_agent_memory.py ../../tests/pipelines/test_agent_guardrails.py ../../tests/services/test_chat_websocket.py -q --tb=line`

Captured stdout: `docs/owasp/evidence/2026-10-07T2315Z-chat-worker-pytest.txt`. Exit code 0. `78 passed in 23.84s`. No warning summary.

Error-path-only and root streaming/RAG captures in `2026-10-07T2249Z-errorpath-pytest.txt` and `2026-10-07T2249Z-root-streaming-rag-pytest.txt` were not rerun. Those modules were not changed.

## Host install

Procedure: `docs/owasp/evidence/2026-10-07-errorpath-deploy.sh`, run with sudo. Backup directory `/var/backups/healthcore-rag-20261007T020559Z`. Captured deploy stdout: `docs/owasp/evidence/2026-10-07T2317Z-chat-worker-deploy.txt`. Exit code 0.

| File | Installed SHA-256 |
| --- | --- |
| `chat_channel.py` | `f219005d89c6c3070bef5c7f74daafa339ec184ae866d9451e7fd4fc04782e7f` |
| prior error-path modules | unchanged from the `2232Z` install |

Host `chat_channel.py` before this install: `47835a74ebd0b23154b7611235d526ca398790e29b8d89ffc239169ad0e23a49`. That hash is historical.

`ERRORPATH_HOST_CHECK_OK`. Health `{"status":"ok"}`. API PID `82558`, user `healthcore`, started `2026-10-07T23:23:46Z`. Web PID stayed `45466`. Gate and `rag.py` unchanged. `permitrootlogin no`. Deploy window `2026-10-07T23:23:45Z` through `23:23:52Z`.

API PID `81774` is historical for the pre-worker-fix finalization. Authenticated WSS success integrity remains `docs/owasp/evidence/2026-10-07T2151Z-errorpath-privacy.md`. The success publish path was not edited. WSS was not re-run.

## Limit

The host check confirms the installed source contains the fixed log line and `failed` status and does not contain `exc_info`. It does not replay the socket sentinel on the host. Finite checks do not guarantee later content.
