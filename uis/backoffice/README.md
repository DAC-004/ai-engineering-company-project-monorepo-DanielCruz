# HealthCore Internal Workspace (`uis/backoffice`)

Next.js application for AUTH-02 (login, registration, JWT session handling, protected views, and profile management) and the HealthCore medical-supply inventory backoffice against the HealthCore API (`services/api`).

This application was mapped from `uis/talent-pipeline-tracker` for Ticket `#infra-40`. The original folder is retained until container validation is complete.

## Prerequisites

1. HealthCore API running (default `http://127.0.0.1:8000`; inventory routes are on the same process)
2. Node.js 20+

## Setup (local, without Docker)

```bash
cd uis/backoffice
cp .env.example .env.local
npm install
npm run dev -- --port 3001
```

`npm run dev` uses webpack. Turbopack exceeds Windows `MAX_PATH` in this monorepo path.

Open <http://localhost:3001>.

`.env.local` must include the variables from `.env.example`. `NEXT_PUBLIC_*` values are a same-origin `/backend` prefix. `API_PROXY_TARGET` is server-side only and must point at the FastAPI origin (`http://127.0.0.1:8000` locally, or `http://backend:8000` inside Docker Compose).

Never commit `.env.local`.

Inventory calls are centralized in `lib/inventory.ts`. Components do not call `fetch` directly. Protected inventory requests send `Authorization: Bearer <token>` from `localStorage`.

## Docker

From the repository root, `docker compose up` starts this app on host port `3001` in the shared UI container.

## Routes

| Path | Auth | Purpose |
| --- | --- | --- |
| `/login` | Public | Email/password login → stores JWT in `localStorage` → redirects to `/` |
| `/register` | Public | `POST /users` then `POST /auth/login` → stores JWT → redirects to `/` |
| `/` | Protected | Main authenticated view |
| `/account/profile` | Protected | Shows email + profile; updates via `PUT /profiles/me` |
| `/backoffice/inventory/products` | Protected | Medical supplies with current stock and stock-level indicators |
| `/backoffice/inventory/orders/inbound` | Protected | Log a supply delivery (vendor shipment) |
| `/backoffice/inventory/orders/outbound` | Protected | Log a supply consumption (clinical use or expiry waste) |
| `/backoffice/inventory/orders` | Protected | Read-only supply delivery and consumption history |

Unauthenticated access to protected routes redirects to `/login` via a client-side `AuthGuard` (localStorage-compatible; no middleware token check).

Logout clears the JWT and returns to `/login`. Any protected API response of HTTP 401 clears the session and redirects to `/login`.

## Out of scope

The public website lives at `uis/website` (and the Milestone 1 static files remain at the repository root). Those pages are not wrapped in authentication.
