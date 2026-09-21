# `shared` folder

This folder is reserved for **unbundled shared resources** in the monorepo: templates, schemas, common assets, short technical documentation, or configuration shared across several components.

- **Main purpose**: provide a neutral place for reusable items that do not fit as an application (`apps/`) or as a package/library (`packages/`).
- **Recommendation**: document what each subfolder or file contains and link to it from consuming components to keep traceability.

## `sales_forecast/`

Reusable HealthCore monthly-revenue helpers used by `scripts/train_sales_forecast.py` and `tests/pipelines/`: load/validate, causal features, chronological split, metrics, Random Forest fitting, and training-only expanding-window variability.

> _Spanish version: [README.es.md](./README.es.md)._
