#!/bin/bash
set -u
DEST=/var/backups/healthcore-rag-20261007T020559Z
APP=/opt/healthcore/app
PY="$APP/services/api/.venv/bin/python"
MEMORY="$APP/services/api/app/agent/memory_policy.py"
RULES="$APP/services/api/app/agent/guardrails/text_rules.py"
GATE="$APP/services/api/app/services/streaming_release_gate.py"
GUARD="$APP/services/api/app/agent/guardrails/untrusted_content.py"
RAG="$APP/data/pipelines/rag.py"
MEM_EXPECTED=fdfd3a3282ab4bedb8e6fe2b82df935bf6c22a9036a48a9d03633f028a8d35c0
RULES_EXPECTED=6aef345eea6d1784225ae81adc67347bc5b021c068e549a896d7d2b48f966d87
GATE_EXPECTED=88387f4ad52725c9168a088d3362611090c7b61cfe66064c3cc70178227f667a

echo PRIVACY_DEPLOY_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

control_snapshot() {
  local label="$1"
  echo "CONTROL_${label}_WEB_PID $(systemctl show healthcore-web -p MainPID --value)"
  echo "CONTROL_${label}_API_ACTIVE $(systemctl is-active healthcore-api)"
  echo "CONTROL_${label}_WEB_ACTIVE $(systemctl is-active healthcore-web)"
  echo "CONTROL_${label}_NGINX_ACTIVE $(systemctl is-active nginx)"
  echo "CONTROL_${label}_SSH_ACTIVE $(systemctl is-active ssh)"
  echo "CONTROL_${label}_CERTBOT_ACTIVE $(systemctl is-active certbot-renew.timer)"
  echo "CONTROL_${label}_ROOTLOGIN $(sshd -T | awk 'tolower($1)=="permitrootlogin" {print $2}')"
  sha256sum "$GUARD" "$RAG" /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx /etc/iptables/rules.v4 /etc/iptables/rules.v6 /etc/nginx/sites-available/healthcore.conf /etc/letsencrypt/renewal/150.136.171.59.conf /etc/letsencrypt/live/150.136.171.59/fullchain.pem | sed "s/^/CONTROL_${label}_SHA /"
  echo "CONTROL_${label}_INSTANCE $(iptables-save | grep -c InstanceServices || true)"
  echo "CONTROL_${label}_OUTPUT $(iptables-save | grep -c -- '-A OUTPUT -d 169.254.0.0/16 -j InstanceServices' || true)"
  echo "CONTROL_${label}_CERT $(openssl x509 -in /etc/letsencrypt/live/150.136.171.59/fullchain.pem -noout -issuer -dates | tr '\n' ' ')"
  echo
}

restore_all() {
  install -o root -g healthcore -m 640 "$DEST/memory_policy.py.before" "$MEMORY"
  install -o root -g healthcore -m 640 "$DEST/text_rules.py.before" "$RULES"
  install -o root -g healthcore -m 640 "$DEST/streaming_release_gate.py.before" "$GATE"
}

control_snapshot BEFORE
install -o root -g root -m 600 "$MEMORY" "$DEST/memory_policy.py.before"
install -o root -g root -m 600 "$RULES" "$DEST/text_rules.py.before"
install -o root -g root -m 600 "$GATE" "$DEST/streaming_release_gate.py.before"
echo BEFORE_MEMORY "$(sha256sum "$DEST/memory_policy.py.before" | awk '{print $1}')"
echo BEFORE_RULES "$(sha256sum "$DEST/text_rules.py.before" | awk '{print $1}')"
echo BEFORE_GATE "$(sha256sum "$DEST/streaming_release_gate.py.before" | awk '{print $1}')"

install -o root -g root -m 600 /tmp/hc-privacy-memory_policy.py "$DEST/memory_policy.py.candidate"
install -o root -g root -m 600 /tmp/hc-privacy-text_rules.py "$DEST/text_rules.py.candidate"
install -o root -g root -m 600 /tmp/hc-privacy-streaming_release_gate.py "$DEST/streaming_release_gate.py.candidate"
rm -f /tmp/hc-privacy-memory_policy.py /tmp/hc-privacy-text_rules.py /tmp/hc-privacy-streaming_release_gate.py

MEM_CANDIDATE="$(sha256sum "$DEST/memory_policy.py.candidate" | awk '{print $1}')"
RULES_CANDIDATE="$(sha256sum "$DEST/text_rules.py.candidate" | awk '{print $1}')"
GATE_CANDIDATE="$(sha256sum "$DEST/streaming_release_gate.py.candidate" | awk '{print $1}')"
echo CANDIDATE_MEMORY "$MEM_CANDIDATE"
echo CANDIDATE_RULES "$RULES_CANDIDATE"
echo CANDIDATE_GATE "$GATE_CANDIDATE"
if [ "$MEM_CANDIDATE" != "$MEM_EXPECTED" ] || [ "$RULES_CANDIDATE" != "$RULES_EXPECTED" ] || [ "$GATE_CANDIDATE" != "$GATE_EXPECTED" ]; then
  echo UNEXPECTED_CANDIDATE
  exit 1
fi
if ! "$PY" -m py_compile "$DEST/memory_policy.py.candidate" "$DEST/text_rules.py.candidate" "$DEST/streaming_release_gate.py.candidate"; then
  echo COMPILE_FAIL
  exit 1
fi
install -o root -g healthcore -m 640 "$DEST/memory_policy.py.candidate" "$MEMORY"
install -o root -g healthcore -m 640 "$DEST/text_rules.py.candidate" "$RULES"
install -o root -g healthcore -m 640 "$DEST/streaming_release_gate.py.candidate" "$GATE"
echo INSTALLED_MEMORY "$(sha256sum "$MEMORY" | awk '{print $1}')"
echo INSTALLED_RULES "$(sha256sum "$RULES" | awk '{print $1}')"
echo INSTALLED_GATE "$(sha256sum "$GATE" | awk '{print $1}')"
stat -c 'INSTALLED_STAT %U %G %a %n' "$MEMORY" "$RULES" "$GATE"
if [ "$(sha256sum "$MEMORY" | awk '{print $1}')" != "$MEM_EXPECTED" ] || [ "$(sha256sum "$RULES" | awk '{print $1}')" != "$RULES_EXPECTED" ] || [ "$(sha256sum "$GATE" | awk '{print $1}')" != "$GATE_EXPECTED" ]; then
  echo HASH_MISMATCH
  restore_all
  exit 1
fi
if ! systemctl restart healthcore-api; then
  echo RESTART_FAIL
  restore_all
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
  restore_all
  systemctl restart healthcore-api
  exit 1
fi
control_snapshot AFTER
echo PRIVACY_DEPLOY_END "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
