#!/bin/bash
set -u
DEST=/var/backups/healthcore-rag-20261007T020559Z
TARGET=/opt/healthcore/app/data/pipelines/rag.py
EXPECTED=7b2ce262dc58d5767a76510d68cb20fa82bbc1da32314a1cdbdb4c5020facaff
BEFORE=b18d8896e6b6dfcc447d0932f7e4cfa54d92203cbaa3a4b2b7d74b0882ae2c34
echo DEPLOY_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo WEB_PID_BEFORE "$(systemctl show healthcore-web -p MainPID --value)"
echo API_PID_BEFORE "$(systemctl show healthcore-api -p MainPID --value)"

rollback() {
  echo ROLLBACK_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  install -o root -g healthcore -m 640 "$DEST/rag.py.before" "${TARGET}.rollback"
  mv -f "${TARGET}.rollback" "$TARGET"
  echo ROLLBACK_HASH "$(sha256sum "$TARGET")"
  stat -c 'ROLLBACK_STAT %U %G %a %n' "$TARGET"
  systemctl restart healthcore-api
  echo ROLLBACK_ACTIVE "$(systemctl is-active healthcore-api)"
  curl -fsS --max-time 20 http://127.0.0.1:8000/health || echo ROLLBACK_HEALTH_FAIL
}

if ! /opt/healthcore/app/services/api/.venv/bin/python -m py_compile "$DEST/rag.py.candidate"; then
  echo COMPILE_FAIL
  exit 1
fi
echo COMPILE_OK
rm -rf "$DEST/__pycache__"

install -o root -g healthcore -m 640 "$DEST/rag.py.candidate" "${TARGET}.new"
sync
mv -f "${TARGET}.new" "$TARGET"
INSTALLED="$(sha256sum "$TARGET" | awk '{print $1}')"
echo INSTALLED_HASH "$INSTALLED"
stat -c 'INSTALLED_STAT %U %G %a %n' "$TARGET"
if [ "$INSTALLED" != "$EXPECTED" ]; then
  echo HASH_MISMATCH
  rollback
  exit 1
fi

if ! systemctl restart healthcore-api; then
  echo RESTART_FAIL
  rollback
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
echo API_PID_AFTER "$(systemctl show healthcore-api -p MainPID --value)"
echo WEB_PID_AFTER "$(systemctl show healthcore-web -p MainPID --value)"
echo WEB_ACTIVE "$(systemctl is-active healthcore-web)"
if [ "$ACTIVE" != "active" ]; then
  rollback
  exit 1
fi
echo DEPLOY_END "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
