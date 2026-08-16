# `scripts` folder

This folder contains **helper scripts** for the monorepo: development automation, maintenance utilities, repetitive tasks (setup, lint, migrations, data generation, etc.), and internal tooling.

- **Main purpose**: group support tools that do not belong to a specific app, agent, or pipeline but make the team’s work easier.
- **Recommendation**: document each script (what it does, parameters, requirements, usage examples) and keep them reproducible (and safe) across environments.

## Incident analysis (HealthCore)

```bash
# From repository root (or from scripts/ with a relative CSV path):
python scripts/analyze.py scripts/incidents-healthcore.csv
```

- `analyze.py` — CLI entrypoint (shared logic in `shared/incident_analyzer/`)
- `seed_incidents.py` — load valid historical rows into TinyDB as `origin: customer`
- `incidents-healthcore.csv` — HealthCore 100-row assignment dataset (company equivalent of `incidents-COMPANY.csv`)

```bash
python scripts/seed_incidents.py
```

The seed reuses `packages/shared` validation, applies CONTEXT transforms, skips
invalid rows, and is idempotent (derived markers; raw CSV `incident_id` is not stored).

The authoritative local copy of the instructor dataset and CONTEXT live under `.project_specs/` (gitignored). Keep `scripts/incidents-healthcore.csv` identical to that official file for runnable submission layout. Never print or export `patient_id` values.

> _Spanish version: [README.es.md](./README.es.md)._
