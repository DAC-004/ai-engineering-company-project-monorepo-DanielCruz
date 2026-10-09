#!/bin/bash
set -u
echo API_PID "$(systemctl show healthcore-api -p MainPID --value)"
echo API_ACTIVE "$(systemctl is-active healthcore-api)"
echo WEB_PID "$(systemctl show healthcore-web -p MainPID --value)"
sha256sum \
  /opt/healthcore/app/services/api/app/agent/memory_policy.py \
  /opt/healthcore/app/services/api/app/agent/guardrails/text_rules.py \
  /opt/healthcore/app/services/api/app/services/streaming_release_gate.py \
  /opt/healthcore/app/data/pipelines/rag.py \
  /opt/healthcore/app/services/api/app/agent/guardrails/untrusted_content.py
echo PERMIT "$(sudo sshd -T | awk '$1=="permitrootlogin"{print $2}')"
