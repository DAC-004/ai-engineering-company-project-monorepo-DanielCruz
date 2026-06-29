# HealthCore Talent Pipeline Tracker

Internal People & Workforce hiring tool for HealthCore — Milestone 3.

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
| `NEXT_PUBLIC_API_BASE_URL` | Base URL for the Talent Tracker REST API |

Example:

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

Do not commit `.env.local`. Commit `.env.example` instead.
