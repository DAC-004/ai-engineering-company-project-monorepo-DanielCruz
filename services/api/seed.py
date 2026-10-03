"""Compatibility entrypoint for `python seed.py` and the hatch/uv script target."""

from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.seed_runner import main

if __name__ == "__main__":
    main()
