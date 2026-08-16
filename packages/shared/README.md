# Shared HealthCore packages

TypeScript placeholder types remain in `types/`.

Python modules in this folder are the single copy of incident validation and
HealthCore manager constants, reused by:

- `scripts/analyze.py` (via `shared/incident_analyzer` re-exports)
- `scripts/seed_incidents.py`
- `services/api` analyzer and incident-manager routes

| Module | Role |
| --- | --- |
| `csv_constants.py` | Analyzer clinic IDs, CSV categories, invalid-rule keys |
| `csv_validate.py` | `classify_invalid_rules` for historical CSV rows |
| `manager_constants.py` | Manager categories, statuses, origins, branches, transitions, CSV maps |
| `manager_transform.py` | CSV → model transforms and derived seed markers |

Consumers add this directory to `sys.path` (not imported as `shared`, which is
already the repo-root analyzer package).
