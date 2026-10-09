#!/bin/bash
set -u
DEST=/var/backups/healthcore-rag-20261007T020559Z
TARGET=/opt/healthcore/app/data/pipelines/rag.py
BEFORE_EXPECTED=a628fa8bd78e168f97e47bad79c01bf6fc87e1cb54f3dfe98c6756358e7c68c7
CANDIDATE_EXPECTED=a15d03168f4585ea68a35b1ac0851b6d3795b81d65c6980a9b2e95f6b5c17414
GUARD=/opt/healthcore/app/services/api/app/agent/guardrails/untrusted_content.py
echo RAG_WRITTEN_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
CURRENT="$(sha256sum "$TARGET" | awk '{print $1}')"
echo CURRENT_HASH "$CURRENT"
if [ "$CURRENT" != "$BEFORE_EXPECTED" ]; then
  echo UNEXPECTED_CURRENT
  exit 1
fi
control_snapshot() {
  local label="$1"
  echo "CONTROL_${label}_WEB_PID $(systemctl show healthcore-web -p MainPID --value)"
  echo "CONTROL_${label}_API_ACTIVE $(systemctl is-active healthcore-api)"
  echo "CONTROL_${label}_WEB_ACTIVE $(systemctl is-active healthcore-web)"
  echo "CONTROL_${label}_NGINX_ACTIVE $(systemctl is-active nginx)"
  echo "CONTROL_${label}_SSH_ACTIVE $(systemctl is-active ssh)"
  echo "CONTROL_${label}_CERTBOT_ACTIVE $(systemctl is-active certbot-renew.timer)"
  echo "CONTROL_${label}_ROOTLOGIN $(sshd -T | awk 'tolower($1)=="permitrootlogin" {print $2}')"
  sha256sum "$GUARD" /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx /etc/iptables/rules.v4 /etc/iptables/rules.v6 /etc/nginx/sites-available/healthcore.conf /etc/letsencrypt/renewal/150.136.171.59.conf /etc/letsencrypt/live/150.136.171.59/fullchain.pem | sed "s/^/CONTROL_${label}_SHA /"
  echo "CONTROL_${label}_INSTANCE $(iptables-save | grep -c InstanceServices || true)"
  echo "CONTROL_${label}_OUTPUT $(iptables-save | grep -c -- '-A OUTPUT -d 169.254.0.0/16 -j InstanceServices' || true)"
  echo "CONTROL_${label}_CERT $(openssl x509 -in /etc/letsencrypt/live/150.136.171.59/fullchain.pem -noout -issuer -dates | tr '\n' ' ')"
  echo
}
control_snapshot BEFORE
install -o root -g root -m 600 "$TARGET" "$DEST/rag.py.a628fa8b"
install -o root -g root -m 600 /tmp/hc-rag-candidate-aec89847.py "$DEST/rag.py.aec89847"
rm -f /tmp/hc-rag-candidate-aec89847.py
CANDIDATE="$(sha256sum "$DEST/rag.py.aec89847" | awk '{print $1}')"
echo CANDIDATE_HASH "$CANDIDATE"
if [ "$CANDIDATE" != "$CANDIDATE_EXPECTED" ]; then
  echo UNEXPECTED_CANDIDATE
  exit 1
fi
python3 - <<'PY'
from pathlib import Path
dest = Path("/var/backups/healthcore-rag-20261007T020559Z")
before = (dest / "rag.py.a628fa8b").read_bytes()
candidate = (dest / "rag.py.aec89847").read_bytes()
print("CANDIDATE_CR", candidate.count(b"\r"))
print("BEFORE_CR", before.count(b"\r"))
print("BYTES_DIFFER", before != candidate)
print("HAS_CANONICAL", b"def _canonical_hour" in candidate)
print("HAS_SPACE_RUN", b"(?:-|\\s+)" in candidate)
print("HAS_NEGATION_LOOKAHEAD", b"(?!{_HOUR_TOKEN}\\b)" in candidate)
if candidate.count(b"\r") != 0:
    raise SystemExit(2)
if b"def _canonical_hour" not in candidate:
    raise SystemExit(3)
if before == candidate:
    raise SystemExit(4)
PY
if [ $? -ne 0 ]; then
  echo CANDIDATE_ABORT
  exit 1
fi
if ! /opt/healthcore/app/services/api/.venv/bin/python -m py_compile "$DEST/rag.py.aec89847"; then
  echo COMPILE_FAIL
  exit 1
fi
install -o root -g healthcore -m 640 "$DEST/rag.py.aec89847" "${TARGET}.new"
sync
mv -f "${TARGET}.new" "$TARGET"
INSTALLED="$(sha256sum "$TARGET" | awk '{print $1}')"
echo INSTALLED_HASH "$INSTALLED"
stat -c 'INSTALLED_STAT %U %G %a %n' "$TARGET"
if [ "$INSTALLED" != "$CANDIDATE_EXPECTED" ]; then
  echo HASH_MISMATCH
  install -o root -g healthcore -m 640 "$DEST/rag.py.a628fa8b" "${TARGET}.rollback"
  mv -f "${TARGET}.rollback" "$TARGET"
  echo ROLLED_BACK_HASH "$(sha256sum "$TARGET" | awk '{print $1}')"
  exit 1
fi
/opt/healthcore/app/services/api/.venv/bin/python -m py_compile "$TARGET"
echo GUARD_HASH "$(sha256sum "$GUARD")"
if ! systemctl restart healthcore-api; then
  echo RESTART_FAIL
  install -o root -g healthcore -m 640 "$DEST/rag.py.a628fa8b" "${TARGET}.rollback"
  mv -f "${TARGET}.rollback" "$TARGET"
  systemctl restart healthcore-api
  echo ROLLED_BACK_HASH "$(sha256sum "$TARGET" | awk '{print $1}')"
  exit 1
fi
ACTIVE=failed
HEALTH_BODY=""
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if [ "$(systemctl is-active healthcore-api)" = "active" ]; then
    HEALTH_BODY="$(curl -fsS --max-time 10 http://127.0.0.1:8000/health || true)"
    if [ -n "$HEALTH_BODY" ]; then
      ACTIVE=active
      break
    fi
  fi
  sleep 1
done
echo HEALTH_BODY "$HEALTH_BODY"
echo API_ACTIVE "$ACTIVE"
echo API_USER "$(systemctl show healthcore-api -p User --value)"
echo API_PID "$(systemctl show healthcore-api -p MainPID --value)"
echo API_ENTER "$(systemctl show healthcore-api -p ActiveEnterTimestamp --value)"
API_PID="$(systemctl show healthcore-api -p MainPID --value)"
ps -o user=,uid=,lstart=,pid=,cmd= -p "$API_PID"
if [ "$ACTIVE" != "active" ]; then
  echo HEALTH_FAIL
  install -o root -g healthcore -m 640 "$DEST/rag.py.a628fa8b" "${TARGET}.rollback"
  mv -f "${TARGET}.rollback" "$TARGET"
  systemctl restart healthcore-api
  echo ROLLED_BACK_HASH "$(sha256sum "$TARGET" | awk '{print $1}')"
  exit 1
fi
echo INSTALLED_HASH_AFTER "$(sha256sum "$TARGET" | awk '{print $1}')"
control_snapshot AFTER
echo RAG_WRITTEN_END "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
