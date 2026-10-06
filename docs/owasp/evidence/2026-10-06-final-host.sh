#!/bin/bash
set -u
echo HOST_DATE "$(date -u)"
echo '---ACTIVE---'
systemctl is-active healthcore-api
systemctl is-active healthcore-web
systemctl is-active nginx
systemctl is-active ssh
systemctl is-active certbot-renew.timer
echo '---IDENTITY---'
systemctl show healthcore-api -p User -p Group -p FragmentPath --no-pager
systemctl show healthcore-web -p User -p Group --no-pager
id healthcore
echo '---LISTEN---'
ss -lnt | awk 'NR==1 || /:22 |:80 |:443 |:111 |:8000|:3000|:6333|:6334|:5432|:6379|:5555/'
echo '---PERMS---'
stat -c '%U %G %a %n' /opt/healthcore/app /etc/healthcore /var/lib/healthcore /var/log/healthcore /var/log/healthcore-renewal /var/log/healthcore-renewal/certbot-deploy-hook.log /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx
echo '---HOOK---'
grep '^LOG=' /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx
sha256sum /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx
echo '---TIMER---'
systemctl show certbot-renew.timer -p ActiveState -p UnitFileState -p NextElapseUSecRealtime --no-pager
systemctl show certbot-renew.service -p ExecStart --no-pager
echo '---CANDIDATE---'
sha256sum \
  /opt/healthcore/app/data/pipelines/rfp_intake/checkpointer.py \
  /opt/healthcore/app/services/api/app/agent/graph.py \
  /opt/healthcore/app/services/api/app/agent/memory_store.py \
  /opt/healthcore/app/services/api/app/agent/tracing.py \
  /opt/healthcore/app/services/api/app/database.py \
  /opt/healthcore/app/shared/healthcore_rag/config.py
echo '---QDRANT---'
if grep -q '^QDRANT_URL=' /etc/healthcore/healthcore.env; then echo QDRANT_URL_PRESENT 1; else echo QDRANT_URL_PRESENT 0; fi
if pgrep -x qdrant >/dev/null; then echo QDRANT_PROCESS 1; else echo QDRANT_PROCESS 0; fi
test -d /var/lib/healthcore/qdrant && echo QDRANT_DIR 1 || echo QDRANT_DIR 0
echo '---INSTANCESERVICES---'
iptables-save | grep -c 'InstanceServices' || true
iptables-save | grep -c -- '-A OUTPUT -d 169.254.0.0/16 -j InstanceServices' || true
echo '---SSHD---'
sshd -T | grep -i permitrootlogin
echo '---CERT---'
openssl x509 -in /etc/letsencrypt/live/150.136.171.59/fullchain.pem -noout -issuer -dates
echo '---RULES---'
sha256sum /etc/iptables/rules.v4 /etc/iptables/rules.v6
echo HOST_END "$(date -u)"
