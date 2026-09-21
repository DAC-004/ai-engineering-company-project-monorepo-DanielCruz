# `data/raw` folder

This folder is intended for **raw data** related to the company: dumps, exports, sample files, event samples, or untransformed datasets.

- **Main purpose**: serve as a landing zone or reference for original data before pipelines process it.
- **Recommendation**: document each dataset’s origin, format, expected size, privacy/PII considerations, and how it is versioned (ideally avoiding sensitive data in the repository).

## `healthcore_sales.csv`

Supplied HealthCore monthly consolidated revenue file used for sales forecasting.

- Columns: `month`, `revenue_usd`, `visits_count`, `avg_revenue_per_visit_usd`, `region`
- 120 first-of-month rows from `2016-01-01` through `2025-12-01`
- Only `consolidated` region rows
- Aggregated monthly figures only: no patient identifiers, diagnoses, or clinical records
- Do not generate, simulate, or edit values in a way that would break the documented growth or seasonality pattern

> _Spanish version: [README.es.md](./README.es.md)._
