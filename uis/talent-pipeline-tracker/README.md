# HealthCore Internal Workspace (`uis/talent-pipeline-tracker`)

Next.js application for AUTH-02 (login, registration, JWT session handling, protected views, and profile management) and the HealthCore medical-supply inventory backoffice against the HealthCore API (`services/api`).

## Prerequisites

1. HealthCore API running at `http://127.0.0.1:8000` (inventory routes are on the same process)
2. Node.js 20+

## Setup

```bash
cd uis/talent-pipeline-tracker
cp .env.example .env.local
npm install
npm run dev
```

`npm run dev` uses webpack. Turbopack exceeds Windows `MAX_PATH` in this monorepo path.

Open <http://localhost:3000>.

`.env.local` must include:

```
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_INVENTORY_API_URL=http://localhost:8000
```

Never commit `.env.local`.

Inventory calls are centralized in `lib/inventory.ts`. Components do not call `fetch` directly. Protected inventory requests send `Authorization: Bearer <token>` from `localStorage`.

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

The Milestone 1 public website (`index.html`, `application.html` at the repository root) is not part of this application and is not wrapped in authentication.
