# HealthCore API (`services/api`)

FastAPI backend for HealthCore Digital: JWT authentication, TinyDB User/Profile identity, and protected incident analysis endpoints.

Validation and metrics for incidents use the shared module at `shared/incident_analyzer/` (same logic as `scripts/analyze.py`).

## Setup (uv)

```bash
cd services/api
uv sync
cp .env.example .env   # then set SECRET_KEY
```

Do not use `pip install` or Poetry for dependency changes.

## Run

From `services/api`:

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

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

### Incident manager routes (`/api/incidents`)

JWT-protected. Validation failures return HTTP 400 with `{ "field", "message" }`.

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/api/incidents` | Create (generated `id`, `created_at`, `updated_at`) |
| `GET` | `/api/incidents` | List; optional `status`, `origin`, `branch`, `category` |
| `GET` | `/api/incidents/summary` | Totals by status, category, origin, branch |
| `GET` | `/api/incidents/{id}` | Detail; 404 if missing |
| `PATCH` | `/api/incidents/{id}/status` | Lifecycle only; advances `updated_at` |

Historical load: `python scripts/seed_incidents.py` (same TinyDB file).

## Identity storage

- User and Profile live in TinyDB only (`data/auth.json` by default)
- Profile links to User through `user_id`
- No User/Profile SQLModel, PostgreSQL, or Supabase tables

## Security notes

- Passwords: `libpass` with bcrypt (`passlib` PyPI package is not used)
- JWT: `python-jose` (assignment requirement; ignore stale `pyjwt[crypto]` setup snippet)
- `SECRET_KEY`, `JWT_ALGORITHM`, and `ACCESS_TOKEN_EXPIRE_MINUTES` come from environment / `.env`
- Operational `user_id` vs `user_uuid` naming for future SQL modules remains unresolved in source material; AUTH-01 does not invent those fields
