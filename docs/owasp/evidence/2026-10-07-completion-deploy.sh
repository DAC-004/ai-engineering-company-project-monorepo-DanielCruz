#!/bin/bash
set -u
DEST=/var/backups/healthcore-rag-20261007T020559Z
APP=/opt/healthcore/app
PY="$APP/services/api/.venv/bin/python"
GATE="$APP/services/api/app/services/streaming_release_gate.py"
RAG="$APP/data/pipelines/rag.py"
MEMORY="$APP/services/api/app/agent/memory_policy.py"
RULES="$APP/services/api/app/agent/guardrails/text_rules.py"
GUARD="$APP/services/api/app/agent/guardrails/untrusted_content.py"
GATE_BEFORE=88387f4ad52725c9168a088d3362611090c7b61cfe66064c3cc70178227f667a
RAG_BEFORE=a15d03168f4585ea68a35b1ac0851b6d3795b81d65c6980a9b2e95f6b5c17414
GATE_EXPECTED=7567c2d67c3e8abb5f46abda061ab2fa616bff5ff78844379a6e71efaf9d3587
RAG_EXPECTED=0a6e2649fb472c633a62870fb3b6cd16ee0940e0f56b460cf7ba1f2ebda8bae3

echo COMPLETION_DEPLOY_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

control_snapshot() {
  local label="$1"
  echo "CONTROL_${label}_WEB_PID $(systemctl show healthcore-web -p MainPID --value)"
  echo "CONTROL_${label}_API_ACTIVE $(systemctl is-active healthcore-api)"
  echo "CONTROL_${label}_WEB_ACTIVE $(systemctl is-active healthcore-web)"
  echo "CONTROL_${label}_NGINX_ACTIVE $(systemctl is-active nginx)"
  echo "CONTROL_${label}_SSH_ACTIVE $(systemctl is-active ssh)"
  echo "CONTROL_${label}_CERTBOT_ACTIVE $(systemctl is-active certbot-renew.timer)"
  echo "CONTROL_${label}_ROOTLOGIN $(sshd -T | awk 'tolower($1)=="permitrootlogin" {print $2}')"
  sha256sum "$MEMORY" "$RULES" "$GUARD" "$GATE" "$RAG" /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx /etc/iptables/rules.v4 /etc/iptables/rules.v6 /etc/nginx/sites-available/healthcore.conf /etc/letsencrypt/renewal/150.136.171.59.conf /etc/letsencrypt/live/150.136.171.59/fullchain.pem | sed "s/^/CONTROL_${label}_SHA /"
  echo "CONTROL_${label}_INSTANCE $(iptables-save | grep -c InstanceServices || true)"
  echo "CONTROL_${label}_OUTPUT $(iptables-save | grep -c -- '-A OUTPUT -d 169.254.0.0/16 -j InstanceServices' || true)"
  echo "CONTROL_${label}_CERT $(openssl x509 -in /etc/letsencrypt/live/150.136.171.59/fullchain.pem -noout -issuer -dates | tr '\n' ' ')"
  echo
}

restore_completion() {
  install -o root -g healthcore -m 640 "$DEST/streaming_release_gate.py.88387f4a" "$GATE"
  install -o root -g healthcore -m 640 "$DEST/rag.py.a15d0316" "$RAG"
}

CURRENT_GATE="$(sha256sum "$GATE" | awk '{print $1}')"
CURRENT_RAG="$(sha256sum "$RAG" | awk '{print $1}')"
echo CURRENT_GATE "$CURRENT_GATE"
echo CURRENT_RAG "$CURRENT_RAG"
if [ "$CURRENT_GATE" != "$GATE_BEFORE" ] || [ "$CURRENT_RAG" != "$RAG_BEFORE" ]; then
  echo UNEXPECTED_CURRENT
  exit 1
fi

control_snapshot BEFORE
install -o root -g root -m 600 "$GATE" "$DEST/streaming_release_gate.py.88387f4a"
install -o root -g root -m 600 "$RAG" "$DEST/rag.py.a15d0316"
install -o root -g root -m 600 /tmp/hc-completion-gate.py "$DEST/streaming_release_gate.py.7567c2d6"
install -o root -g root -m 600 /tmp/hc-completion-rag.py "$DEST/rag.py.0a6e2649"
rm -f /tmp/hc-completion-gate.py /tmp/hc-completion-rag.py

GATE_CANDIDATE="$(sha256sum "$DEST/streaming_release_gate.py.7567c2d6" | awk '{print $1}')"
RAG_CANDIDATE="$(sha256sum "$DEST/rag.py.0a6e2649" | awk '{print $1}')"
echo CANDIDATE_GATE "$GATE_CANDIDATE"
echo CANDIDATE_RAG "$RAG_CANDIDATE"
python3 - <<'PY'
from pathlib import Path
dest = Path("/var/backups/healthcore-rag-20261007T020559Z")
gate = (dest / "streaming_release_gate.py.7567c2d6").read_bytes()
rag = (dest / "rag.py.0a6e2649").read_bytes()
print("GATE_CR", gate.count(b"\r"))
print("RAG_CR", rag.count(b"\r"))
print("GATE_HAS_PROTECTED", b"def _protected_open_suffix_length" in gate)
print("RAG_HAS_COMPLETION_RELEASE", b"released_at_completion" in rag)
if gate.count(b"\r") or rag.count(b"\r"):
    raise SystemExit(2)
if b"def _protected_open_suffix_length" not in gate:
    raise SystemExit(3)
if b"released_at_completion" not in rag:
    raise SystemExit(4)
PY
if [ $? -ne 0 ]; then
  echo CANDIDATE_ABORT
  exit 1
fi
if [ "$GATE_CANDIDATE" != "$GATE_EXPECTED" ] || [ "$RAG_CANDIDATE" != "$RAG_EXPECTED" ]; then
  echo UNEXPECTED_CANDIDATE
  exit 1
fi
if ! "$PY" -m py_compile "$DEST/streaming_release_gate.py.7567c2d6" "$DEST/rag.py.0a6e2649"; then
  echo COMPILE_FAIL
  exit 1
fi
install -o root -g healthcore -m 640 "$DEST/streaming_release_gate.py.7567c2d6" "$GATE"
install -o root -g healthcore -m 640 "$DEST/rag.py.0a6e2649" "$RAG"
echo INSTALLED_GATE "$(sha256sum "$GATE" | awk '{print $1}')"
echo INSTALLED_RAG "$(sha256sum "$RAG" | awk '{print $1}')"
stat -c 'INSTALLED_STAT %U %G %a %n' "$GATE" "$RAG"
if [ "$(sha256sum "$GATE" | awk '{print $1}')" != "$GATE_EXPECTED" ] || [ "$(sha256sum "$RAG" | awk '{print $1}')" != "$RAG_EXPECTED" ]; then
  echo HASH_MISMATCH
  restore_completion
  exit 1
fi
if ! systemctl restart healthcore-api; then
  echo RESTART_FAIL
  restore_completion
  systemctl restart healthcore-api
  exit 1
fi
ACTIVE=failed
HEALTH_BODY=""
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if [ "$(systemctl is-active healthcore-api)" = "active" ]; then
    if HEALTH_BODY="$(curl -fsS --max-time 10 http://127.0.0.1:8000/health)"; then
      echo
      echo HEALTH_BODY "$HEALTH_BODY"
      ACTIVE=active
      break
    fi
  fi
  sleep 1
done
echo API_ACTIVE "$ACTIVE"
echo API_USER "$(systemctl show healthcore-api -p User --value)"
echo API_PID "$(systemctl show healthcore-api -p MainPID --value)"
echo API_ENTER "$(systemctl show healthcore-api -p ActiveEnterTimestamp --value)"
if [ "$ACTIVE" != "active" ]; then
  echo HEALTH_FAIL
  restore_completion
  systemctl restart healthcore-api
  exit 1
fi
if ! PYTHONPATH="$APP:$APP/services/api" "$PY" /tmp/hc-completion-gate-check.py; then
  echo GATE_CHECK_FAIL
  restore_completion
  systemctl restart healthcore-api
  exit 1
fi
rm -f /tmp/hc-completion-gate-check.py
control_snapshot AFTER
echo COMPLETION_DEPLOY_END "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
