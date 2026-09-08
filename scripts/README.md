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
- `incidents-healthcore.csv` — HealthCore 100-row assignment dataset (company equivalent of `incidents-COMPANY.csv`)

The authoritative local copy of the instructor dataset and CONTEXT live under `.project_specs/` (gitignored). Keep `scripts/incidents-healthcore.csv` identical to that official file for runnable submission layout. Never print or export `patient_id` values.

## Nightly telemetry export (Ticket #DEV-53)

Independent worker. It does not start FastAPI. The CSV under `data/raw/` is an audit backup only; the pipeline continues to read `telemetry_events` from the database. Orchestration status is stored in `job_runs`. The pipeline continues to write ETL status to `pipeline_runs`.

```bash
# Logical assignment command, from the repository root:
python scripts/nightly_export.py

# Local development when system Python does not have project packages:
#   services/api/.venv/Scripts/python.exe scripts/nightly_export.py
#   (or: cd services/api && uv run python ../../scripts/nightly_export.py)
```

Requires `SECRET_KEY` and `DATABASE_URL` from the environment or `services/api/.env`. The worker never prints those values.

Override the UTC target date without changing code:

```bash
# PowerShell
$env:TARGET_DATE="2026-09-07"; python scripts/nightly_export.py
# bash
TARGET_DATE=2026-09-07 python scripts/nightly_export.py
```

Production pipeline CLI (default, when the testing override is unset):

`python data/pipelines/pipeline.py`

`NIGHTLY_EXPORT_PIPELINE_COMMAND` is a validation-only subprocess override. Production must leave it unset. The worker ignores it unless `NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE=1`.

### Sole production trigger: OS crontab

File: `infra/cron/nightly-export.crontab`

- Expression: `5 0 * * *`
- Timezone: `CRON_TZ=UTC` so the default target date is the completed previous UTC calendar day
- Command: `/bin/sh /path/to/repo/scripts/run_nightly_export.sh`

Replace every `/path/to/repo` with the absolute checkout path on the host (the directory that contains `scripts/` and `data/`). The launcher derives the repository root from its own location, uses `services/api/.venv/bin/python` when that interpreter exists, sets `PYTHONPATH`, and execs `python scripts/nightly_export.py`. Secrets stay in `services/api/.env`.

Unattended validation:

```bash
python scripts/validate_nightly_export.py
```

The four files under `data/pipelines/` (`pipeline.py`, `reporting_store.py`, `transforms.py`, `__init__.py`) are the Milestone 6 CLI copied from the open pipeline branch so this ticket stays reviewable against current `main`. They are not newly authored DEV-53 pipeline logic.

> _Spanish version: [README.es.md](./README.es.md)._
