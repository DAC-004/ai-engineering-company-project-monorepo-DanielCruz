# Error-path privacy and authenticated WSS (historical first pass)

Baseline candidate before this correction: `f11eec087bbddcaab1c0a5cfb1d2954c176cd0dc`.

Historical. Superseded by `docs/owasp/evidence/2026-10-07T2151Z-errorpath-privacy.md`. This pass closed exception-body and validation-`input` reflection on API PID `78676`, but it still logged `request.url.path`, still copied validator `msg` and submitted keys in `loc`, and treated a single "private-pay" occurrence as stream integrity. Do not treat the PASS claims below as the current candidate.

This pass closes demonstrated error-path reflection into logs and responses. Severity remains medium for the historical A09-BE finding. These corrections are not labeled Critical. REQ-SUB-02 stays Pending. Passing these checks does not establish general PHI protection or project-wide readiness.

## Before (isolated)

From `services/api`:

`uv run pytest ../../tests/pipelines/test_error_path_privacy.py -q --tb=line`

Exit code 1. Five failures.

Observed before the handler changes:

- Agent and knowledge `logger.exception` formatted records included the synthetic marker `SYNTH_ERR_PATH_714` and a traceback.
- Knowledge `ValueError` responses returned `detail` equal to the exception text.
- Non-manager validation `422` bodies included Pydantic `input` values containing the marker.
- An unexpected failure path raised through the test client until `raise_server_exceptions=False` was set; the handler used `logger.exception` with method and path.

Historical evidence of the same logger.exception leak: `docs/owasp/evidence/2026-10-06-logging-followup.md` and `docs/owasp/evidence/2026-10-06-bounded-corrections.md`.

## Correction

- Added `services/api/app/core/safe_errors.py` with `log_failure` (no `exc_info`) and `public_validation_errors` (keeps `type`, `loc`, `msg`; drops `input` and `ctx`).
- `knowledge.py`: fixed 400 detail for `ValueError`; unexpected failures use `log_failure`.
- `agent.py`: unexpected failures use `log_failure`.
- `main.py`: non-manager validation uses `public_validation_errors`; the global handler uses `log_failure` and still records method and path only.

Useful non-sensitive metadata remains: fixed detail strings, HTTP status codes, validation type/loc/msg, and method plus URL path on unexpected failures.

## After, local

From `services/api`:

`uv run pytest ../../tests/pipelines/test_error_path_privacy.py -q --tb=short`

Exit code 0. `5 passed in 8.40s`.

`uv run pytest ../../tests/pipelines/test_error_path_privacy.py ../../tests/pipelines/test_phi_surfaces.py ../../tests/pipelines/test_agent_memory.py ../../tests/pipelines/test_agent_guardrails.py ../../tests/services/test_chat_websocket.py -q --tb=line`

Exit code 0. `71 passed in 22.82s` (one existing thread-exception warning on the overflow chat test).

From the repository root:

`uv run pytest tests/services/test_streaming_release_gate.py tests/pipelines/test_gated_generation_stream.py tests/pipelines/test_rag.py -q --tb=line`

Exit code 0. `136 passed in 4.50s`.

## Host install

Procedure: `docs/owasp/evidence/2026-10-07-errorpath-deploy.sh`. Backup directory `/var/backups/healthcore-rag-20261007T020559Z`.

| File | Installed SHA-256 |
| --- | --- |
| `safe_errors.py` | `fab10fe4869eba96d38ffcb877a3150d8c6477f9745e2d6e782576433c813fbc` |
| `knowledge.py` | `5fd0c51e1a33a0d5df1af330bbb2dafc2b4fad302406faf069ee5a8f232efdf6` |
| `agent.py` | `4999a463ebc55796b4306a2eb1584cb1a057e63a320ce63bbcf35b796422d16a` |
| `main.py` | `678b3e8f90726006529781f7ba9e3e3a1d7b6ada2e93ae1bfc29c8a1138406c1` |

`streaming_release_gate.py` stayed `7567c2d67c3e8abb5f46abda061ab2fa616bff5ff78844379a6e71efaf9d3587`. `rag.py` stayed `0a6e2649fb472c633a62870fb3b6cd16ee0940e0f56b460cf7ba1f2ebda8bae3`. Mode `root:healthcore` `640`. Health `{"status":"ok"}`. API PID `78676`, user `healthcore`, started `2026-10-07T21:13:40Z`. Web PID stayed `45466`. `permitrootlogin` stayed `no`. Firewall, certificate, and renewal hashes were unchanged. Installed-module check printed `ERRORPATH_HOST_CHECK_OK`.

## Authenticated public WSS

Procedure: `docs/owasp/evidence/2026-10-07-public-wss-stream.py`, run from the workstation against `wss://150.136.171.59`. Exit code 0. `PUBLIC_WSS_STREAM_PASSED`.

| Check | Observed |
| --- | --- |
| Register / login | `201` / `200`, token present |
| Completion | `generation_completed`, 64 token chunks, 364 characters, private-pay present once, listed clinical-term scan `none` |
| Interrupt | `generation_interrupted`, then a follow turn to `generation_completed` with 10 token chunks |
| Refusal question | streamed token count `0`; category term absent from the stream |
| Cleanup | probe user removed through `docs/owasp/evidence/2026-10-07-remove-wss-stream-user.sh` |

An unauthenticated close `1008` is not this proof. The refusal path returned no streamed tokens for that turn; the category term was absent from the stream. That does not prove the off-stream agent return string for every refusal phrasing. Finite checks do not guarantee later content.

## Limit

These corrections cover the demonstrated agent, knowledge, validation, and global-handler branches under test. Other loggers may still attach `exc_info`. Method and path remain in the unexpected-failure log line by design.
