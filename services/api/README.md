# HealthCore API (`services/api`)

FastAPI backend for HealthCore Digital.

Current capabilities:

- Patient incident analysis (`/api/incidents/...`) via `shared/incident_analyzer/`
- Supplier Directory (`/suppliers/...`) backed by TinyDB + Pydantic validation

## Setup

From `services/api`:

```bash
uv sync
```

Or with pip:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
```

## Seed suppliers

Loads the exact HealthCore CONTEXT directory into TinyDB (skips duplicates on re-run):

```bash
uv run seed
```

## Run

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open Swagger UI at `http://127.0.0.1:8000/docs`.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/incidents/analyze` | Multipart CSV upload → JSON summary |
| `GET` | `/api/incidents/results/export` | Download last analysis as `results.csv` |
| `GET` | `/health` | Liveness check |
| `POST` | `/suppliers` | Register a supplier |
| `GET` | `/suppliers` | List / filter suppliers (`country`, `category`) |
| `GET` | `/suppliers/{id}` | Supplier detail |
| `PATCH` | `/suppliers/{id}/rate` | Update `monthly_rate` + `updated_at` |
| `PATCH` | `/suppliers/{id}/status` | Set `active` / `suspended` |
| `DELETE` | `/suppliers/{id}` | Remove a supplier |

TinyDB file path: `services/api/data/suppliers.json` (local, gitignored).
