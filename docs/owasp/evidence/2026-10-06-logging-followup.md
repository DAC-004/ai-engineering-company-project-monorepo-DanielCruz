# Logging follow-up, 2026-10-06

This file finishes the formatted generation-failure check, the tool-log capture distinction, and the knowledge exception path. No traceback, marker, password, or draft text is copied here. Production services were not restarted, and the live auth file was not edited.

## 1. Formatted generation-failure record

Reused procedure: `docs/owasp/evidence/2026-10-06-log-record-format.py`. Reused results: `docs/owasp/evidence/2026-10-06-bounded-corrections.md` section 3.

`docs/owasp/evidence/2026-10-06-logging-isolation.py` checked `record.getMessage()`. That method does not include `exc_info`. It is not the traceback check.

The formatted check uses `Formatter.format`. For the graph `logger.error` record: `FAILURE_EXC_INFO_SET 0`, `FAILURE_FORMATTED_HAS_SECRET False`, `FAILURE_FORMATTED_HAS_TRACEBACK False`. The call does not pass `exc_info`.

The same failure then reached `POST /agent/query`. `ROUTE_STATUS 502`. The body detail is generic. `ROUTE_BODY_HAS_SECRET False`. `app.routers.agent` calls `logger.exception`. `ROUTE_EXC_INFO_SET 1`. `ROUTE_FORMATTED_HAS_SECRET True`. `ROUTE_FORMATTED_HAS_TRACEBACK True`. The formatted record contains the synthetic marker and the traceback text. The trace files do not.

## 2. Tool-log capture

The denied-write test is `mcps/healthcore-tools/tests/test_mcp_acceptance.py` `test_inventory_write_is_rejected_and_data_is_unchanged`. It passed: `1 passed in 12.84s`, recorded in `docs/owasp/evidence/2026-10-06-stage2-results.md`.

The test requests `caplog: pytest.LogCaptureFixture`, sets `caplog` to `INFO` for `healthcore_mcp.invocations`, and asserts that `caplog.text` contains `tool=attempt_inventory_modification client=inventory-reader result=inventory_write_forbidden`. `caplog` is an in-memory handler in the pytest process. The test does not write `caplog.text` to a file. That buffer was not copied into `docs/owasp`. The retained proof is the passing assertion, not a saved log transcript.

The MCP server in that test is a `uvicorn.Server` on a daemon thread in the same pytest process. `configure_invocation_logging` adds a `StreamHandler` to that process when the logger has no handlers. It does not add a `FileHandler`. Pytest's default stream capture was not saved as an evidence file.

`ApiProcess` is a separate subprocess. Its `stdout` and `stderr` are both sent to `api.log` under a `healthcore-mcp-*` temporary directory. `stop()` closes that file and does not delete the directory. At this inspection, nine of those directories were still under the workstation temp folder. Each contained `api.log`, `auth.json`, and `inventory.db`. A boolean scan found the invocation line in none of the `api.log` files. Those files were not copied here. A removal attempt at that time left all nine directories in place because the log files were locked. That sentence is historical. The later cleanup is `docs/owasp/evidence/2026-10-06T221344Z-test-cleanup.md`. `auth.json` was not read into this record.

`healthcore-api` on the host is a different process. `systemctl show` reported `StandardOutput=journal` and `StandardError=inherit`. That unit collects the API service stdout and stderr. It was not the process that emitted the tool line, and it was not restarted. The MCP server is not a systemd unit and was not started. Absence of a `FileHandler` does not describe the API journal or the trace files.

## 3. Knowledge exception

Procedure: `docs/owasp/evidence/2026-10-06-knowledge-exception.py`.

Isolation: temporary SQLite and TinyDB. `OPERATIONAL_PATH_USED False`. `app.routers.knowledge.pipeline_query` was replaced before the request, so retrieval and generation did not run. `PIPELINE_PATCHED True`.

Logger before the probe handler: `KNOWLEDGE_HANDLERS_BEFORE none`. `KNOWLEDGE_PROPAGATE_BEFORE True`. Propagation was turned off for the probe so the formatted record stayed in the capture handler.

Result: `KNOWLEDGE_STATUS 502`. `KNOWLEDGE_DETAIL_IS_GENERIC True`. `KNOWLEDGE_BODY_HAS_SECRET False`. `KNOWLEDGE_RECORD_COUNT 1`. `KNOWLEDGE_LOGGER_NAMES app.routers.knowledge`. `KNOWLEDGE_EXC_INFO_SET 1`. `KNOWLEDGE_FORMATTED_HAS_SECRET True`. `KNOWLEDGE_FORMATTED_HAS_TRACEBACK True`. `KNOWLEDGE_CALL logger.exception`.

The response does not contain the synthetic marker. The formatted record does, because `logger.exception` attaches the traceback. This process was not the production API, so this record was not read from the service journal.

Cleanup: `TEMP_REMOVED True`.
