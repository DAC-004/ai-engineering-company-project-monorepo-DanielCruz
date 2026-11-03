"""CLI: seed HealthCore inventory tables when they are empty."""

from __future__ import annotations

import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

from sqlmodel import Session  # noqa: E402

from app.db.database import get_engine, init_databases  # noqa: E402
from app.services.inventory_seed import (  # noqa: E402
    apply_seed_command_result,
    seed_inventory_if_empty,
)


def main() -> int:
    init_databases()
    with Session(get_engine()) as session:
        result = seed_inventory_if_empty(session)
    return apply_seed_command_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
