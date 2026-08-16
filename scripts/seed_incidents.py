#!/usr/bin/env python3
"""Load historical HealthCore incidents from the analyzer CSV.

Usage:
    python scripts/seed_incidents.py
    python scripts/seed_incidents.py scripts/incidents-healthcore.csv

Reuses packages/shared CSV validation and manager transforms. Inserts are
idempotent via a SHA-256 marker; the raw CSV incident_id is never stored.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "services" / "api"
PACKAGES_SHARED = REPO_ROOT / "packages" / "shared"

for path in (REPO_ROOT, API_DIR, PACKAGES_SHARED):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Seed writes TinyDB only. Settings still require SECRET_KEY; do not use JWT.
os.environ.setdefault("SECRET_KEY", "local-seed-placeholder-not-for-production")

from csv_constants import INVALID_RULE_LABELS  # noqa: E402
from csv_validate import classify_invalid_rules  # noqa: E402
from manager_transform import TransformError, transform_valid_csv_row  # noqa: E402

from shared.incident_analyzer.analyze import REQUIRED_COLUMNS  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.incident_service import insert_historical_incident  # noqa: E402

DEFAULT_CSV = REPO_ROOT / "scripts" / "incidents-healthcore.csv"


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    text = csv_path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("The CSV file is empty.")

    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise ValueError("The CSV file has no header row.")

    normalized = [name.strip() for name in reader.fieldnames if name is not None]
    missing = [col for col in REQUIRED_COLUMNS if col not in normalized]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))

    header_map = {
        (name.strip() if name else ""): name for name in reader.fieldnames if name
    }
    rows: list[dict[str, str]] = []
    for raw in reader:
        rows.append(
            {
                field: (raw.get(header_map[field], "") or "").strip()
                for field in REQUIRED_COLUMNS
            }
        )
    if not rows:
        raise ValueError("The CSV file contains no data rows.")
    return rows


def _format_rules(rules: list[str]) -> str:
    return "; ".join(INVALID_RULE_LABELS.get(rule, rule) for rule in rules)


def seed(csv_path: Path) -> int:
    rows = _read_rows(csv_path)
    inserted = 0
    skipped = 0
    invalid_reports: list[str] = []

    for index, row in enumerate(rows, start=2):
        # Row numbers are 1-based including the header, matching typical CSV tools.
        rules = classify_invalid_rules(row)
        if rules:
            invalid_reports.append(f"Row {index}: {_format_rules(rules)}")
            continue

        try:
            fields = transform_valid_csv_row(row)
        except TransformError as exc:
            invalid_reports.append(f"Row {index}: {exc.message}")
            continue

        result = insert_historical_incident(fields)
        if result is None:
            skipped += 1
        else:
            inserted += 1

    print(f"Source: {csv_path}")
    print(f"TinyDB: {get_settings().tinydb_path}")
    print(f"Inserted: {inserted}")
    print(f"Skipped (already present): {skipped}")
    print(f"Invalid (not inserted): {len(invalid_reports)}")
    if invalid_reports:
        print("Invalid records:")
        for line in invalid_reports:
            print(f"  {line}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1:
        print("Usage: python scripts/seed_incidents.py [path_to_csv]", file=sys.stderr)
        return 2

    csv_path = Path(args[0]) if args else DEFAULT_CSV
    if not csv_path.is_file():
        print(f"Error: file not found: {csv_path}", file=sys.stderr)
        return 1

    try:
        return seed(csv_path)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
