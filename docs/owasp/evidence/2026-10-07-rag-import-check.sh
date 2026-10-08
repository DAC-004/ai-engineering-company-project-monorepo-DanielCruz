#!/bin/bash
set -u
API_PID="$(systemctl show healthcore-api -p MainPID --value)"
echo IMPORT_PID "$API_PID"
ps -o user=,pid=,lstart=,cmd= -p "$API_PID"
echo IMPORT_HASH "$(sha256sum /opt/healthcore/app/data/pipelines/rag.py)"
cat > /tmp/hc-import-check.py <<'PY'
import inspect
import data.pipelines.rag as rag

source = inspect.getsource(rag._asserted_cancellation_deadline_hours)
print("IMPORTED_DEADLINE_COMPARE", "def _asserted_cancellation_deadline_hours" in source)
print("IMPORTED_REMIND_GUARD", 'rfind("remind")' in source)
PY
chmod 644 /tmp/hc-import-check.py
sudo -u healthcore env PYTHONPATH=/opt/healthcore/app:/opt/healthcore/app/services/api \
  /opt/healthcore/app/services/api/.venv/bin/python /tmp/hc-import-check.py
rm -f /tmp/hc-import-check.py
