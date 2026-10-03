# HealthCore Backoffice (Milestone 4)

Internal Next.js + TypeScript application for visible integration of the Milestone 2 HealthCore business-logic module.

## Run locally

```bash
cd uis/backoffice
npm install
npm run dev
```

Open <http://localhost:3000>. The home page remains the Milestone 2 operations view. Supplier Directory is at <http://localhost:3000/suppliers> and calls the HealthCore API at `http://127.0.0.1:8000`.

The approved static files `suppliers.html`, `suppliers.js`, and `styles.css` remain in this package. The running backoffice is the Next.js app, so the same directory behavior is served from `/suppliers` instead of a separate `http-server` process.
