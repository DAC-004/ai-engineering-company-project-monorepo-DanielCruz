# HealthCore Internal Workspace (`uis/talent-pipeline-tracker`)

Next.js application that completes AUTH-02: login, registration, JWT session handling, protected views, and profile management against the HealthCore API (`services/api`).

## Prerequisites

1. AUTH-01 API running at `http://127.0.0.1:8000`
2. Node.js 20+

## Setup

```bash
cd uis/talent-pipeline-tracker
cp .env.example .env.local
npm install
npm run dev
```

Open <http://localhost:3000>.

## Routes

| Path | Auth | Purpose |
| --- | --- | --- |
| `/login` | Public | Email/password login → stores JWT in `localStorage` → redirects to `/`; includes **Forgot your password?** |
| `/register` | Public | `POST /users` then `POST /auth/login` → stores JWT → redirects to `/` |
| `/forgot-password` | Public | Requests `POST /auth/forgot-password`; always shows the anti-enumeration confirmation and disables the form after submit |
| `/reset-password` | Public | Reads `token` from the query string; `POST /auth/reset-password`; redirects to `/login?reset=success` on success |
| `/` | Protected | Main authenticated view |
| `/account/profile` | Protected | Shows email + profile; updates via `PUT /profiles/me` |
| `/account/change-password` | Protected | Current + new + confirmation; `POST /auth/change-password` |

Unauthenticated access to protected routes redirects to `/login` via a client-side `AuthGuard` (localStorage-compatible; no middleware token check).

Logout clears the JWT and returns to `/login`. Any protected API response of HTTP 401 clears the session and redirects to `/login`.

Password-reset emails are sent by the API via **Resend** (`RESEND_API_KEY` in `services/api/.env`).

## Out of scope

The Milestone 1 public website (`index.html`, `application.html` at the repository root) is not part of this application and is not wrapped in authentication.
