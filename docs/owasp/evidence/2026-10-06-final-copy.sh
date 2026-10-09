#!/bin/bash
set -u
rm -rf /tmp/hc-compare
mkdir -p /tmp/hc-compare
cp /opt/healthcore/app/data/pipelines/rfp_intake/checkpointer.py /tmp/hc-compare/checkpointer.py
cp /opt/healthcore/app/services/api/app/agent/graph.py /tmp/hc-compare/graph.py
cp /opt/healthcore/app/services/api/app/agent/memory_store.py /tmp/hc-compare/memory_store.py
cp /opt/healthcore/app/services/api/app/agent/tracing.py /tmp/hc-compare/tracing.py
cp /opt/healthcore/app/services/api/app/database.py /tmp/hc-compare/database.py
cp /opt/healthcore/app/shared/healthcore_rag/config.py /tmp/hc-compare/config.py
chmod 644 /tmp/hc-compare/*
chown ubuntu:ubuntu /tmp/hc-compare /tmp/hc-compare/*
runuser -u healthcore -- test -w /var/log/healthcore-renewal
echo DIR_W $?
runuser -u healthcore -- test -w /var/log/healthcore-renewal/certbot-deploy-hook.log
echo FILE_W $?
runuser -u healthcore -- test -w /var/log/healthcore
echo APPLOG_DIR_W $?
