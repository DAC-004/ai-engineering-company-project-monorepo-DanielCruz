#!/bin/bash
set -u
DEST=/var/backups/healthcore-rag-20261007T020559Z
TARGET=/opt/healthcore/app/data/pipelines/rag.py
BEFORE_EXPECTED=7b2ce262dc58d5767a76510d68cb20fa82bbc1da32314a1cdbdb4c5020facaff
CANDIDATE_EXPECTED=9cd3a8338f9c1dbae57ca0323294975c1642a13a9570c49257b8ec3f19a52d1c
echo RAG2_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
CURRENT="$(sha256sum "$TARGET" | awk '{print $1}')"
echo CURRENT_HASH "$CURRENT"
if [ "$CURRENT" != "$BEFORE_EXPECTED" ]; then
  echo UNEXPECTED_CURRENT
  exit 1
fi
install -o root -g root -m 600 "$TARGET" "$DEST/rag.py.7b2ce262"
install -o root -g root -m 600 /tmp/hc-rag-candidate2.py "$DEST/rag.py.candidate2"
rm -f /tmp/hc-rag-candidate2.py
CANDIDATE="$(sha256sum "$DEST/rag.py.candidate2" | awk '{print $1}')"
echo CANDIDATE_HASH "$CANDIDATE"
if [ "$CANDIDATE" != "$CANDIDATE_EXPECTED" ]; then
  echo UNEXPECTED_CANDIDATE
  exit 1
fi
python3 - <<'PY'
from pathlib import Path
import difflib
dest = Path("/var/backups/healthcore-rag-20261007T020559Z")
before = (dest / "rag.py.7b2ce262").read_bytes().replace(b"\r\n", b"\n").decode().splitlines()
candidate = (dest / "rag.py.candidate2").read_bytes().replace(b"\r\n", b"\n").decode().splitlines()
diff = list(difflib.unified_diff(before, candidate, fromfile="deployed", tofile="candidate", lineterm=""))
removed = [line[1:] for line in diff if line.startswith("-") and not line.startswith("---")]
added = [line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")]
print("ONLY_DEPLOYED", len(removed))
print("ONLY_CANDIDATE", len(added))
print("REMOVED_FIXED_24", any('"24 hour" in lowered' in line for line in removed))
print("ADDED_FIXED_24", any('"24 hour" in lowered' in line for line in added))
joined = "\n".join(added)
if "def _answer_invents_cancellation_deadline" not in joined:
    raise SystemExit(2)
if "_sentence_states_two_hour_cancellation" not in joined:
    raise SystemExit(3)
PY
if [ $? -ne 0 ]; then
  echo DIFF_ABORT
  exit 1
fi
if ! /opt/healthcore/app/services/api/.venv/bin/python -m py_compile "$DEST/rag.py.candidate2"; then
  echo COMPILE_FAIL
  exit 1
fi
rm -rf "$DEST/__pycache__"
install -o root -g healthcore -m 640 "$DEST/rag.py.candidate2" "${TARGET}.new"
sync
mv -f "${TARGET}.new" "$TARGET"
INSTALLED="$(sha256sum "$TARGET" | awk '{print $1}')"
echo INSTALLED_HASH "$INSTALLED"
stat -c 'INSTALLED_STAT %U %G %a %n' "$TARGET"
if [ "$INSTALLED" != "$CANDIDATE_EXPECTED" ]; then
  echo HASH_MISMATCH
  install -o root -g healthcore -m 640 "$DEST/rag.py.7b2ce262" "${TARGET}.rollback"
  mv -f "${TARGET}.rollback" "$TARGET"
  exit 1
fi
/opt/healthcore/app/services/api/.venv/bin/python -m py_compile "$TARGET"
echo GUARD_HASH "$(sha256sum /opt/healthcore/app/services/api/app/agent/guardrails/untrusted_content.py)"
echo WEB_PID_BEFORE "$(systemctl show healthcore-web -p MainPID --value)"
if ! systemctl restart healthcore-api; then
  echo RESTART_FAIL
  install -o root -g healthcore -m 640 "$DEST/rag.py.7b2ce262" "${TARGET}.rollback"
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
  install -o root -g healthcore -m 640 "$DEST/rag.py.7b2ce262" "${TARGET}.rollback"
  mv -f "${TARGET}.rollback" "$TARGET"
  systemctl restart healthcore-api
  exit 1
fi
echo RAG2_END "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
