"""Explicit synthetic demo seeding. Never runs at application startup."""

import argparse
from pathlib import Path
from shared.healthcore_audit.store import AuditStore
from shared.healthcore_audit.seed import seed_synthetic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, required=True, help="Dedicated local test/demo ledger path"
    )
    parser.add_argument("--synthetic-only", action="store_true", required=True)
    args = parser.parse_args()
    store = AuditStore(args.db)
    print({"synthetic_entries_added": seed_synthetic(store), "integrity": store.verify()})


if __name__ == "__main__":
    main()
