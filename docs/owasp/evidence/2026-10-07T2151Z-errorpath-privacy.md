# Error-path privacy boundary completion and authenticated WSS integrity

Baseline pushed candidate before this correction pass: `f11eec087bbddcaab1c0a5cfb1d2954c176cd0dc`.

The earlier evidence file `docs/owasp/evidence/2026-10-07T2113Z-errorpath-privacy.md` is historical. It closed exception-body and validation-`input` reflection, but it still logged `request.url.path`, still copied validator `msg` and submitted keys in `loc`, and treated a single "private-pay" occurrence as stream integrity. Those PASS rows are superseded by this file. Severity remains medium for the historical A09-BE finding. These corrections are not labeled Critical. REQ-SUB-02 stays Pending. Passing these checks does not establish general PHI protection or project-wide readiness.

## Gaps reproduced before this correction

Working directory: `services/api`.

The staged first-pass modules were restored temporarily, then the new gap tests were run:

`uv run pytest ../../tests/pipelines/test_error_path_privacy.py::test_supplier_custom_validator_message_is_not_reflected ../../tests/pipelines/test_error_path_privacy.py::test_supplier_extra_field_key_is_redacted_from_loc ../../tests/pipelines/test_error_path_privacy.py::test_public_validation_errors_redacts_custom_msg_and_dict_keys ../../tests/pipelines/test_error_path_privacy.py::test_unhandled_exception_omits_exception_text_and_raw_url_path ../../tests/pipelines/test_error_path_privacy.py::test_safe_route_template_unmatched_when_no_route -q --tb=line`

Exit code 1. Five failures.

Observed against the first-pass handlers with fully formatted log records (`Formatter.format`, not `getMessage()` alone) and synthetic marker `SYNTH_ERR_PATH_714`:

- `POST /suppliers` with an invalid category returned `422` whose `msg` contained the marker from `SupplierCreate.categories` custom `ValueError` text.
- `POST /suppliers` with an extra body key named as the marker returned `422` whose `loc` contained that submitted key.
- Direct sanitizer output kept custom `msg` text and dictionary keys in `loc`.
- An unexpected failure on `/__error_path_privacy_probe/{token}` logged the raw URL path including the marker.
- `safe_route_template` was absent from the first-pass module.

## Correction

- `safe_errors.safe_route_template` returns the matched Starlette route template, or `<unmatched>` when no route is available. It does not use `request.url.path`.
- `public_validation_errors` keeps `type`, a safe `loc` (schema field names and list indexes; submitted keys become `*`), and a type-based `msg`. It still drops `input` and `ctx`. Custom validator text is never copied.
- `main.py` global handler logs method plus `safe_route_template(request)`.
- Non-manager validation still returns HTTP `422` with the sanitized detail list.
- Authenticated WSS evidence now compares the assembled `token_chunk` stream to `session_snapshot` assistant text for `generation_completed.message_id`, checks contiguous `sequence` values, and distinguishes interrupt versus follow-up by distinct `message_id` values and interrupted snapshot status. Server-only `last_generation.stored_text` is not used.

Reachable schema cases used for handler tests: `SupplierCreate` custom category validator and `extra="forbid"` submitted keys. Dictionary-key `loc` shape from `TelemetryEvent.properties` is covered by the direct sanitizer test; the telemetry router still validates manually through `HTTPException` and is outside this RequestValidationError boundary.

## After, local

Working directory: `services/api`.

`uv run pytest ../../tests/pipelines/test_error_path_privacy.py -q --tb=line`

Exit code 0. `9 passed in 10.38s`.

`uv run pytest ../../tests/pipelines/test_error_path_privacy.py ../../tests/pipelines/test_phi_surfaces.py ../../tests/pipelines/test_agent_memory.py ../../tests/pipelines/test_agent_guardrails.py ../../tests/services/test_chat_websocket.py -q --tb=line`

Exit code 0. `75 passed in 23.34s` (one existing thread-exception warning on the overflow chat test).

Working directory: repository root.

`uv run pytest tests/services/test_streaming_release_gate.py tests/pipelines/test_gated_generation_stream.py tests/pipelines/test_rag.py -q --tb=line`

Exit code 0. `136 passed in 4.49s`.

## Host install

Procedure: `docs/owasp/evidence/2026-10-07-errorpath-deploy.sh`. Backup directory `/var/backups/healthcore-rag-20261007T020559Z`.

| File | Installed SHA-256 |
| --- | --- |
| `safe_errors.py` | `0f84861136f695923f649ab48689db89bc9d3aec3ebfa345b171e099d3e973d6` |
| `knowledge.py` | `5fd0c51e1a33a0d5df1af330bbb2dafc2b4fad302406faf069ee5a8f232efdf6` |
| `agent.py` | `4999a463ebc55796b4306a2eb1584cb1a057e63a320ce63bbcf35b796422d16a` |
| `main.py` | `a7037688c08915d6d76c1cf26a49ec5640c46fddf84c3e51fcdfc7072e89ccca` |

`streaming_release_gate.py` stayed `7567c2d67c3e8abb5f46abda061ab2fa616bff5ff78844379a6e71efaf9d3587`. `rag.py` stayed `0a6e2649fb472c633a62870fb3b6cd16ee0940e0f56b460cf7ba1f2ebda8bae3`. Mode `root:healthcore` `640`. Health `{"status":"ok"}`. API PID `80512`, user `healthcore`, started `2026-10-07T21:51:22Z`. Web PID stayed `45466`. `permitrootlogin` stayed `no`. Firewall, certificate, and renewal hashes were unchanged. Host check printed `ERRORPATH_HOST_CHECK_OK`. Deploy window: `ERRORPATH_DEPLOY_START 2026-10-07T21:51:21Z` through `ERRORPATH_DEPLOY_END 2026-10-07T21:51:26Z`.

The previous host identities from the 21:13Z pass (`safe` `fab10fe4…`, `main` `678b3e8f…`, PID `78676`) are historical.

## Authenticated public WSS on the resulting candidate

Procedure: `docs/owasp/evidence/2026-10-07-public-wss-stream.py`, workstation against `wss://150.136.171.59` after PID `80512` was active. Exit code 0. `PUBLIC_WSS_STREAM_PASSED`.

| Check | Observed |
| --- | --- |
| Register / login | `201` / `200`, token present |
| Completion integrity | `generation_completed` `msg_a8649bfadf58`; 64 contiguous sequences; stream chars 364 equals `session_snapshot` assistant text; private-pay present; listed clinical-term scan `none` |
| Interrupt integrity | interrupted `msg_2043fb72f67d` with snapshot status `interrupted`; stream equals snapshot; follow `msg_d471734b28d4` completed with 10 contiguous tokens; stream equals snapshot; message IDs distinct; texts differ |
| Refusal | completed with 0 streamed tokens; stream equals empty snapshot text; category term absent from streamed/snapshot text |
| Cleanup | probe user removed through `docs/owasp/evidence/2026-10-07-remove-wss-stream-user.sh` |

An unauthenticated close `1008` is not this proof. The refusal path returned no streamed tokens; category absence applies only to streamed and snapshot text, not to any unpublished agent return string. The public protocol does not expose server-only `last_generation` fields, so those were not claimed.

## Limit

These corrections cover the demonstrated agent, knowledge, RequestValidationError, and global-handler branches under test. Other loggers may still attach `exc_info`. Method plus route template remain in the unexpected-failure log line by design. Finite checks do not guarantee later content.

Historical note: the earlier sentence that left telemetry's manual `HTTPException(detail=exc.errors())` path outside this boundary is superseded by `docs/owasp/evidence/2026-10-07T2232Z-errorpath-finalization.md`, which also covers inventory create validation and the final host install on API PID `81774`.
