#!/bin/bash
set -u
DEST=/var/backups/healthcore-rag-20261007T020559Z
TARGET=/opt/healthcore/app/data/pipelines/rag.py
BEFORE_EXPECTED=ff96e50dcade274b70eefce8c765e0a97c30a7509d836ddc541e19ffbd9eaa94
CANDIDATE_EXPECTED=a628fa8bd78e168f97e47bad79c01bf6fc87e1cb54f3dfe98c6756358e7c68c7
echo RAG6_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
CURRENT="$(sha256sum "$TARGET" | awk '{print $1}')"
echo CURRENT_HASH "$CURRENT"
if [ "$CURRENT" != "$BEFORE_EXPECTED" ]; then
  echo UNEXPECTED_CURRENT
  exit 1
fi
install -o root -g root -m 600 "$TARGET" "$DEST/rag.py.ff96e50d"
install -o root -g root -m 600 /tmp/hc-rag-candidate6.py "$DEST/rag.py.candidate6"
rm -f /tmp/hc-rag-candidate6.py
CANDIDATE="$(sha256sum "$DEST/rag.py.candidate6" | awk '{print $1}')"
echo CANDIDATE_HASH "$CANDIDATE"
if [ "$CANDIDATE" != "$CANDIDATE_EXPECTED" ]; then
  echo UNEXPECTED_CANDIDATE
  exit 1
fi
python3 - <<'PY'
from pathlib import Path
dest = Path("/var/backups/healthcore-rag-20261007T020559Z")
before = (dest / "rag.py.ff96e50d").read_bytes().replace(b"\r\n", b"\n")
candidate = (dest / "rag.py.candidate6").read_bytes().replace(b"\r\n", b"\n")
print("NORMALIZED_EQUAL", before == candidate)
print("CANDIDATE_CR", (dest / "rag.py.candidate6").read_bytes().count(b"\r"))
print("HAS_DEADLINE_COMPARE", b"def _asserted_cancellation_deadline_hours" in candidate)
if before != candidate:
    raise SystemExit(2)
if b"def _asserted_cancellation_deadline_hours" not in candidate:
    raise SystemExit(3)
PY
if [ $? -ne 0 ]; then
  echo DIFF_ABORT
  exit 1
fi
if ! /opt/healthcore/app/services/api/.venv/bin/python -m py_compile "$DEST/rag.py.candidate6"; then
  echo COMPILE_FAIL
  exit 1
fi
install -o root -g healthcore -m 640 "$DEST/rag.py.candidate6" "${TARGET}.new"
sync
mv -f "${TARGET}.new" "$TARGET"
INSTALLED="$(sha256sum "$TARGET" | awk '{print $1}')"
echo INSTALLED_HASH "$INSTALLED"
stat -c 'INSTALLED_STAT %U %G %a %n' "$TARGET"
if [ "$INSTALLED" != "$CANDIDATE_EXPECTED" ]; then
  echo HASH_MISMATCH
  install -o root -g healthcore -m 640 "$DEST/rag.py.ff96e50d" "${TARGET}.rollback"
  mv -f "${TARGET}.rollback" "$TARGET"
  exit 1
fi
/opt/healthcore/app/services/api/.venv/bin/python -m py_compile "$TARGET"
echo GUARD_HASH "$(sha256sum /opt/healthcore/app/services/api/app/agent/guardrails/untrusted_content.py)"
echo WEB_PID_BEFORE "$(systemctl show healthcore-web -p MainPID --value)"
if ! systemctl restart healthcore-api; then
  echo RESTART_FAIL
  install -o root -g healthcore -m 640 "$DEST/rag.py.ff96e50d" "${TARGET}.rollback"
  mv -f "${TARGET}.rollback" "$TARGET"
  systemctl restart healthcore-api
  exit 1
fi
ACTIVE=failed
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if [ "$(systemctl is-active healthcore-api)" = "active" ]; then
    if curl -fsS --max-time 10 http://127.0.0.1:8000/health; then
      echo
      ACTIVE=active
      break
    fi
  fi
  sleep 1
done
echo API_ACTIVE "$ACTIVE"
echo API_USER "$(systemctl show healthcore-api -p User --value)"
echo API_PID "$(systemctl show healthcore-api -p MainPID --value)"
echo WEB_PID_AFTER "$(systemctl show healthcore-web -p MainPID --value)"
if [ "$ACTIVE" != "active" ]; then
  install -o root -g healthcore -m 640 "$DEST/rag.py.ff96e50d" "${TARGET}.rollback"
  mv -f "${TARGET}.rollback" "$TARGET"
  systemctl restart healthcore-api
  exit 1
fi
echo RAG6_END "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
