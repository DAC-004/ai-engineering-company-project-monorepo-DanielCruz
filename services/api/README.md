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

## AUTH-03 password recovery and change

Password reset emails are sent with **Resend**. Set these in `.env` (see `.env.example`):

| Variable | Purpose |
| --- | --- |
| `RESEND_API_KEY` | Resend API key (required to send real reset emails; never hard-code) |
| `RESEND_FROM_EMAIL` | From address. Must be Resend-allowed (use `HealthCore <onboarding@resend.dev>` unless you verified your own domain) |
| `FRONTEND_BASE_URL` | Frontend origin used in reset links (default `http://localhost:3000`) |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | Token lifetime; must be 15–60 (default `30`) |
| `AUTH03_TEST_RECIPIENT` | Optional local-only real inbox for AUTH-03 inbox validation (do not commit) |

Reset credentials are opaque random tokens. Only a SHA-256 hash is stored in TinyDB (`password_reset_tokens`) with an expiry and `used_at` so a token cannot be reused after a successful reset.

### Manual reset flow

1. Register a user, then `POST /auth/forgot-password` with `{ "email": "…" }`
2. Open the link from the Resend email (`/reset-password?token=…`)
3. `POST /auth/reset-password` with `{ "token": "…", "new_password": "…" }`
4. While logged in, `POST /auth/change-password` with `{ "current_password": "…", "new_password": "…" }` and `Authorization: Bearer <token>`

## Route inventory (AUTH-01 / AUTH-03)

### Authentication routes (`/auth`)

| Method | Path | Auth |
| --- | --- | --- |
| `POST` | `/auth/login` | Public |
| `GET` | `/auth/me` | Protected |
| `POST` | `/auth/forgot-password` | Public (always HTTP 200; no account enumeration) |
| `POST` | `/auth/reset-password` | Public (HTTP 400 for invalid/expired/used tokens) |
| `POST` | `/auth/change-password` | Protected |

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

## Identity storage

- User and Profile live in TinyDB only (`data/auth.json` by default)
- Profile links to User through `user_id`
- No User/Profile SQLModel, PostgreSQL, or Supabase tables

## Security notes

- Passwords: `libpass` with bcrypt (`passlib` PyPI package is not used)
- JWT: `python-jose` (assignment requirement; ignore stale `pyjwt[crypto]` setup snippet)
- `SECRET_KEY`, `JWT_ALGORITHM`, and `ACCESS_TOKEN_EXPIRE_MINUTES` come from environment / `.env`
- AUTH-03: `RESEND_API_KEY` and related reset settings come from environment / `.env` (never hard-code API keys)
- Operational `user_id` vs `user_uuid` naming for future SQL modules remains unresolved in source material; AUTH-01 does not invent those fields
