"""Index the authorized HealthCore knowledge documents into Qdrant."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.process.rag import setup


if __name__ == "__main__":
    print(json.dumps(setup(), indent=2))
