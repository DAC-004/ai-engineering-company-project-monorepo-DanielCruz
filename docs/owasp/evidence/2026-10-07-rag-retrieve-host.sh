#!/bin/bash
set -u
echo RETRIEVE_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - <<'PY'
from pathlib import Path
cache = Path("/opt/healthcore/app/data/pipelines/__pycache__")
print("PYCACHE_EXISTS", cache.is_dir())
if cache.is_dir():
    for path in sorted(cache.glob("rag*.pyc")):
        data = path.read_bytes()
        print(path.name, "BYTES", len(data), "HAS_CLAIM", b"_CANCELLATION_CLAIM" in data)
PY
rm -rf /tmp/hc-qdrant-copy
cp -a /var/lib/healthcore/qdrant /tmp/hc-qdrant-copy
chmod -R a+rX /tmp/hc-qdrant-copy
export PYTHONPATH=/opt/healthcore/app:/opt/healthcore/app/services/api
cd /opt/healthcore/app/services/api
/opt/healthcore/app/services/api/.venv/bin/python /tmp/hc-rag-retrieve-check.py
STATUS=$?
rm -rf /tmp/hc-qdrant-copy /tmp/hc-rag-retrieve-check.py
echo RETRIEVE_EXIT $STATUS
echo API_STILL "$(systemctl is-active healthcore-api)"
