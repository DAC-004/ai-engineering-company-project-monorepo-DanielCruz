# AUTH-01 acceptance notes

## Protected route inventory

### Auth (`/auth`) — not counted toward the five-route rubric

- `POST /auth/login` — public
- `GET /auth/me` — protected

### Users (`/users`) — not counted toward the five-route rubric

- `POST /users` — public
- `GET /users` — protected
- `GET /users/{id}` — protected
- `PUT /users/{id}` — protected (self/admin → otherwise 403)
- `DELETE /users/{id}` — protected (self/admin; deletes linked Profile)

### Profiles (`/profiles`) — not counted toward the five-route rubric

- `GET /profiles/me` — protected
- `PUT /profiles/me` — protected (owner via `/me`)

### Qualifying protected routes outside `/users` and `/auth` (rubric ≥5)

Instructor clarification authorizes creating three additional legitimate Incident Analyzer routes so the total reaches five.

| # | Method | Path | Notes |
| --- | --- | --- | --- |
| 1 | `POST` | `/api/incidents/analyze` | Pre-AUTH-01; protected |
| 2 | `GET` | `/api/incidents/results` | Additional; JSON last analysis |
| 3 | `GET` | `/api/incidents/results/summary` | Additional; aggregate metrics |
| 4 | `GET` | `/api/incidents/results/export` | Pre-AUTH-01; protected |
| 5 | `DELETE` | `/api/incidents/results` | Additional; owner/admin only (403 otherwise) |

`GET /health` remains public and is not counted.

**Qualifying protected total: 5**

## Source notes (non-blocking documentation)

- Future operational SQL identity reference: `user_id` vs `user_uuid` — no existing field in repo; Profile uses required `user_id`
- Stale setup snippet mentioned `pyjwt[crypto]`; governing requirement used: `python-jose`
- Passwords: `libpass[bcrypt]` (correction supersedes passlib)
