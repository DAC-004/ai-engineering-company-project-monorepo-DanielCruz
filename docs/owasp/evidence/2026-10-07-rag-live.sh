#!/bin/bash
set -u
echo LIVE_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
API_PID="$(systemctl show healthcore-api -p MainPID --value)"
ps -o user=,uid=,group=,pid=,cmd= -p "$API_PID"
echo DEPLOYED_RAG "$(sha256sum /opt/healthcore/app/data/pipelines/rag.py)"
echo DEPLOYED_GUARD "$(sha256sum /opt/healthcore/app/services/api/app/agent/guardrails/untrusted_content.py)"
echo '---CONTROLS---'
systemctl is-active healthcore-api
systemctl is-active healthcore-web
systemctl is-active nginx
systemctl is-active ssh
systemctl is-active certbot-renew.timer
sshd -T | grep -i '^permitrootlogin'
sha256sum /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx
sha256sum /etc/iptables/rules.v4 /etc/iptables/rules.v6
iptables-save | grep -c 'InstanceServices' || true
iptables-save | grep -c -- '-A OUTPUT -d 169.254.0.0/16 -j InstanceServices' || true
echo WEB_PID "$(systemctl show healthcore-web -p MainPID --value)"
echo '---PUBLIC---'
curl -fsS --max-time 20 -o /dev/null -w 'PUBLIC_ROOT %{http_code}\n' https://150.136.171.59/
curl -fsS --max-time 20 -o /dev/null -w 'PUBLIC_LOGIN %{http_code}\n' https://150.136.171.59/login
curl -sS --max-time 20 -o /dev/null -w 'PUBLIC_KNOWLEDGE_GET %{http_code}\n' https://150.136.171.59/knowledge/query
echo '---QUERIES---'
install -o root -g root -m 600 /tmp/hc-rag-live-queries.py /var/backups/healthcore-rag-20261007T020559Z/live_queries.py
install -o root -g root -m 600 /tmp/hc-rag-journal-filter.py /var/backups/healthcore-rag-20261007T020559Z/journal_filter.py
rm -f /tmp/hc-rag-live-queries.py /tmp/hc-rag-journal-filter.py
/usr/bin/python3 /var/backups/healthcore-rag-20261007T020559Z/live_queries.py
echo '---JOURNAL---'
journalctl -u healthcore-api --since '2026-10-07 03:42:54 UTC' -o cat --no-pager > /var/backups/healthcore-rag-20261007T020559Z/api-journal.txt
chmod 600 /var/backups/healthcore-rag-20261007T020559Z/api-journal.txt
/usr/bin/python3 /var/backups/healthcore-rag-20261007T020559Z/journal_filter.py
echo LIVE_END "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
