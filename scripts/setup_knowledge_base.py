"""Index the authorized HealthCore knowledge documents into Qdrant."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.process.rag import setup
from shared.healthcore_rag.qdrant import close_qdrant_client, resolve_embedded_qdrant_path


if __name__ == "__main__":
    resolve_embedded_qdrant_path(allow_pytest_override=False)
    try:
        print(json.dumps(setup(), indent=2))
    finally:
        close_qdrant_client()
