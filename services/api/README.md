# HealthCore API (`services/api`)

FastAPI backend for HealthCore Digital: JWT authentication, TinyDB User/Profile identity, protected incident analysis, inventory, RFP intake, and the Supplier Directory.

Validation and metrics for incidents use the shared module at `shared/incident_analyzer/` (same logic as `scripts/analyze.py`).

## Setup (uv)

```bash
cd services/api
uv sync
cp .env.example .env   # then set SECRET_KEY and DATABASE_URL
```

`DATABASE_URL` must be the Supabase **transaction pooler** URI (Connect → Direct → Transaction pooler → URI). Do not commit `.env`.

This API uses Python 3.13. `markitdown[pdf]` depends on `onnxruntime`, which does not publish a Python 3.14 wheel. `services/api/.python-version` pins 3.13 so `uv` does not recreate the environment on the system default.

RFP intake also needs the local file `qwen2.5-3b-instruct-q4_k_m.gguf` at `data/process/models/` (or in the directory named by `RAG_MODELS_DIR`). Part 1 does not download that file and does not call a remote chat API. Without the file, an upload stays `analyzing` with `processing_failed` and code `model_asset_missing`.

Do not use `pip install` or Poetry for dependency changes.

## Run

Index the knowledge base once from the repository root before the first API start. That writes the gitignored 384-d collection `healthcore_knowledge` under `data/process/qdrant_storage`. Later API starts reopen that directory. They do not ingest again.

```bash
uv run python scripts/setup_knowledge_base.py
```

From `services/api`:

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Stop the API with Ctrl+C so lifespan can release the local Qdrant lock. The index stays on disk. Start the same command again without re-running `setup_knowledge_base.py`. Do not point `QDRANT_PATH` at another milestone's store.

An embedded `QDRANT_PATH` outside this checkout is rejected by default so a
leftover worktree setting cannot silently select another index. For a
deliberately shared external store, set both `QDRANT_PATH` and
`HEALTHCORE_ALLOW_EXTERNAL_QDRANT=1`. That opt-in does not migrate, convert, or
re-ingest the selected store.

Open interactive docs: <http://127.0.0.1:8000/docs>

## Manual auth acceptance flow

1. `POST /users` — register (JSON body with `email`, `password`, optional profile fields)
2. `POST /auth/login` — OAuth2 form: `username` = email, `password` = password → JWT
3. Click **Authorize** in `/docs` and paste the token, or send `Authorization: Bearer <token>`
4. Call a protected route (for example `GET /auth/me` or `GET /users`)

## Route inventory (AUTH-01)

### New authentication routes (`/auth`)

| Method | Path | Auth |
| --- | --- | --- |
| `POST` | `/auth/login` | Public |
| `GET` | `/auth/me` | Protected |

### New user routes (`/users`)

| Method | Path | Auth |
| --- | --- | --- |
| `POST` | `/users` | Public registration |
| `GET` | `/users` | Protected |
| `GET` | `/users/{id}` | Protected |
| `PUT` | `/users/{id}` | Protected (self or admin) |
| `DELETE` | `/users/{id}` | Protected (self or admin; removes linked Profile) |

### New profile routes (`/profiles`)

| Method | Path | Auth |
| --- | --- | --- |
| `GET` | `/profiles/me` | Protected |
| `PUT` | `/profiles/me` | Protected (owner only via `/me`) |

### Qualifying protected routes outside `/users` and `/auth` (rubric ≥5)

Instructor clarification authorizes three additional legitimate Incident Analyzer routes.

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/incidents/analyze` | **Protected** | Pre-AUTH-01 CSV analysis |
| `GET` | `/api/incidents/results` | **Protected** | JSON last analysis |
| `GET` | `/api/incidents/results/summary` | **Protected** | Aggregate operational summary |
| `GET` | `/api/incidents/results/export` | **Protected** | Pre-AUTH-01 CSV export |
| `DELETE` | `/api/incidents/results` | **Protected** | Clear analysis; owner/admin (403 otherwise) |
| `GET` | `/health` | Public | Liveness — not counted |

**Qualifying protected total: 5**

## Identity and inventory storage

- User and Profile live in TinyDB only (`data/auth.json` by default)
- Profile links to User through `user_id`
- No User/Profile SQLModel, PostgreSQL, or Supabase tables
- MedicalSupply, SupplyDelivery, and SupplyConsumption live in PostgreSQL via SQLModel (`DATABASE_URL`, Supabase transaction pooler in the live app)

## Inventory routes (`/inventory`)

HealthCore inventory routes require authentication. Catalog rows are `MedicalSupply`. Inbound writes are `SupplyDelivery`. Outbound writes are `SupplyConsumption`.

| Method | Path | Auth |
| --- | --- | --- |
| `GET` | `/inventory/products` | Protected |
| `POST` | `/inventory/products` | Protected |
| `GET` | `/inventory/products/{id}` | Protected |
| `POST` | `/inventory/orders/inbound` | Protected |
| `POST` | `/inventory/orders/outbound` | Protected |
| `GET` | `/inventory/orders` | Protected |

## RFP intake routes (`/rfp`)

Part 1 intake runs in this same API process. The agents live under `data/pipelines/rfp_intake/`. Tickets, metadata, department key aspects, and the Part 2 handoff are SQLModel tables on `DATABASE_URL`.

| Method | Path | Auth |
| --- | --- | --- |
| `POST` | `/rfp/tickets` | Protected. PDF only. Returns 202 with `ticket_id` and status `analyzing`. |
| `GET` | `/rfp/tickets/{ticket_id}` | Protected. Poll until `intake_complete`, `discarded`, or `processing_failed`. |

A caught pipeline failure stays `analyzing` with `processing_failed` and a code. It does not become a successful intake. A process that dies is reported as `stalled` on the GET response when `updated_at` is older than 15 minutes and the ticket is not running in this process. The stored status is not rewritten to success.

`current_stock` is computed as `SUM(SupplyDelivery.quantity) - SUM(SupplyConsumption.quantity)` for each `MedicalSupply`. A consumption that would make that stock negative returns HTTP 400 with `Insufficient stock for supply '{name}'. Available: {available}, requested: {quantity}.` and is not persisted.

Seed (idempotent on empty tables): `uv run python scripts/seed_inventory.py`

Validate inventory behavior: `uv run python scripts/validate_inventory.py`

## Supplier directory

Supplier records live in their own TinyDB file, `services/api/data/suppliers.json`, not in the authentication database. `updated_at` is written by the API. A rate change refreshes that timestamp. USA must use USD and UK must use GBP.

```bash
cd services/api
uv run seed
```

The seeder inserts the 15 HealthCore suppliers and skips names that are already present.

| Method | Path | Auth |
| --- | --- | --- |
| `POST` | `/suppliers` | Public |
| `GET` | `/suppliers` | Public. Optional `country` and `category` filters. |
| `GET` | `/suppliers/{id}` | Public |
| `PATCH` | `/suppliers/{id}/rate` | Public. Updates `monthly_rate` and `updated_at`. |
| `PATCH` | `/suppliers/{id}/status` | Public. `active` or `suspended`. |
| `DELETE` | `/suppliers/{id}` | Public |

## Security notes

- Passwords: `libpass` with bcrypt (`passlib` PyPI package is not used)
- JWT: `python-jose` (assignment requirement; ignore stale `pyjwt[crypto]` setup snippet)
- `SECRET_KEY`, `JWT_ALGORITHM`, and `ACCESS_TOKEN_EXPIRE_MINUTES` come from environment / `.env`
- Operational `user_id` vs `user_uuid` naming for future SQL modules remains unresolved in source material; AUTH-01 does not invent those fields

## Support agent graph

`POST /agent/query` is public, like `POST /knowledge/query`. The knowledge route still calls `query()` and is unchanged.

`POST /agent/query` accepts `{ "question": "..." }`, including an empty string, and on success returns `{ "answer": "...", "trace_id": "..." }`. The handler only invokes the compiled LangGraph graph in `app/agent/graph.py` and translates the result:

- An empty or whitespace-only question becomes HTTP 400.
- An unexpected node failure is logged on the server and returned as HTTP 502 with `The knowledge assistant could not generate an answer right now.`
- The response never includes a traceback.

Checkpoints are written to `data/process/agent_checkpoints/support_agent.sqlite` after each node. Runtime traces are written to `data/process/agent_traces/<trace_id>.json`. Both directories are gitignored.

From the repository root, the fixture evals are:

```bash
uv run pytest tests/pipelines/test_agent_evals.py -q
```

Regenerate the reviewed fixtures and `docs/rag/sample-agent-trace.json` with:

```bash
uv run python tests/pipelines/record_agent_traces.py
```

That command runs the compiled graph with patched retrieval and generation. It does not call the live generation model. See `docs/rag/langgraph-agent.md`.
