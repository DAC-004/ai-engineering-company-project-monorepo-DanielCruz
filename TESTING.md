# AUTH-088 Testing

Unit tests for the HealthCore authentication API. This document is the test plan and the run book.

The Git repository root is **not** a Python/uv project. Python commands in this file must be run from `services/api/`. A literal `uv run pytest` from the repository root cannot work because there is no `pyproject.toml` there.

## How to run the tests

### FastAPI / pytest

From `services/api/`:

```bash
cd services/api
uv sync --group dev
uv run pytest
uv run pytest --cov
```

The authentication coverage target is at least 70% on:

- `app.routers.auth`
- `app.core.security`
- `app.core.deps`

`uv run pytest --cov` is configured to measure those modules. It does not measure the whole `app` package, and it does not treat all of `app.routers.users` as the authentication module. `POST /users` registration is still tested as an AUTH-088 endpoint.

### TypeScript / Jest

From `uis/talent-pipeline-tracker/`:

```bash
cd uis/talent-pipeline-tracker
npm install
npx jest --coverage
```

Jest covers the existing authentication token-storage helpers in `lib/auth/token.ts`.

## Scope

### In AUTH-088

| Endpoint or module | Responsibility |
| --- | --- |
| `POST /users` | Public registration only: hash password, default role, create linked Profile, reject duplicate email |
| `POST /auth/login` | Validate credentials and issue a JWT |
| `GET /auth/me` | Resolve the authenticated user and linked Profile |
| `app.core.security` | Password hashing/verification and JWT create/decode |
| `app.core.deps` (`get_current_user`) | Token validation and user lookup |

There is no `/auth/token` route. Token expiration is enforced by `decode_access_token` and `get_current_user`.

### Out of AUTH-088

- Remaining `/users` CRUD (`GET`, `PUT`, `DELETE`)
- `GET /profiles/me` and `PUT /profiles/me`
- Incident routes
- `GET /health`
- Optional tickets API-042 and FE-019

AUTH-01 documents `/auth`, `/users`, and `/profiles` as separate groups. Registration is included because AUTH-088 uses registration-oriented examples (`test_register.py`, duplicate users), AUTH-01's auth flow starts with `POST /users`, and registration contains authentication application logic. That reasoning does not pull the rest of `/users` CRUD into this suite.

## Case selection criteria

Cases were selected to protect application decisions, not FastAPI/Pydantic/OAuth2 plumbing.

Included when the application decides the outcome (hash, persist, issue token, reject credentials, reject expired/malformed tokens, normalize email).

Excluded as required AUTH-088 cases because they fail in the framework/schema before application logic:

- missing registration password (Pydantic)
- seven-character registration password (`Field(min_length=8)`)
- missing OAuth login form fields (FastAPI `OAuth2PasswordRequestForm`)
- empty login password string (this FastAPI version returns 422 before `login()`; confirmed during implementation)
- missing `Authorization` header (`OAuth2PasswordBearer`)

## Test plan

Written before any AUTH-088 test file was created.

### `POST /users` — `services/api/tests/test_register.py`

| Kind | Case | Why |
| --- | --- | --- |
| Happy | Valid email and password create a user; stored password is hashed; `verify_password` succeeds; role defaults to `user`; a linked Profile is created | Core identity-creation behavior |
| Edge | Mixed-case email is stored lowercased | Same normalization used at login; easy to regress |
| Failure | Duplicate email is rejected with 409 and no second user is created | Application `ValueError` in `create_user`, not schema validation |

### `POST /auth/login` — `services/api/tests/test_login.py`

| Kind | Case | Why |
| --- | --- | --- |
| Happy | Valid credentials issue a JWT whose `sub` is the TinyDB user id and that includes `exp` | Token issuance is the login contract |
| Edge | Mixed-case email authenticates against a lowercased stored email | AI-assisted case; see below |
| Failure | Wrong password is rejected with 401 and no token | Credential verification |
| Failure | Unknown email is rejected with 401 and no token | `get_user_by_email` returns None; same application branch as a missing user |
| Failure | Inactive user is rejected with 401 and detail `Inactive user` | Distinct branch after password check |

### `GET /auth/me` — `services/api/tests/test_me.py`

| Kind | Case | Why |
| --- | --- | --- |
| Happy | Valid token returns that user's email, role, and profile | Current-user resolution |
| Edge | Token for a deleted/missing user is rejected with 401 | `get_current_user` loads the user after decode |
| Edge | Token without `sub` is rejected with 401 | Application check after decode |
| Failure | Expired token is rejected with 401 | CTO regression: expiration must be enforced |
| Failure | Malformed token is rejected with 401 | `decode_access_token` / `JWTError` path |

### Security helpers — `services/api/tests/test_token.py`

| Kind | Case | Why |
| --- | --- | --- |
| Happy | `create_access_token` / `decode_access_token` round-trip | Token generate/validate logic without HTTP |
| Happy | Matching password verifies | Password helper contract |
| Edge | Extra claims survive decoding | `create_access_token(..., extra_claims=...)` |
| Failure | Expired JWT raises `JWTError` | Expiration at the helper layer |
| Failure | Incorrect password does not verify | Negative password check |

### TypeScript token helpers — `uis/talent-pipeline-tracker/__tests__/auth/token.test.ts`

For each of `getAccessToken`, `setAccessToken`, `clearAccessToken`, and `hasAccessToken`: one happy-path test and one failure-mode test against a controlled `localStorage` mock.

## AI-assisted case

**Mixed-case email login.** Inspection of `create_user` showed emails are stored with `.lower()`. Inspection of `get_user_by_email` showed lookup also uses `.lower()`. A mixed-case login against a stored lowercase email is therefore a real application path and an easy omission. The suite includes that case for both registration storage and login lookup.

No production bug is claimed from inspection alone. If a legitimate test later exposes a defect, it will be recorded in the results section.

## Coverage results

Recorded 17 August 2026 after running the required commands.

### pytest

Working directory: `services/api/`

`uv run pytest`

- collected 18 items
- 18 passed
- 0 failed

`uv run pytest --cov`

- collected 18 items
- 18 passed
- 0 failed
- modules measured: `app.routers.auth`, `app.core.security`, `app.core.deps`
- coverage:

| Module | Cover |
| --- | --- |
| `app.routers.auth` | 100% |
| `app.core.security` | 100% |
| `app.core.deps` | 74% |
| **TOTAL** | **89%** |

The 70% authentication-module threshold is met (89% combined). Missed lines in `app.core.deps` are `require_self_or_admin` (authorization for `/users` CRUD), which is outside AUTH-088.

A literal `uv run pytest` from the Git repository root fails with `Failed to spawn: pytest` / `program not found`. The repository root has no Python/uv project. Use `services/api/` as shown above.

### Jest

Working directory: `uis/talent-pipeline-tracker/`

`npx jest --coverage`

- test suites: 1 passed, 1 total
- tests: 8 passed, 8 total
- `lib/auth/token.ts`: 100% statements / branches / functions / lines

### AI-assisted case

Mixed-case email login is implemented and passing: `test_login_accepts_mixed_case_email` and `test_register_stores_mixed_case_email_in_lowercase`.

### Production defects found

None. Implementation showed that an empty login password string is rejected with HTTP 422 by FastAPI form validation before `login()` runs. That case was removed from the required AUTH-088 matrix and replaced with unknown-email 401, which is application logic. No production code was changed.

The `setAccessToken` server/browser-guard difference remains unconfirmed as a defect; no production change was made.
