#!/bin/sh
# Unattended OS-crontab launcher for Ticket #DEV-53.
# Resolves the repository from this script so crontab does not depend on /app
# or a developer workstation path. SECRET_KEY and DATABASE_URL are loaded by
# the Python settings module from services/api/.env and are never printed.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

if [ -x "$REPO_ROOT/services/api/.venv/bin/python" ]; then
  PYTHON="$REPO_ROOT/services/api/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  PYTHON=python
fi

export PYTHONPATH="$REPO_ROOT:$REPO_ROOT/services/api${PYTHONPATH:+:$PYTHONPATH}"
unset NIGHTLY_EXPORT_PIPELINE_COMMAND
unset NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE

exec "$PYTHON" "$REPO_ROOT/scripts/nightly_export.py"
