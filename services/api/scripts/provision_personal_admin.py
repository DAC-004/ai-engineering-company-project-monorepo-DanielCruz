"""Local operator command: provision the approved personal Admin identity.

Working directory: services/api
Interpreter: services/api/.venv/Scripts/python.exe

Usage (no password on the command line, in the environment, or in a file):

    python scripts/provision_personal_admin.py

A new account prompts twice with a hidden getpass confirmation. An existing
matching account is upgraded or left unchanged without collecting a password.
This command does not start the API, run the five-user seed, or open a public route.
"""

from __future__ import annotations

import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

from app.services.personal_admin_provision import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
