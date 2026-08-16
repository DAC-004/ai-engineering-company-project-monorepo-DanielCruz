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
