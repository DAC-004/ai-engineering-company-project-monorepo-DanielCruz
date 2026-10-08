# Error-path finalization: manual validation paths

Baseline pushed HEAD: `f11eec087bbddcaab1c0a5cfb1d2954c176cd0dc`.

This file closes the remaining manual `ValidationError` reflection paths that the 21:51Z boundary left documented as out of scope. It does not reopen the route-template, supplier RequestValidationError, or authenticated WSS integrity proofs in `docs/owasp/evidence/2026-10-07T2151Z-errorpath-privacy.md`. Those remain valid. Chat code was not changed in this install, so the authenticated WSS result on PID `80512` is reused and not re-run.

Severity remains medium. Not Critical. REQ-SUB-02 stays Pending.

## Gaps before this finalization

Working directory: `services/api`.

`telemetry.py` and inventory product create returned `detail=exc.errors()` after manual `model_validate`. Against that code:

`uv run pytest ../../tests/pipelines/test_error_path_privacy.py::test_telemetry_validation_omits_input_and_submitted_keys ../../tests/pipelines/test_error_path_privacy.py::test_inventory_create_validation_omits_input_and_submitted_keys -q --tb=line`

Exit code 1. Two failures. Synthetic marker `SYNTH_ERR_PATH_714` appeared in `loc` and `input` in the `422` bodies.

## Correction

- `telemetry.py` and `inventory.py` pass `ValidationError.errors()` through `public_validation_errors` before `HTTPException`.
- Status remains `422`. Safe `type`, redacted `loc`, and type-based `msg` are kept.

## After, local

### Narrative summary from the 22:32Z finalization run

Working directory: `services/api`.

`uv run pytest ../../tests/pipelines/test_error_path_privacy.py -q --tb=line`

Exit code 0. `11 passed in 11.36s`.

`uv run pytest ../../tests/pipelines/test_error_path_privacy.py ../../tests/pipelines/test_phi_surfaces.py ../../tests/pipelines/test_agent_memory.py ../../tests/pipelines/test_agent_guardrails.py ../../tests/services/test_chat_websocket.py -q --tb=line`

Exit code 0. `77 passed in 22.88s`.

Working directory: repository root.

`uv run pytest tests/services/test_streaming_release_gate.py tests/pipelines/test_gated_generation_stream.py tests/pipelines/test_rag.py -q --tb=line`

Exit code 0. `136 passed in 2.25s`.

Those three result lines are narrative summaries retained from the finalization session. They are not the durable stdout captures.

### Captured stdout from the 22:49Z documentation-reconciliation re-run

Identical commands were re-executed after the host install. No application code changed between the 22:32Z narrative and this capture. Full command, working directory, pytest stdout/stderr, and exit code are in these files:

| Suite | Capture path | Exit code | Captured summary line |
| --- | --- | --- | --- |
| Error-path | `docs/owasp/evidence/2026-10-07T2249Z-errorpath-pytest.txt` | 0 | `11 passed in 10.97s` |
| API privacy/chat | `docs/owasp/evidence/2026-10-07T2249Z-api-privacy-chat-pytest.txt` | 0 | `77 passed, 1 warning in 22.63s` |
| Root streaming/RAG | `docs/owasp/evidence/2026-10-07T2249Z-root-streaming-rag-pytest.txt` | 0 | `136 passed in 2.14s` |

The API privacy/chat capture includes one `PytestUnhandledThreadExceptionWarning` from `test_first_sample_context_overflow_does_not_complete_the_turn`. The suite still exited 0.

## Host install

Procedure: `docs/owasp/evidence/2026-10-07-errorpath-deploy.sh`. Backup directory `/var/backups/healthcore-rag-20261007T020559Z`. One install for the complete error-path candidate.

| File | Installed SHA-256 |
| --- | --- |
| `safe_errors.py` | `0f84861136f695923f649ab48689db89bc9d3aec3ebfa345b171e099d3e973d6` |
| `knowledge.py` | `5fd0c51e1a33a0d5df1af330bbb2dafc2b4fad302406faf069ee5a8f232efdf6` |
| `agent.py` | `4999a463ebc55796b4306a2eb1584cb1a057e63a320ce63bbcf35b796422d16a` |
| `main.py` | `a7037688c08915d6d76c1cf26a49ec5640c46fddf84c3e51fcdfc7072e89ccca` |
| `telemetry.py` | `b472a24f1477fb8087d1975647d7bd8aac8ceec8effbdf4452f912245721e9df` |
| `inventory.py` | `874f6b88b1b797b8776c0ea0c9964c4df43a43ed75163f42219fc597f7c57742` |

Gate and `rag.py` unchanged. Health `{"status":"ok"}`. API PID `81774`, user `healthcore`, started `2026-10-07T22:32:09Z`. Web PID stayed `45466`. Controls unchanged. `ERRORPATH_HOST_CHECK_OK`. Deploy window `2026-10-07T22:32:08Z` through `22:32:13Z`.

Prior API PIDs `80512` and `78676` are historical for earlier error-path installs.

## Authenticated WSS

Not re-executed. Chat, streaming gate, and `rag.py` were not replaced. Reused evidence: `docs/owasp/evidence/2026-10-07T2151Z-errorpath-privacy.md` (`PUBLIC_WSS_STREAM_PASSED` on PID `80512`). Limits from that file still apply: refusal may complete with zero streamed tokens; category absence is stream/snapshot only; server-only `last_generation` is not a public event.

## Limit

Fixed `users` 409 strings and inventory insufficient-stock messages that embed catalog names are outside this closure. Inactive-login still has no durable application auth record. Finite checks do not guarantee later content.
