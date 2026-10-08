#!/bin/bash
set -u
sha256sum \
  /opt/healthcore/app/data/pipelines/rfp_intake/checkpointer.py \
  /opt/healthcore/app/services/api/app/agent/graph.py \
  /opt/healthcore/app/services/api/app/agent/memory_store.py \
  /opt/healthcore/app/services/api/app/agent/tracing.py \
  /opt/healthcore/app/services/api/app/database.py \
  /opt/healthcore/app/shared/healthcore_rag/config.py
stat -c '%Y %s %n' \
  /opt/healthcore/app/data/pipelines/rfp_intake/checkpointer.py \
  /opt/healthcore/app/services/api/app/agent/graph.py \
  /opt/healthcore/app/services/api/app/agent/memory_store.py \
  /opt/healthcore/app/services/api/app/agent/tracing.py \
  /opt/healthcore/app/services/api/app/database.py \
  /opt/healthcore/app/shared/healthcore_rag/config.py
