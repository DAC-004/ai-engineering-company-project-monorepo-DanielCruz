# HealthCore Web UI — Incident Analysis relocation (`uis/web`)

This folder is a **static relocation entry point** only. CSV upload, analysis, and export run in the authenticated Internal Workspace at `/incident-analysis` inside `uis/talent-pipeline-tracker`.

## Workspace URL

The link target is built from `window.STAFF_WORKSPACE_URL` when set, otherwise `http://localhost:3000`. Optional local override:

1. Copy `config.local.js.example` to `config.local.js` (keep `config.local.js` out of Git).
2. Set `window.STAFF_WORKSPACE_URL` to your tracker origin.

`index.html` loads `config.local.js` before `app.js`. This page does **not** call `/api/incidents/*`.

## Run

```bash
npx http-server uis/web -p 8080 -a 127.0.0.1 -c-1
```

Open the printed URL and follow the workspace link to sign in and analyze CSVs.
