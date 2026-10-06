# Bounded corrections, 2026-10-06

These three checks supersede the stage 2 sentences they name. Earlier files stay as historical evidence. No draft text, password, token, or traceback is copied here. `healthcore-api` stayed active. The live auth file was not edited. The MCP service was not started.

## 1. RFP persistence and response path

Procedure: `docs/owasp/evidence/2026-10-06-rfp-persist-path.py` on the guest API virtualenv.

The stage 2 guest script inserted `RfpTicket` and `DepartmentSection` with `Session.add` and then deleted that database. No suitable temporary draft remained, so this script called `complete_local` once. It screened that text, stored it with `rfp_service._store_department_outcome`, and read it back with `GET /rfp/tickets/{ticket_id}`.

Isolation: `/tmp` SQLite and TinyDB. `OPERATIONAL_DB_USED False`. `TEMP_ROOT_IS_TMP True`.

Result: `GENERATOR complete_local`. `SCREEN_PHI False`. `SCREEN_CHARS 231`. `REGISTER 201`. `LOGIN 200`. `PERSISTENCE _store_department_outcome`. `RESPONSE_STATUS 200`. `RESPONSE_PATH GET /rfp/tickets/{ticket_id}`. `SECTION_COUNT 1`. `RESPONSE_DRAFT_CHARS 231`. `RESPONSE_DRAFT_MATCHES_SCREENED_LENGTH True`. `TICKET_PHI_DETECTED False`. `SECTION_CONTAINS_PHI False`. `RESPONSE_CLINICAL False`. `NEEDS_HUMAN_REVIEW False`.

Ticket fields present: `arbitration_state`, `compliance_review_required`, `created_at`, `metadata`, `node_trace`, `part2_handoff`, `part3_handoff`, `phi_detected`, `processing_error_code`, `processing_failed`, `raw_pdf_path`, `sections`, `stalled`, `status`, `synthesizer_summary`, `ticket_id`, `updated_at`.

Section fields present: `approval_revision_count`, `approval_status`, `approved_at`, `approved_content_sha256`, `approver`, `contact_name`, `department_id`, `department_name`, `draft_content`, `evaluation_results`, `iteration_limit_reached`, `key_aspects`, `needs_human_review`, `submitted_by_user_id`.

Cleanup: `TEMP_REMOVED True`. The guest copy of the script was removed. The draft text was not written into this repository.

## 2. Inactive-user login

Procedure: `docs/owasp/evidence/2026-10-06-log-record-format.py`.

Isolation: a temporary TinyDB and SQLite created before import. `OPERATIONAL_PATH_USED False`. The account was created and deactivated through `POST /users` and `PUT /users/{id}`.

Result: `DEACTIVATE 200`. `ACTIVE False`. `INACTIVE_STATUS 401`. `DETAIL Inactive user`.

Logging: handlers were attached to the root logger and to `uvicorn`, `uvicorn.error`, `uvicorn.access`, `app.routers.auth`, and `fastapi`. Records were rendered with `Formatter.format`, which includes exception text when `exc_info` is set. `INACTIVE_RECORD_COUNT 1`. `INACTIVE_LOGGER_NAMES httpx2`. `INACTIVE_EXC_INFO_SET 0`. `INACTIVE_FORMATTED_HAS_SECRET False`. `INACTIVE_FORMATTED_HAS_TRACEBACK False`. `INACTIVE_DETAIL_IN_FORMATTED False`.

`httpx2` is the Starlette test client library. The application auth loggers emitted no record. The password was not in the formatted record. `auth.py` still has no logger, and `main.py` returns an `HTTPException` without calling `logger.exception`.

Cleanup: `TEMP_REMOVED True`.

## 3. Formatted logging, journal collection, and trace files

Same local script. Retrieval and answer generation were patched. The marker was a synthetic exception string. It is not printed here.

Application graph record: `logger.error` in `app.agent.graph` does not pass `exc_info`. `SOURCE_ERROR_PASSES_EXC_INFO False`. `GRAPH_LOGGER_HANDLERS_BEFORE none`. `FAILURE_RECORD_COUNT 1`. `FAILURE_LOGGER_NAMES app.agent.graph`. `FAILURE_EXC_INFO_SET 0`. `FAILURE_FORMATTED_HAS_SECRET False`. `FAILURE_FORMATTED_HAS_TRACEBACK False`. A `StreamHandler` attached for the check received the failure sentence and not the marker or a traceback. `STDERR_STREAM_HAS_SECRET False`. `STDERR_STREAM_HAS_TRACEBACK False`. `STDERR_STREAM_HAS_FAILURE_SENTENCE True`.

Request boundary: `POST /agent/query` returned `502` with the generic detail. `ROUTE_BODY_HAS_SECRET False`. `app.routers.agent` uses `logger.exception`. `ROUTE_RECORD_COUNT 1`. `ROUTE_EXC_INFO_SET 1`. `ROUTE_FORMATTED_HAS_SECRET True`. `ROUTE_FORMATTED_HAS_TRACEBACK True`. `getMessage()` does not include that traceback. The formatted record does.

Trace files: `persist_trace` stores `GRAPH_EXECUTION_FAILED` and does not receive the exception object. `TRACE_FILE_COUNT 1` for the direct call, then `ALL_TRACE_COUNT 2` after the route. `ALL_TRACE_HAS_SECRET False`. `ALL_TRACE_HAS_TRACEBACK False`. Both files were under the temporary directory and were removed. `TEMP_REMOVED True`.

Service journal: `systemctl show healthcore-api` reported `StandardOutput=journal` and `StandardError=inherit`. `inherit` follows stdout, so this unit's stderr is collected by the journal. The service was not restarted. An isolated test process is not that unit.

MCP: `systemctl list-unit-files 'healthcore*'` lists `healthcore-api.service` and `healthcore-web.service` only. The MCP server was not started. `configure_invocation_logging` adds a `StreamHandler` when the logger has no handlers and does not add a `FileHandler`. The earlier loopback acceptance test remains the executed denied-write check. Absence of a `FileHandler` does not describe the API unit journal or the trace files.

The knowledge exception, the formatted generation-failure distinction from `getMessage()`, and the tool-log capture are in `docs/owasp/evidence/2026-10-06-logging-followup.md`.
