## Summary

When the existing classifier accepts an RFP and the stored ticket is still `analyzing`, the API publishes one `rfp_ticket_created` event. The Revenue Cycle workspace shows that arrival in a separate panel. The event carries `ticket_id`, a persisted `rfp_id`, `status` `analyzing`, and `created_at`. Upload, discard, and later completion do not publish a second event.

`rfp_id` is a second UUID stored on the ticket. It is created at accept when it is null, indexed, unique, and never equal to `ticket_id`. Existing classified rows with a null `rfp_id` receive one new id. Discarded rows and analyzing rows with no metadata stay null. `needs_human_review` is only a backfill signal for a row that was already classified. The notification never emits that status.

## Stream

`GET /rfp/tickets/stream` requires the existing JWT through `get_current_user`. The response is `Content-Type: text/event-stream`, with `Cache-Control: no-cache` and `X-Accel-Buffering: no`. Each frame is `id:`, `event:`, and `data:` on consecutive lines, then a blank line:

```text
id: <boot_id>:<sequence>
event: rfp_ticket_created
data: {"ticket_id":"...","rfp_id":"...","status":"analyzing","created_at":"..."}

```

The `data` line is flat JSON. Keepalive comments are about every 15 seconds. The dashboard uses `fetch` and `ReadableStream` with `Authorization: Bearer` and `Accept: text/event-stream`. It does not use `EventSource`.

Send `Last-Event-ID` only after the client has received an id. No header replays the current in-process buffer, then live frames. A known id replays only later frames. A foreign boot id, or an id that has left the buffer, returns `: replay-gap`, then live frames only. The buffer holds 50 frames in the API process. A process restart clears that buffer and starts a new boot id, so an old cursor cannot hide new tickets. There is no broker and no ticket-list refetch.

Start the API from `services/api`. Start the UI with `npm run dev` from `uis/talent-pipeline-tracker` at `http://localhost:3000`. Root `npm start` and `uis/web` also use port 3000 and are a different site.

## Checks

From the repository root, with Python 3.13:

```text
uv run --project services/api --python 3.13 python -m pytest tests/pipelines/test_rfp_classifier.py tests/pipelines/test_rfp_worker.py tests/pipelines/test_rfp_grounding.py tests/pipelines/test_rfp_phi.py tests/pipelines/test_rfp_response_readiness.py tests/pipelines/test_rfp_generator.py tests/pipelines/test_rfp_evaluator.py tests/pipelines/test_rfp_response_loop.py tests/pipelines/test_rfp_approval.py tests/pipelines/test_rfp_arbitration.py tests/pipelines/test_rfp_approval_e2e.py services/api/tests/test_rfp_intake_api.py services/api/tests/test_rfp_approval_api.py tests/services/test_rfp_sse_notifications.py -q
```

Result: 81 passed in 11.12s.

Tracker dependencies were installed with `npm ci` (356 packages). Browser checks used the signed-in tracker against an API whose classifier completion was stubbed. `qwen2.5-3b-instruct-q4_k_m.gguf` was not on disk, so these checks did not classify a PDF with the local model.

- The stream request was `fetch` to `http://127.0.0.1:8000/rfp/tickets/stream` with `Authorization` and `Accept: text/event-stream`.
- A 202 upload while the page stayed on `/` added one panel row: ticket `5c42555f-c7bf-4dba-afcd-f0eee80d097d`, RFP `e50f1ec2-2120-4638-839b-8435461421db`, `analyzing`, `2026-10-01T18:27:49.751788Z`, linked to `/backoffice/rfp/5c42555f-c7bf-4dba-afcd-f0eee80d097d`.
- Immediate open failures waited about 1s, 2s, 4s, 8s, 16s, then 30s. A 2ms pair at the start was the development double mount. After an event, the next wait was about 1s.
- With reconnects refused, a second upload created ticket `60348823-4973-4ac4-bb4c-a226c8140879`, RFP `4f1fba8b-5898-4904-9917-0a98f24fd1bc`, `analyzing`, `2026-10-01T22:46:11.041112Z`. The panel still showed only the first ticket. The reconnect that delivered the missed ticket sent `Last-Event-ID: b11948d23c3a49ee9d6bc7709aa9c40b:1` and received only `id: b11948d23c3a49ee9d6bc7709aa9c40b:2`. The missed ticket appeared once. The first ticket stayed one row.
- The recovery harness did not rewrite `Last-Event-ID`. It rejected the next stream read once. Refused reconnects never opened a body, so that rejection stayed armed until the first allowed reconnect. That read was aborted before the client parsed event `:2`, the open was not established, and the next wait stayed at 30s. The following request still sent `:1` because `:1` was the last id the client had parsed. The `:2` frame was read on that later connection. That was harness timing, not a failure to store the cursor.
- After a later event `7e88820ca0894de983852f703561dbda:1` for ticket `7b3e23a3-2d21-4b1a-9a5c-25b743637a3b`, the unmodified client reconnected with `Last-Event-ID: 7e88820ca0894de983852f703561dbda:1`. The panel stayed at one row for that ticket.

## Design

1. Two users get two independent authenticated SSE responses. They share only the in-process fan-out. Fifty users means fifty connections and fifty queues in one API process. There is no broker. A second API process would not see the in-memory buffer.
2. Recovery is short in-process replay of at most 50 frames. No id replays the whole buffer, then live frames. A known id replays later frames, then live frames. One lock covers the snapshot and subscriber registration, so a publish during that handoff is in the snapshot or on the live queue. The panel keeps one row per `ticket_id`. A foreign boot id or an expired id produces `: replay-gap`, then live frames. A restart clears the buffer and does not reuse a bare integer cursor.
3. SSE is one-way HTTP push with the existing bearer token. A WebSocket fits a later case where the client must send a reaction on the same channel. Approval stays on the existing POST routes. This part does not add a WebSocket.

## Limitation

Live GGUF classification was not run. The file `data/process/models/qwen2.5-3b-instruct-q4_k_m.gguf` was absent. The dashboard API used an isolated classifier stub outside the repository: the classifier role returned accept, the arrival was published, and a later role failed with `model_output_invalid`. The notification module did not call a model. That stub is not a public debug route.

## Review status

Pull request #31 is instructor-approved and merged. Pull requests #32 and #33 were merged so this work could build on the RFP workflow. Their instructor review is still pending. Merging them did not record instructor approval. This description does not publish the SSE pull request and does not request review.
