# HealthCore Internal Workspace (`uis/talent-pipeline-tracker`)

Next.js application for AUTH-02 (login, registration, JWT session handling, protected views, and profile management), the HealthCore medical-supply inventory backoffice, password recovery and change (AUTH-03), and the Milestone 3 candidate pipeline.

The candidate pipeline calls the 4Geeks Talent Tracker API. Login, profile, inventory, telemetry, and RFP intake call the HealthCore API (`services/api`).

## Prerequisites

1. HealthCore API running at `http://127.0.0.1:8000` for authenticated workspace routes
2. Node.js 20+
3. Network access to the 4Geeks tracker API when reviewing candidate records

## Reviewer setup

Run these commands from the monorepo (incident UI modules live in the sibling
`uis/incidents` package and must be installed before lint/build):

```bash
cd uis/incidents
npm ci
cd ../talent-pipeline-tracker
cp .env.example .env.local
npm ci
npm run dev
```

`npm run dev` uses webpack. Turbopack exceeds Windows `MAX_PATH` in this monorepo path.

Open [http://localhost:3000](http://localhost:3000).

Before reviewing:

- Use `.env.example` as the reference for required environment variables.
- Do not commit `.env.local` (it is gitignored).
- Run the app from `uis/talent-pipeline-tracker/`, not the repository root.

Optional checks:

```bash
npm run lint
npm run build
```

## Environment variables

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | HealthCore API used by login, registration, and profile |
| `NEXT_PUBLIC_INVENTORY_API_URL` | HealthCore API used by inventory routes |
| `NEXT_PUBLIC_TELEMETRY_ENDPOINT` | Telemetry capture destination |
| `NEXT_PUBLIC_TRACKER_API_BASE_URL` | 4Geeks Talent Tracker REST API used by the candidate pipeline |
| `NEXT_PUBLIC_STAFF_WORKSPACE_URL` | This app's public origin for cross-links (optional; default documented as `http://localhost:3000`) |

Example (also in `.env.example`):

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_INVENTORY_API_URL=http://localhost:8000
NEXT_PUBLIC_TELEMETRY_ENDPOINT=http://localhost:8000/telemetry/events
NEXT_PUBLIC_TRACKER_API_BASE_URL=https://playground.4geeks.com/tracker/api/v1
```

Never commit `.env.local`.

Inventory calls are centralized in `lib/inventory.ts`. Supplier mutations are centralized in `lib/suppliers.ts` and use `apiFetch(..., { auth: true })` against the HealthCore API. Components do not call `fetch` directly for those modules. Protected inventory and supplier requests send `Authorization: Bearer <token>` from `localStorage`. Candidate calls are centralized in `lib/api/client.ts` and use `NEXT_PUBLIC_TRACKER_API_BASE_URL` only (no HealthCore JWT is sent to the external tracker API).

## Routes

| Path | Auth | Purpose |
| --- | --- | --- |
| `/login` | Public | Email/password login → stores JWT in `localStorage` → redirects to `/`; includes **Forgot your password?** |
| `/register` | Public | `POST /users` then `POST /auth/login` → stores JWT → redirects to `/` |
| `/forgot-password` | Public | Requests `POST /auth/forgot-password`; always shows the anti-enumeration confirmation and disables the form after submit |
| `/reset-password` | Public | Reads `token` from the query string; `POST /auth/reset-password`; redirects to `/login?reset=success` on success |
| `/` | Protected | Main authenticated workspace (incidents, inventory, suppliers, knowledge, profile, change password, talent pipeline) |
| `/incidents/new` | Protected | Register an incident |
| `/incidents` | Protected | Incident list and status updates |
| `/incidents/summary` | Protected | Aggregate incident metrics |
| `/account/profile` | Protected | Shows email and profile; updates via `PUT /profiles/me` |
| `/account/change-password` | Protected | Current + new + confirmation; `POST /auth/change-password` |
| `/backoffice/inventory/products` | Protected | Medical supplies with current stock and stock-level indicators |
| `/backoffice/inventory/orders/inbound` | Protected | Log a supply delivery |
| `/backoffice/inventory/orders/outbound` | Protected | Log a supply consumption |
| `/backoffice/inventory/orders` | Protected | Read-only supply delivery and consumption history |
| `/backoffice/suppliers` | Protected | Supplier directory (list, register, update rate/status; no delete UI) |
| `/backoffice/rfp` | Protected | RFP intake list |
| `/backoffice/rfp/[ticketId]` | Protected | RFP ticket detail |
| `/backoffice/knowledge` | Protected | Knowledge assistant (WebSocket chat) |
| `/candidates` | Public to HealthCore auth | Candidate list with status, stage, and search filters |
| `/candidates/new` | Public to HealthCore auth | Register a new candidate |
| `/candidates/[id]` | Public to HealthCore auth | Candidate detail, status and stage updates, notes |
| `/candidates/[id]/edit` | Public to HealthCore auth | Edit candidate profile |

`/` stays the authenticated workspace. The candidate list is `/candidates` because `app/(app)/page.tsx` and `app/page.tsx` would both claim `/`.

Unauthenticated access to protected workspace routes redirects to `/login` via a client-side `AuthGuard`. Candidate routes are outside that guard.

Logout clears the JWT and returns to `/login`. Any protected API response of HTTP 401 clears the session and redirects to `/login`.

## API

Candidate records integrate with the [4Geeks Talent Tracker API](https://playground.4geeks.com/tracker/api/v1/docs).

Password-reset emails are sent by the API via **Resend** (`RESEND_API_KEY` in `services/api/.env`).

## Out of scope

The Milestone 1 public website (`index.html`, `application.html` at the repository root) and the separate Milestone 4 apps (`uis/website`, `uis/backoffice`) are not wrapped in this application's authentication.
