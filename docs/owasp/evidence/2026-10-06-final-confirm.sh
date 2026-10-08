#!/bin/bash
set -u
echo CONFIRM_DATE "$(date -u)"
systemctl is-active healthcore-api
systemctl is-active healthcore-web
systemctl is-active nginx
systemctl is-active ssh
python3 - <<'PY'
from pathlib import Path
values = {}
for line in Path("/etc/healthcore/healthcore.env").read_text().splitlines():
    if not line or line.startswith("#") or "=" not in line:
        continue
    name, value = line.split("=", 1)
    values[name] = value
print("QDRANT_URL_EMPTY", values.get("QDRANT_URL", "") == "")
print("QDRANT_PATH_IS_HOST_STORE", values.get("QDRANT_PATH", "") == "/var/lib/healthcore/qdrant")
print("QDRANT_DIR", Path("/var/lib/healthcore/qdrant").is_dir())
PY
echo '---BACKEND---'
journalctl -u healthcore-api --since '2026-10-06 22:44:00 UTC' -o cat --no-pager | sed -n 's/.*backend=\([^ ]*\).*/BACKEND \1/p' | tail -1
echo '---HOOK_MARKERS---'
grep -E 'DEPLOY_HOOK_EXIT|NGINX_TEST_EXIT|NGINX_RELOAD_EXIT' /var/log/healthcore-renewal/certbot-deploy-hook.log | tail -5
echo '---TMP---'
find /tmp -maxdepth 1 \( -name 'hc-compare' -o -name 'healthcore-final-*' -o -name 'checkpointer.py' -o -name 'graph.py' -o -name 'memory_store.py' -o -name 'tracing.py' -o -name 'database.py' \) -print
echo UBUNTU_STILL_OK
echo CONFIRM_END "$(date -u)"
