# HealthCore LangGraph support agent

This is Part 1 of the support-agent migration. It wraps the existing RAG functions in an explicit graph. It does not replace `POST /knowledge/query` or `query()`.

## Flow

```text
START
  -> receive_question
       empty or whitespace question -> reject_question -> END
       otherwise -> retrieve_context
                      no chunk returned by retrieve() -> respond_no_information -> END
                      context present -> generate_from_context -> END
```

`retrieve_context` calls `retrieve()` in `data/pipelines/rag.py`. That function already drops neighbors below `DEFAULT_MIN_SCORE` (`0.45`). An empty list is the no-context route. `generate_from_context` calls `generate_answer(question, context)` with that stored context. It does not call `retrieve()` or `query()`.

`respond_no_information` returns `insufficient_information_answer()` and does not call the generation model. `query()` still generates when retrieval is empty. That difference is limited to the graph.

State fields are `question`, `context`, `answer`, and `error`. The graph does not store conversation history.

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
| Real full run | The compiled graph, real `retrieve()` against the embedded `healthcore_knowledge` index, and the configured local GGUF. The graph was invoked directly. FastAPI was not started. | `docs/rag/real-full-run-trace.json` |

`docs/rag/sample-agent-trace.json` is patched sample evidence. It is the same content as `tests/pipelines/fixtures/agent_traces/referral_grounding.json`. It remains useful for documenting that patched run and the matching deterministic fixture. It is not a real full run, and it is not the pull-request export for live retrieval plus the configured generator.

`docs/rag/real-full-run-trace.json` is the reviewed real full-run export. It is an exact copy of runtime trace `8ea29e5a9e2d4a34b79d639bf7096821`. The question was `How long does an internal referral take?`. The recorded node order was `receive_question`, `retrieve_context`, `generate_from_context`. Retrieval used the actual `retrieve()` implementation and the existing embedded `healthcore_knowledge` index. All three chunks came from `referral-process`. The retrieved referral-policy context contained `11 days`, and that text occurs in `docs/company-knowledge-base/healthcore-referral-process.en.md`. The configured local GGUF produced an answer that also contained `11 days`. That answer is grounded in the three retrieved chunks: the 11-day completed-referral target, escalation after 5 business days, and longer manual handling outside the network. The stored error is empty. The export passed sensitive-data review and is the assignment's real full-run trace export. Creating the pull request, adding its label, attaching eval output, and submitting remain separate pending actions.

After every run, including a run that raises inside a later node, the graph writes:

`data/process/agent_traces/<trace_id>.json`

The JSON object contains `trace_id`, `thread_id`, `question`, `node_order`, `nodes` (each completed node's output), `context`, `answer`, and `error`. A node that raises is not listed as completed. Completed retrieval context is kept. The failure `error` value is `graph execution failed`. The file does not contain the exception class, message, or traceback.

Load a trace with `load_trace(trace_id)` from `app.agent.tracing`. On failure, the server log contains `Support agent graph execution failed trace_id=<id>`. That id is not returned to the HTTP client. `POST /agent/query` returns `trace_id` only on success. Unexpected failures stay HTTP 502 with the fixed public message and no traceback.

## Evals

From the repository root:

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

Default command. Leave `PART2_LIVE_RAG_EVAL` unset. This runs the real incident-service ticket eval, the asset-free knowledge-routing eval, and the missing-ticket failure eval. `test_knowledge_routing_eval_patches_retrieval_and_generation` patches only `retrieve()` and `generate_answer()`. The live retrieval test is skipped before any RAG call, so this command does not download a model.

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

`POST /agent/query` is public. Request body: `{ "question": "..." }`. An empty string is valid input and is routed by the graph. Success body: `{ "answer": "...", "trace_id": "..." }`.

Empty-question graph errors are HTTP 400. Unexpected failures are HTTP 502 with `The knowledge assistant could not generate an answer right now.` The client does not receive a traceback.
