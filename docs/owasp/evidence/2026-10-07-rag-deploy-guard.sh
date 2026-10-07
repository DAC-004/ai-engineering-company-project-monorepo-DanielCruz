#!/bin/bash
set -u
DEST=/var/backups/healthcore-rag-20261007T020559Z
TARGET=/opt/healthcore/app/services/api/app/agent/guardrails/untrusted_content.py
BEFORE_EXPECTED=f4be31ea0b3c40a3b347ccd7944bfc07e4e3bd32e213aaea53f2d6f7c526b34c
CANDIDATE_EXPECTED=7b2f767805fbd979fe7827fdabfd04f9b97209137efdbc7d2d8607ebb3b852e5
echo GUARD2_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
CURRENT="$(sha256sum "$TARGET" | awk '{print $1}')"
echo CURRENT_HASH "$CURRENT"
if [ "$CURRENT" != "$BEFORE_EXPECTED" ]; then
  echo UNEXPECTED_CURRENT
  exit 1
fi
install -o root -g root -m 600 "$TARGET" "$DEST/untrusted_content.py.f4be31ea"
install -o root -g root -m 600 /tmp/hc-untrusted-candidate.py "$DEST/untrusted_content.py.candidate2"
rm -f /tmp/hc-untrusted-candidate.py
CANDIDATE="$(sha256sum "$DEST/untrusted_content.py.candidate2" | awk '{print $1}')"
echo CANDIDATE_HASH "$CANDIDATE"
if [ "$CANDIDATE" != "$CANDIDATE_EXPECTED" ]; then
  echo UNEXPECTED_CANDIDATE
  exit 1
fi
python3 - <<'PY'
from pathlib import Path
import difflib
dest = Path("/var/backups/healthcore-rag-20261007T020559Z")
before = (dest / "untrusted_content.py.f4be31ea").read_bytes().replace(b"\r\n", b"\n").decode().splitlines()
candidate = (dest / "untrusted_content.py.candidate2").read_bytes().replace(b"\r\n", b"\n").decode().splitlines()
diff = list(difflib.unified_diff(before, candidate, fromfile="deployed", tofile="candidate", lineterm=""))
removed = [line[1:] for line in diff if line.startswith("-") and not line.startswith("---")]
added = [line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")]
print("ONLY_DEPLOYED", len(removed))
print("ONLY_CANDIDATE", len(added))
print("---REMOVED---")
for line in removed:
    print(line)
print("---ADDED---")
for line in added:
    print(line)
if "disclosure_is_prohibited(source_name)" not in "\n".join(added):
    raise SystemExit(2)
PY
if [ $? -ne 0 ]; then
  echo DIFF_ABORT
  exit 1
fi
if ! /opt/healthcore/app/services/api/.venv/bin/python -m py_compile "$DEST/untrusted_content.py.candidate2"; then
  echo COMPILE_FAIL
  exit 1
fi
rm -rf "$DEST/__pycache__"
install -o root -g healthcore -m 640 "$DEST/untrusted_content.py.candidate2" "${TARGET}.new"
sync
mv -f "${TARGET}.new" "$TARGET"
INSTALLED="$(sha256sum "$TARGET" | awk '{print $1}')"
echo INSTALLED_HASH "$INSTALLED"
stat -c 'INSTALLED_STAT %U %G %a %n' "$TARGET"
if [ "$INSTALLED" != "$CANDIDATE_EXPECTED" ]; then
  echo HASH_MISMATCH
  install -o root -g healthcore -m 640 "$DEST/untrusted_content.py.f4be31ea" "${TARGET}.rollback"
  mv -f "${TARGET}.rollback" "$TARGET"
  exit 1
fi
/opt/healthcore/app/services/api/.venv/bin/python -m py_compile "$TARGET"
echo RAG_HASH "$(sha256sum /opt/healthcore/app/data/pipelines/rag.py)"
echo WEB_PID_BEFORE "$(systemctl show healthcore-web -p MainPID --value)"
if ! systemctl restart healthcore-api; then
  echo RESTART_FAIL
  install -o root -g healthcore -m 640 "$DEST/untrusted_content.py.f4be31ea" "${TARGET}.rollback"
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
  install -o root -g healthcore -m 640 "$DEST/untrusted_content.py.f4be31ea" "${TARGET}.rollback"
  mv -f "${TARGET}.rollback" "$TARGET"
  systemctl restart healthcore-api
  exit 1
fi
echo GUARD2_END "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
