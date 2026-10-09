# HealthCore Backoffice (Milestone 4)

Internal Next.js + TypeScript application for visible integration of the Milestone 2 HealthCore business-logic module.

## Run locally

```bash
cd uis/backoffice
npm install
npm run dev
```

Open <http://localhost:3000>. The home page remains the Milestone 2 operations view. The legacy Supplier Directory route at `/suppliers` is a visible relocation page only; it does not call the HealthCore API.

Authenticated supplier list/create/rate/status lives in the Internal Workspace at `uis/talent-pipeline-tracker` (`/backoffice/suppliers`). Set `NEXT_PUBLIC_STAFF_WORKSPACE_URL` in `.env.local` (see `.env.example`) so relocation links target that app.

The static files `suppliers.html` and `suppliers.js` are historical relocation artifacts with no supplier API calls. `styles.css` remains shared styling.
