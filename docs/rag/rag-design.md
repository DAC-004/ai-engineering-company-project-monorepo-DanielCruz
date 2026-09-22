# HealthCore RAG design

This document describes the retrieval-augmented generation assistant used by Priya Nair’s patient coordinators. It is written so another developer can operate and extend the current pipeline without reading every source file.

The authorized corpus is limited to four HealthCore policy and procedure documents. The system never indexes patient records and must never invent coverage, fees, timeframes, referral rules, or required documents.

## 1. End-to-end RAG flow

1. Copy the official English source files from `00-general-contexts/healthcore/` into `docs/company-knowledge-base/`.
2. `setup()` in `data/process/rag.py` reads those four files, splits them into semantic chunks, and recreates the Qdrant collection `healthcore_knowledge`.
3. Each chunk is embedded with `embed()` and stored with the HealthCore payload contract: `company`, `source_document`, `section`, `language`, `chunk_index`, and `text`.
4. A coordinator submits a natural-language question in the backoffice Knowledge assistant or through `POST /knowledge/query`.
5. The FastAPI router calls `query()` from `data/pipelines/rag.py`. It does not search Qdrant or call the generation model itself.
6. `query()` calls `retrieve()`, which embeds the question with the same `embed()` function used at index time, searches Qdrant, and drops neighbors below `min_score`.
7. `query()` passes the surviving payload dictionaries to `generate_answer()`.
8. `generate_answer()` builds a coordinator prompt from the retrieved context and calls the dedicated generation LLM. Company facts come only from those chunks.
9. The endpoint returns `{ "answer": "..." }` only. Source metadata stays in logs, tests, and this document.

```text
Source docs
    -> setup() / semantic chunking
    -> embed(chunk) via BAAI/bge-small-en-v1.5
    -> Qdrant collection healthcore_knowledge
Question
    -> embed(question) via BAAI/bge-small-en-v1.5
    -> retrieve() + min_score
    -> generate_answer() via Qwen2.5-3B-Instruct
    -> POST /knowledge/query { answer }
```

`retrieve()` and `generate_answer()` are separate so a later LangGraph agent can call them independently without running retrieval twice.

## 2. Chunking strategy

The four HealthCore files are short policy documents. They use a title, then labeled rule groups: country sections, cancellation conditions, numbered referral steps, and checklist items.

`chunk_markdown_document()` splits on blank lines and keeps a semantic unit intact: a labeled heading stays with its bullets, an introductory sentence stays with the steps it introduces, and the next titled section is never swallowed.

That keeps the cancellation fee with the Medicare/Medicaid exemption, United States insurance separate from United Kingdom insurance, and the five-business-day escalation rule with Marcus Reid’s role.

| Source document | Chunks | Semantic units |
| --- | ---: | --- |
| `insurance-coverage` | 4 | country overview, US coverage, UK coverage, undocumented-coverage verification |
| `appointment-policy` | 4 | booking, cancellation including Medicare/Medicaid, reminders, repeat no-show flag |
| `referral-process` | 4 | internal steps, 11-day average, 5-day escalation, out-of-network handling |
| `new-patient-checklist` | 3 | pre-visit requirements, documents to bring, incomplete history-form exception |

Total indexed chunks: **15**. Overlap is not used. Indexed vectors include the section title plus the chunk body. Stored `text` remains the chunk body used for prompt assembly.

One-line summary: split on blank lines and keep each rule with its exception.

## 3. Embedding and generation

The default path is local and key-free. Optional `EMBEDDING_*`, `GENERATION_*`, or `LLM_*` variables can point at a remote OpenAI-compatible gateway. Those are overrides, not the default.

| Role | Model ID | Runtime |
| --- | --- | --- |
| Embedding | `BAAI/bge-small-en-v1.5` | FastEmbed ONNX. `embed()` calls `TextEmbedding.embed()`. |
| Generation | `Qwen2.5-3B-Instruct` | llama-cpp. `generate_answer()` calls `Llama.create_chat_completion()` on `qwen2.5-3b-instruct-q4_k_m.gguf`. |

The two model IDs differ. `embed()` never calls the generation model.

- Vector dimension: `384`
- Qdrant distance: cosine
- `min_score`: `0.45`
- Retrieval `k`: `3`

The static prompt contains audience and faithfulness instructions only. It does not name accepted plans, fees, referral timeframes, billing contacts, or required documents. Those facts must appear in retrieved chunks before they may appear in an answer.

After generation, if the model claims a gap while retrieved text already answers the question, or mentions a policy marker that is absent from the retrieved text, the same llama-cpp model is asked once more. The retry is still model generation.

### Local model acquisition and reuse

The GGUF is not committed. The first process that needs it downloads `qwen2.5-3b-instruct-q4_k_m.gguf` from `Qwen/Qwen2.5-3B-Instruct-GGUF` into `data/process/models/` (or `RAG_MODELS_DIR`). Network access is required only for that first download. Place an already-downloaded file in that directory to skip the download. Do not commit model binaries.

If acquisition fails, the process raises a project-level error that names the repository, filename, local directory, and the no-commit rule. The original Hub exception is preserved as the cause.

`_load_local_llm()` caches the llama-cpp object on the module. The first request in a process pays CPU load time. Later requests reuse the same loaded model.

### Threshold tuning

Recall@3 is measured with `k=3` and `min_score=0.0`. Production `min_score=0.45` sits above unrelated cosine scores (0.42 / 0.39) and below in-corpus top hits (0.71–0.79).

## 4. Idempotency

`setup()` deletes `healthcore_knowledge` when it exists, recreates it with size 384 and cosine distance, and upserts `uuid5(namespace, healthcore:{source_document}:{chunk_index}:{section})`.

Qdrant can be reached through `QDRANT_URL` (Docker Compose service `qdrant` or Qdrant Cloud), local embedded storage at `data/process/qdrant_storage`, or `:memory:` for isolated tests.

## 5. Retrieval evaluation

`data/eval/test-queries.json` contains **12** questions covering all four source documents and no PHI. A hit requires the expected `source_document` and `expected_chunk_index` in the top three payloads.

```bash
uv run python scripts/eval_rag_recall.py
```

Measured result with **BAAI/bge-small-en-v1.5**:

- Hits: **12 / 12**
- Recall@3: **100%**
- Collection: `healthcore_knowledge`, 15 chunks

A non-lexical paraphrase (“What papers should a first-time visitor bring to the clinic?”) retrieved checklist chunks above 0.76. Unrelated questions returned zero results at `min_score=0.45`.

## 6. Generation, API, and interface

`generate_answer()` asks `Qwen2.5-3B-Instruct` to speak as a HealthCore coordinator and to use only retrieved context. Empty retrieval still calls the model; if that output invents company facts, the insufficient-information statement is returned.

`POST /knowledge/query` accepts `{ "question": "..." }` and returns `{ "answer": "..." }`. The backoffice page `uis/talent-pipeline-tracker/app/(app)/backoffice/knowledge/page.tsx` shows explicit loading, error, and success states. The HealthCore tokens include a `prefers-color-scheme: dark` variant.

## 7. Local commands

```bash
docker compose up -d qdrant
uv run python scripts/setup_knowledge_base.py
uv run python scripts/eval_rag_recall.py
uv run python -m pytest tests/pipelines/test_rag.py
```

API (from `services/api`):

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
