"""CLI entry for `uv run seed` — loads CONTEXT suppliers into TinyDB."""

from __future__ import annotations

from datetime import datetime, timezone

from tinydb import Query

from app.database import close_db, get_suppliers_table
from app.seed_data import SUPPLIERS_SEED


def _seed_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_suppliers() -> int:
    """Insert missing CONTEXT suppliers. Returns the number of newly inserted rows."""
    table = get_suppliers_table()
    supplier_query = Query()
    inserted = 0

    for supplier in SUPPLIERS_SEED:
        # Deduplicate by exact trade name — CONTEXT names are unique in the seed set.
        existing = table.search(supplier_query.name == supplier["name"])
        if existing:
            continue

        record = dict(supplier)
        record["updated_at"] = _seed_timestamp()
        table.insert(record)
        inserted += 1

    return inserted


def main() -> None:
    try:
        inserted = seed_suppliers()
        total = len(get_suppliers_table())
        print(f"Inserted {inserted} supplier record(s).")
        print(f"Directory now contains {total} supplier(s).")
    finally:
        close_db()


if __name__ == "__main__":
    main()
