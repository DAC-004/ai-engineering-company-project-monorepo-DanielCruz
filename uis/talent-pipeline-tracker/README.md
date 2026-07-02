# HealthCore Talent Pipeline Tracker

Internal People & Workforce hiring tool for HealthCore — Milestone 3.

## Reviewer setup

Run these commands from the app directory in the monorepo:

```bash
cd uis/talent-pipeline-tracker
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Before reviewing:

- Use `.env.example` as the reference for required environment variables.
- Do **not** commit `.env.local` (it is gitignored).
- Run the app from `uis/talent-pipeline-tracker/`, not the repository root.

Optional checks:

```bash
npm run lint
npm run build
```

## Setup

1. Install dependencies:

```bash
npm install
```

2. Copy environment variables:

```bash
cp .env.example .env.local
```

3. Start the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment variables

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Base URL for the Talent Tracker REST API (required) |

Example (also in `.env.example`):

```env
NEXT_PUBLIC_API_BASE_URL=https://playground.4geeks.com/tracker/api/v1
```

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Candidate list with status/stage filters and search |
| `/candidates/new` | Register a new candidate |
| `/candidates/[id]` | Candidate detail, status/stage updates, notes |
| `/candidates/[id]/edit` | Edit candidate profile |

## API

This app integrates with the [4Geeks Talent Tracker API](https://playground.4geeks.com/tracker/api/v1/docs).

## Submission notes

- Push your branch to the monorepo on GitHub and share the link with your instructor.
- Commit `.env.example`; do **not** commit `.env.local`.
