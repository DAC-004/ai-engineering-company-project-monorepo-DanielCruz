#!/bin/bash
set -u
echo HOST_DATE "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo '---ACTIVE---'
systemctl is-active healthcore-api
systemctl is-active healthcore-web
systemctl is-active nginx
systemctl is-active ssh
systemctl is-active certbot-renew.timer
echo '---API-UNIT---'
systemctl show healthcore-api -p User -p Group -p MainPID -p ActiveState -p FragmentPath -p WorkingDirectory --no-pager
systemctl show healthcore-api -p Environment --no-pager
echo '---RAG-FILE---'
stat -c '%U %G %a %n' /opt/healthcore/app /opt/healthcore/app/data /opt/healthcore/app/data/pipelines /opt/healthcore/app/data/pipelines/rag.py
sha256sum /opt/healthcore/app/data/pipelines/rag.py
wc -c /opt/healthcore/app/data/pipelines/rag.py
python3 - <<'PY'
from pathlib import Path
text = Path("/opt/healthcore/app/data/pipelines/rag.py").read_bytes()
print("DEPLOYED_CRLF", text.count(b"\r\n"))
print("DEPLOYED_HAS_REPLACER", b"_answer_replaces_cancellation_threshold" in text)
print("DEPLOYED_HAS_CLAIM", b"_CANCELLATION_CLAIM" in text)
PY
echo '---PYTHON---'
/opt/healthcore/app/services/api/.venv/bin/python -V
echo '---CONTROLS---'
sshd -T | grep -i '^permitrootlogin'
sha256sum /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx
grep '^LOG=' /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx
sha256sum /etc/iptables/rules.v4 /etc/iptables/rules.v6
iptables-save | grep -c 'InstanceServices' || true
iptables-save | grep -c -- '-A OUTPUT -d 169.254.0.0/16 -j InstanceServices' || true
echo '---LISTEN---'
ss -lnt | awk 'NR==1 || /:22 |:80 |:443 |:111 |:8000|:3000|:6333|:6334|:5432|:6379|:5555/'
echo '---BACKUP-PARENT---'
stat -c '%U %G %a %n' /var/backups
runuser -u healthcore -- test -w /var/backups; echo HEALTHCORE_BACKUP_PARENT_WRITABLE $?
runuser -u healthcore -- test -w /opt/healthcore/app/data/pipelines; echo HEALTHCORE_CODE_DIR_WRITABLE $?
