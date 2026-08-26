# HealthCore Public Website (`uis/website`)

Next.js public-facing site mapped from the Milestone 1 static pages (`index.html`, `application.html`, `validation.js`, and `assets/backgrounds/`) for Ticket `#infra-40`.

The original static files remain at the repository root until container validation is complete.

## Pages

| Path | Source | Purpose |
| --- | --- | --- |
| `/` | `index.html` | Public landing page |
| `/application` | `application.html` + `validation.js` | Care request form |

Internal links use `/` and `/application` in place of `index.html` and `application.html`. Appearance, navigation, copy, and form validation rules are preserved.

## Local (without Docker)

```bash
cd uis/website
cp .env.example .env.local
npm install
npm run dev -- --port 3000
```

`npm run dev` uses webpack, matching the backoffice Windows `MAX_PATH` workaround.

Open <http://localhost:3000>.

## Docker

From the repository root, `docker compose up` starts this app on host port `3000` in the shared UI container.
