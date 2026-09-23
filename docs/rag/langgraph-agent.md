# HealthCore LangGraph support agent

This document keeps the Part 1 graph history and describes the current Part 2 branch. The graph still wraps the existing RAG functions. It does not replace `POST /knowledge/query` or `query()`.

## Flow

### Part 1 route (historical)

On the Part 1 graph, `receive_question` sent an empty or whitespace question to `reject_question` and every other question to `retrieve_context`. There was no ticket lookup node.

```text
START
  -> receive_question
       empty or whitespace question -> reject_question -> END
       otherwise -> retrieve_context
                      no chunk returned by retrieve() -> respond_no_information -> END
                      context present -> generate_from_context -> END
```

### Current route

`classify_question` reads the question text and returns `empty`, `ticket`, `knowledge`, or `both`. It does not read a bearer token.

```text
START
  -> receive_question
       empty or whitespace -> reject_question -> END
       ticket -> lookup_ticket -> END
       both -> lookup_ticket -> retrieve_context
                                 no chunk returned by retrieve() -> respond_no_information -> END
                                 context present -> generate_from_context -> END
       knowledge -> retrieve_context
                      no chunk returned by retrieve() -> respond_no_information -> END
                      context present -> generate_from_context -> END
```

`lookup_ticket` is the ticket tool node. After `caller_is_authenticated` is true, it reads the integrated incident service. A combined question runs that lookup first and then `retrieve_context`. The edge to retrieval does not depend on the lookup succeeding. A ticket-only question stops after `lookup_ticket`.

`retrieve_context` calls `retrieve()` in `data/pipelines/rag.py`. That function already drops neighbors below `DEFAULT_MIN_SCORE` (`0.45`). An empty list is the no-context route. `generate_from_context` calls `generate_answer(question, context)` with that stored context. It does not call `retrieve()` or `query()`.

`respond_no_information` returns `insufficient_information_answer()` and does not call the generation model. `query()` still generates when retrieval is empty. That difference is limited to the graph.

## State

Part 1 state was `question`, `context`, `answer`, and `error`. The current graph still has those fields and does not store conversation history.

Current fields also include:

- `caller_is_authenticated`: a boolean. `run_support_agent` sets it only when the argument is true. Missing, or any value other than true, makes `lookup_ticket` return before `get_incident` or `list_incidents`. The token and the user record are not stored.
- `sources`: `rag`, `ticket_tool`, or both, in the order the nodes append them.
- `ticket_clause`: the sentence prepended to a later RAG answer on a combined route.
- `lookup_failure`: empty on success, or `unauthorized`, `unsupported`, `capacity`, `timeout`, `missing`, or `error`.
- `ticket_id` and `ticket_status`: set from a successful read. They are empty when the lookup fails. Title and description are not copied into state.

## Checkpointing

Each run opens a local SQLite file, compiles the graph with that checkpointer, and closes the connection when the run finishes. The installed `SqliteSaver` is lightweight synchronous storage for a single process. It is not a high-concurrency production backend. Overlapping writes to the same file can block or raise a database lock error.

The runtime database is:

`data/process/agent_checkpoints/support_agent.sqlite`

The directory is gitignored. A run passes `thread_id` in the graph config. Reopen the same file and call `get_state_history` with that `thread_id`. LangGraph 1.2 returns that history newest-first. Tests look for persisted intake, retrieval, rejection, no-information, and answer states rather than a fixed snapshot count.

## Traces

These kinds of trace are not interchangeable:

| Kind | What ran | Where it lives |
| --- | --- | --- |
| Deterministic fixture eval | Nothing at eval time. The test reads JSON written earlier. | `tests/pipelines/fixtures/agent_traces/` |
| Patched compiled-graph run | The compiled graph, with `retrieve()` and/or `generate_answer()` replaced by test doubles. | Recorder output and `docs/rag/sample-agent-trace.json` |
| Real retrieval integration | The compiled graph, real `retrieve()` against the indexed knowledge base, generation still patched. | Not stored as a repository export. |
| Older Part 1 real full run | The compiled graph, real `retrieve()` against the embedded `healthcore_knowledge` index, and the configured local GGUF. The graph was invoked directly. FastAPI was not started. | `docs/rag/real-full-run-trace.json` |
| Later Part 1 confirmation | A real run on the Part 1 checkout at commit `56dabc1c833aea30c94ff18c9b573edf8c4cd5fd`. | Trace `faf264e7083048e99411743c92fbb937`. That file is not in this repository. |
| Part 2 ticket, RAG, and failure exports | Runs on this Part 2 branch. | The four `docs/rag/part2-*.json` files below. |

`docs/rag/sample-agent-trace.json` is patched sample evidence. It is the same content as `tests/pipelines/fixtures/agent_traces/referral_grounding.json`. It remains useful for documenting that patched run and the matching deterministic fixture. It is not a real full run, and it is not a Part 2 export.

`docs/rag/real-full-run-trace.json` is the older Part 1 real-run export. It is an exact copy of runtime trace `8ea29e5a9e2d4a34b79d639bf7096821`. That run was recorded from uncommitted working-tree files. It was not executed on the submitted Part 1 commit `56dabc1c833aea30c94ff18c9b573edf8c4cd5fd`. The question was `How long does an internal referral take?`. The recorded node order was `receive_question`, `retrieve_context`, `generate_from_context`. Retrieval used the actual `retrieve()` implementation and the embedded `healthcore_knowledge` index. All three chunks came from `referral-process`. The retrieved referral-policy context contained `11 days`, and that text occurs in `docs/company-knowledge-base/healthcore-referral-process.en.md`. The configured local GGUF produced an answer that also contained `11 days`. That answer is grounded in the three retrieved chunks: the 11-day completed-referral target, escalation after 5 business days, and longer manual handling outside the network. The stored error is empty. The export passed sensitive-data review. It is not one of the Part 2 traces.

The later Part 1 confirmation on commit `56dabc1c833aea30c94ff18c9b573edf8c4cd5fd` recorded trace `faf264e7083048e99411743c92fbb937`. That trace is not stored in this repository, and it is not `docs/rag/real-full-run-trace.json`.

Part 2 exports from runs on this branch:

| File | Trace | What the file shows |
| --- | --- | --- |
| `docs/rag/part2-ticket-trace-open.json` | `8eaab6a0d75e4dc986cbba1d61c10853` | `ticket_tool` only. Nodes `receive_question`, `lookup_ticket`. Status `open` for id `f45414d4-d3fc-4778-a2e3-7ec967fe56b9`. |
| `docs/rag/part2-ticket-trace-in-progress.json` | `3baed5fda45d4ebc9ffde477bcc88907` | Same id after the recorded status change. Status `in_progress`. `ticket_tool` only. |
| `docs/rag/part2-rag-trace.json` | `6bfa05d9b76f4ad89fa2c9ff7298eae9` | `rag` only. `retrieve_context` before `generate_from_context`. The answer contains `11 days`. |
| `docs/rag/part2-failure-trace.json` | `db1edfb59b5d44619302636edb44afd5` | `lookup_failure` is `missing`. The answer is `I couldn't confirm that ticket's status right now`. |

After every run, including a run that raises inside a later node, the graph writes:

`data/process/agent_traces/<trace_id>.json`

The current JSON object contains `trace_id`, `thread_id`, `question`, `node_order`, `nodes` (each completed node's output), `context`, `answer`, `error`, `sources`, `lookup_failure`, `ticket_id`, and `ticket_status`. The older Part 1 export does not contain those last four fields. A node that raises is not listed as completed. Completed retrieval context is kept. The failure `error` value is `graph execution failed`. The file does not contain the exception class, message, or traceback. It does not contain the bearer token or the user record.

Load a trace with `load_trace(trace_id)` from `app.agent.tracing`. On failure, the server log contains `Support agent graph execution failed trace_id=<id>`. That id is not returned to the HTTP client. `POST /agent/query` returns `trace_id` only on success. Unexpected failures stay HTTP 502 with the fixed public message and no traceback.

## Evals

Part 1 fixture evals, from the repository root:

```bash
uv run pytest tests/pipelines/test_agent_evals.py -q
```

Those tests read `tests/pipelines/fixtures/agent_traces/`. They do not compile the graph, call `retrieve()`, or call a model. The referral eval also requires the stored chunk text to occur in `docs/company-knowledge-base/healthcore-referral-process.en.md`.

Regenerate the deterministic fixtures and the patched sample `docs/rag/sample-agent-trace.json` with:

```bash
uv run python tests/pipelines/record_agent_traces.py
```

The recorder runs the compiled graph three times with patched `retrieve()` and `generate_answer()`. The grounding fixture copies the 11-day paragraph from the referral-process document into the retrieved context. The patched generator returns an answer only when that context contains `11 days`. Running that command does not create a real full-run export.

## Part 2 routing evals

Run these from `services/api` with that package's environment. A fresh clone does not contain `data/process/qdrant_storage/` or `data/process/models/qwen2.5-3b-instruct-q4_k_m.gguf`.

Default command. Leave `PART2_LIVE_RAG_EVAL` unset. This runs the real incident-service ticket eval, the asset-free knowledge-routing eval, and the missing-ticket failure eval. For the asset-free test, RAG retrieval and generation are patched, and `get_incident` and `list_incidents` have fail-fast guards that prove those reads are not called. The live retrieval test is skipped before any RAG call, so this command does not download a model.

```powershell
uv run pytest --rootdir . ..\..\tests\pipelines\test_agent_phase4_evals.py -q -p no:cacheprovider --tb=short
```

Opt-in live retrieval. PowerShell:

```powershell
$env:PART2_LIVE_RAG_EVAL = "1"
uv run pytest --rootdir . ..\..\tests\pipelines\test_agent_phase4_evals.py -q -p no:cacheprovider --tb=short -k test_knowledge_eval_uses_real_retrieval_and_local_generation
```

With that variable set, `test_knowledge_eval_uses_real_retrieval_and_local_generation` checks the local Qdrant collection file and GGUF before calling the graph. If either file is absent, the test fails and does not download a model or substitute a mock. When both files exist, it uses real `retrieve()` and local GGUF generation. The published trace for that live run is `docs/rag/part2-rag-trace.json`.

## Endpoint

`POST /agent/query` accepts `{ "question": "..." }`. Success body: `{ "answer": "...", "trace_id": "..." }`.

A missing bearer is allowed for a knowledge-only question and for an empty question. Those requests run the graph. A ticket-only or combined question with no bearer returns HTTP 401 `Could not validate credentials` before `run_support_agent`. A present bearer is accepted only by `get_current_user`. An invalid bearer returns the same 401. The route does not store the token. `lookup_ticket` checks `caller_is_authenticated` again and does not call `get_incident` or `list_incidents` unless that flag is true.

An empty question that reaches the graph returns HTTP 400 with the graph error. Unexpected failures are HTTP 502 with `The knowledge assistant could not generate an answer right now.` The client does not receive a traceback.
