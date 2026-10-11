# HealthCore Incident Manager UI (`uis/incidents`)

Registration, list, and summary interface for the Centralized Incident Manager.

This folder holds the incident interface. Authenticated routing, AppShell, and
JWT session handling stay in `uis/talent-pipeline-tracker`. Thin host pages
mount these components at:

- `/incidents/new`
- `/incidents`
- `/incidents/summary`

English is the interface language. Do not enter identifying patient data in
title or description.

## Local setup (with the tracker host)

TypeScript and the Next.js production build type-check files under this folder.
Install dependencies here before `npm run build` in the tracker (Node 20+; Node
24 used for I03a validation):

```bash
cd uis/incidents
npm ci
cd ../talent-pipeline-tracker
npm ci
npm run lint
npm run build
```

`react` is a **peer** of this package; the tracker app supplies the runtime
version (`19.2.4` on the reconciled merge). The `devDependencies` here provide
`react` and `@types/react` for sibling-package type-checking only.
