# HealthCore Backoffice (`uis/backoffice`)

Internal administrative UI for HealthCore Digital.

## Supplier Directory

`suppliers.html` is the centralized Supplier Directory for Diane Foster and Claire Whitfield.

It loads data from the HealthCore API (`services/api`) and supports:

- listing suppliers with categories, `monthly_rate`, compliance agreement, and status
- filtering by country and category without a page reload
- registering a supplier via `POST /suppliers`
- updating `monthly_rate` via `PATCH /suppliers/{id}/rate`
- activating or suspending a supplier via `PATCH /suppliers/{id}/status`

## Run

1. Start the API from `services/api`:

```bash
uv sync
uv run seed
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

2. Serve this folder:

```bash
npx http-server uis/backoffice -p 3001 -a 127.0.0.1 -c-1
```

3. Open `http://127.0.0.1:3001/` and use **Supplier Directory** in the application menu.
