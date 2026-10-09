#!/bin/bash
set -u
DEST=/var/backups/healthcore-rag-20261007T020559Z
APP=/opt/healthcore/app
PY="$APP/services/api/.venv/bin/python"
SAFE="$APP/services/api/app/core/safe_errors.py"
KNOWLEDGE="$APP/services/api/app/routers/knowledge.py"
AGENT="$APP/services/api/app/routers/agent.py"
MAIN="$APP/services/api/app/main.py"
TELEMETRY="$APP/services/api/app/routers/telemetry.py"
INVENTORY="$APP/services/api/app/routers/inventory.py"
CHAT="$APP/services/api/app/services/chat_channel.py"
GATE="$APP/services/api/app/services/streaming_release_gate.py"
RAG="$APP/data/pipelines/rag.py"
GUARD="$APP/services/api/app/agent/guardrails/untrusted_content.py"
SAFE_EXPECTED=0f84861136f695923f649ab48689db89bc9d3aec3ebfa345b171e099d3e973d6
KNOWLEDGE_EXPECTED=5fd0c51e1a33a0d5df1af330bbb2dafc2b4fad302406faf069ee5a8f232efdf6
AGENT_EXPECTED=4999a463ebc55796b4306a2eb1584cb1a057e63a320ce63bbcf35b796422d16a
MAIN_EXPECTED=a7037688c08915d6d76c1cf26a49ec5640c46fddf84c3e51fcdfc7072e89ccca
TELEMETRY_EXPECTED=b472a24f1477fb8087d1975647d7bd8aac8ceec8effbdf4452f912245721e9df
INVENTORY_EXPECTED=874f6b88b1b797b8776c0ea0c9964c4df43a43ed75163f42219fc597f7c57742
CHAT_EXPECTED=f219005d89c6c3070bef5c7f74daafa339ec184ae866d9451e7fd4fc04782e7f
GATE_KEEP=7567c2d67c3e8abb5f46abda061ab2fa616bff5ff78844379a6e71efaf9d3587
RAG_KEEP=0a6e2649fb472c633a62870fb3b6cd16ee0940e0f56b460cf7ba1f2ebda8bae3

echo ERRORPATH_DEPLOY_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

control_snapshot() {
  local label="$1"
  echo "CONTROL_${label}_WEB_PID $(systemctl show healthcore-web -p MainPID --value)"
  echo "CONTROL_${label}_API_ACTIVE $(systemctl is-active healthcore-api)"
  echo "CONTROL_${label}_WEB_ACTIVE $(systemctl is-active healthcore-web)"
  echo "CONTROL_${label}_NGINX_ACTIVE $(systemctl is-active nginx)"
  echo "CONTROL_${label}_SSH_ACTIVE $(systemctl is-active ssh)"
  echo "CONTROL_${label}_CERTBOT_ACTIVE $(systemctl is-active certbot-renew.timer)"
  echo "CONTROL_${label}_ROOTLOGIN $(sshd -T | awk 'tolower($1)=="permitrootlogin" {print $2}')"
  sha256sum "$GATE" "$RAG" "$GUARD" /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx /etc/iptables/rules.v4 /etc/iptables/rules.v6 /etc/nginx/sites-available/healthcore.conf /etc/letsencrypt/renewal/150.136.171.59.conf /etc/letsencrypt/live/150.136.171.59/fullchain.pem | sed "s/^/CONTROL_${label}_SHA /"
  echo "CONTROL_${label}_INSTANCE $(iptables-save | grep -c InstanceServices || true)"
  echo "CONTROL_${label}_OUTPUT $(iptables-save | grep -c -- '-A OUTPUT -d 169.254.0.0/16 -j InstanceServices' || true)"
  echo
}

restore_all() {
  if [ -f "$DEST/safe_errors.py.before" ]; then
    install -o root -g healthcore -m 640 "$DEST/safe_errors.py.before" "$SAFE"
  else
    rm -f "$SAFE"
  fi
  install -o root -g healthcore -m 640 "$DEST/knowledge.py.before" "$KNOWLEDGE"
  install -o root -g healthcore -m 640 "$DEST/agent.py.before" "$AGENT"
  install -o root -g healthcore -m 640 "$DEST/main.py.before" "$MAIN"
  install -o root -g healthcore -m 640 "$DEST/telemetry.py.before" "$TELEMETRY"
  install -o root -g healthcore -m 640 "$DEST/inventory.py.before" "$INVENTORY"
  if [ -f "$DEST/chat_channel.py.before" ]; then
    install -o root -g healthcore -m 640 "$DEST/chat_channel.py.before" "$CHAT"
  fi
}

control_snapshot BEFORE
echo CURRENT_GATE "$(sha256sum "$GATE" | awk '{print $1}')"
echo CURRENT_RAG "$(sha256sum "$RAG" | awk '{print $1}')"
if [ "$(sha256sum "$GATE" | awk '{print $1}')" != "$GATE_KEEP" ] || [ "$(sha256sum "$RAG" | awk '{print $1}')" != "$RAG_KEEP" ]; then
  echo UNEXPECTED_UNCHANGED
  exit 1
fi

if [ -f "$SAFE" ]; then
  install -o root -g root -m 600 "$SAFE" "$DEST/safe_errors.py.before"
  echo BEFORE_SAFE "$(sha256sum "$DEST/safe_errors.py.before" | awk '{print $1}')"
else
  rm -f "$DEST/safe_errors.py.before"
  echo BEFORE_SAFE absent
fi
install -o root -g root -m 600 "$KNOWLEDGE" "$DEST/knowledge.py.before"
install -o root -g root -m 600 "$AGENT" "$DEST/agent.py.before"
install -o root -g root -m 600 "$MAIN" "$DEST/main.py.before"
install -o root -g root -m 600 "$TELEMETRY" "$DEST/telemetry.py.before"
install -o root -g root -m 600 "$INVENTORY" "$DEST/inventory.py.before"
install -o root -g root -m 600 "$CHAT" "$DEST/chat_channel.py.before"
echo BEFORE_KNOWLEDGE "$(sha256sum "$DEST/knowledge.py.before" | awk '{print $1}')"
echo BEFORE_AGENT "$(sha256sum "$DEST/agent.py.before" | awk '{print $1}')"
echo BEFORE_MAIN "$(sha256sum "$DEST/main.py.before" | awk '{print $1}')"
echo BEFORE_TELEMETRY "$(sha256sum "$DEST/telemetry.py.before" | awk '{print $1}')"
echo BEFORE_INVENTORY "$(sha256sum "$DEST/inventory.py.before" | awk '{print $1}')"
echo BEFORE_CHAT "$(sha256sum "$DEST/chat_channel.py.before" | awk '{print $1}')"

install -o root -g root -m 600 /tmp/hc-errorpath-safe_errors.py "$DEST/safe_errors.py.candidate"
install -o root -g root -m 600 /tmp/hc-errorpath-knowledge.py "$DEST/knowledge.py.candidate"
install -o root -g root -m 600 /tmp/hc-errorpath-agent.py "$DEST/agent.py.candidate"
install -o root -g root -m 600 /tmp/hc-errorpath-main.py "$DEST/main.py.candidate"
install -o root -g root -m 600 /tmp/hc-errorpath-telemetry.py "$DEST/telemetry.py.candidate"
install -o root -g root -m 600 /tmp/hc-errorpath-inventory.py "$DEST/inventory.py.candidate"
install -o root -g root -m 600 /tmp/hc-errorpath-chat_channel.py "$DEST/chat_channel.py.candidate"
rm -f /tmp/hc-errorpath-safe_errors.py /tmp/hc-errorpath-knowledge.py /tmp/hc-errorpath-agent.py /tmp/hc-errorpath-main.py /tmp/hc-errorpath-telemetry.py /tmp/hc-errorpath-inventory.py /tmp/hc-errorpath-chat_channel.py

SAFE_CANDIDATE="$(sha256sum "$DEST/safe_errors.py.candidate" | awk '{print $1}')"
KNOWLEDGE_CANDIDATE="$(sha256sum "$DEST/knowledge.py.candidate" | awk '{print $1}')"
AGENT_CANDIDATE="$(sha256sum "$DEST/agent.py.candidate" | awk '{print $1}')"
MAIN_CANDIDATE="$(sha256sum "$DEST/main.py.candidate" | awk '{print $1}')"
TELEMETRY_CANDIDATE="$(sha256sum "$DEST/telemetry.py.candidate" | awk '{print $1}')"
INVENTORY_CANDIDATE="$(sha256sum "$DEST/inventory.py.candidate" | awk '{print $1}')"
CHAT_CANDIDATE="$(sha256sum "$DEST/chat_channel.py.candidate" | awk '{print $1}')"
echo CANDIDATE_SAFE "$SAFE_CANDIDATE"
echo CANDIDATE_KNOWLEDGE "$KNOWLEDGE_CANDIDATE"
echo CANDIDATE_AGENT "$AGENT_CANDIDATE"
echo CANDIDATE_MAIN "$MAIN_CANDIDATE"
echo CANDIDATE_TELEMETRY "$TELEMETRY_CANDIDATE"
echo CANDIDATE_INVENTORY "$INVENTORY_CANDIDATE"
echo CANDIDATE_CHAT "$CHAT_CANDIDATE"
python3 - <<'PY'
from pathlib import Path
dest = Path("/var/backups/healthcore-rag-20261007T020559Z")
names = (
    "safe_errors.py.candidate",
    "knowledge.py.candidate",
    "agent.py.candidate",
    "main.py.candidate",
    "telemetry.py.candidate",
    "inventory.py.candidate",
    "chat_channel.py.candidate",
)
for name in names:
    data = (dest / name).read_bytes()
    print(name, "CR", data.count(b"\r"))
    if data.count(b"\r"):
        raise SystemExit(2)
if b"def log_failure" not in (dest / "safe_errors.py.candidate").read_bytes():
    raise SystemExit(3)
if b"public_validation_errors" not in (dest / "telemetry.py.candidate").read_bytes():
    raise SystemExit(4)
if b"public_validation_errors" not in (dest / "inventory.py.candidate").read_bytes():
    raise SystemExit(5)
if b"safe_route_template" not in (dest / "main.py.candidate").read_bytes():
    raise SystemExit(6)
if b"HealthCore chat generation failed" not in (dest / "chat_channel.py.candidate").read_bytes():
    raise SystemExit(7)
PY
if [ $? -ne 0 ]; then
  echo CANDIDATE_ABORT
  exit 1
fi
if [ "$SAFE_CANDIDATE" != "$SAFE_EXPECTED" ] || [ "$KNOWLEDGE_CANDIDATE" != "$KNOWLEDGE_EXPECTED" ] || [ "$AGENT_CANDIDATE" != "$AGENT_EXPECTED" ] || [ "$MAIN_CANDIDATE" != "$MAIN_EXPECTED" ] || [ "$TELEMETRY_CANDIDATE" != "$TELEMETRY_EXPECTED" ] || [ "$INVENTORY_CANDIDATE" != "$INVENTORY_EXPECTED" ] || [ "$CHAT_CANDIDATE" != "$CHAT_EXPECTED" ]; then
  echo UNEXPECTED_CANDIDATE
  exit 1
fi
if ! "$PY" -m py_compile "$DEST/safe_errors.py.candidate" "$DEST/knowledge.py.candidate" "$DEST/agent.py.candidate" "$DEST/main.py.candidate" "$DEST/telemetry.py.candidate" "$DEST/inventory.py.candidate" "$DEST/chat_channel.py.candidate"; then
  echo COMPILE_FAIL
  exit 1
fi
install -o root -g healthcore -m 640 "$DEST/safe_errors.py.candidate" "$SAFE"
install -o root -g healthcore -m 640 "$DEST/knowledge.py.candidate" "$KNOWLEDGE"
install -o root -g healthcore -m 640 "$DEST/agent.py.candidate" "$AGENT"
install -o root -g healthcore -m 640 "$DEST/main.py.candidate" "$MAIN"
install -o root -g healthcore -m 640 "$DEST/telemetry.py.candidate" "$TELEMETRY"
install -o root -g healthcore -m 640 "$DEST/inventory.py.candidate" "$INVENTORY"
install -o root -g healthcore -m 640 "$DEST/chat_channel.py.candidate" "$CHAT"
echo INSTALLED_SAFE "$(sha256sum "$SAFE" | awk '{print $1}')"
echo INSTALLED_KNOWLEDGE "$(sha256sum "$KNOWLEDGE" | awk '{print $1}')"
echo INSTALLED_AGENT "$(sha256sum "$AGENT" | awk '{print $1}')"
echo INSTALLED_MAIN "$(sha256sum "$MAIN" | awk '{print $1}')"
echo INSTALLED_TELEMETRY "$(sha256sum "$TELEMETRY" | awk '{print $1}')"
echo INSTALLED_INVENTORY "$(sha256sum "$INVENTORY" | awk '{print $1}')"
echo INSTALLED_CHAT "$(sha256sum "$CHAT" | awk '{print $1}')"
stat -c 'INSTALLED_STAT %U %G %a %n' "$SAFE" "$KNOWLEDGE" "$AGENT" "$MAIN" "$TELEMETRY" "$INVENTORY" "$CHAT"
if [ "$(sha256sum "$SAFE" | awk '{print $1}')" != "$SAFE_EXPECTED" ] || [ "$(sha256sum "$KNOWLEDGE" | awk '{print $1}')" != "$KNOWLEDGE_EXPECTED" ] || [ "$(sha256sum "$AGENT" | awk '{print $1}')" != "$AGENT_EXPECTED" ] || [ "$(sha256sum "$MAIN" | awk '{print $1}')" != "$MAIN_EXPECTED" ] || [ "$(sha256sum "$TELEMETRY" | awk '{print $1}')" != "$TELEMETRY_EXPECTED" ] || [ "$(sha256sum "$INVENTORY" | awk '{print $1}')" != "$INVENTORY_EXPECTED" ] || [ "$(sha256sum "$CHAT" | awk '{print $1}')" != "$CHAT_EXPECTED" ]; then
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
if ! PYTHONPATH="$APP:$APP/services/api" "$PY" /tmp/hc-errorpath-host-check.py; then
  echo HOST_CHECK_FAIL
  restore_all
  systemctl restart healthcore-api
  exit 1
fi
rm -f /tmp/hc-errorpath-host-check.py
control_snapshot AFTER
echo ERRORPATH_DEPLOY_END "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
