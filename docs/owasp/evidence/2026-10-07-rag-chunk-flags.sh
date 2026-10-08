#!/bin/bash
set -u
rm -rf /tmp/hc-qdrant-copy
cp -a /var/lib/healthcore/qdrant /tmp/hc-qdrant-copy
chmod -R a+rX /tmp/hc-qdrant-copy
export PYTHONPATH=/opt/healthcore/app:/opt/healthcore/app/services/api
cd /opt/healthcore/app/services/api
/opt/healthcore/app/services/api/.venv/bin/python /tmp/hc-rag-chunk-flags.py
echo PYTHON_EXIT $?
rm -rf /tmp/hc-qdrant-copy /tmp/hc-rag-chunk-flags.py
echo API_STILL "$(systemctl is-active healthcore-api)"
