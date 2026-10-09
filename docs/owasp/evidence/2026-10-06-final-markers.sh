#!/bin/bash
set -u
for path in \
  /opt/healthcore/app/data/pipelines/rfp_intake/checkpointer.py \
  /opt/healthcore/app/services/api/app/agent/graph.py \
  /opt/healthcore/app/services/api/app/agent/memory_store.py \
  /opt/healthcore/app/services/api/app/agent/tracing.py \
  /opt/healthcore/app/services/api/app/database.py \
  /opt/healthcore/app/shared/healthcore_rag/config.py
do
  count=$(grep -c 'runtime_data_path' "$path" || true)
  echo "MARKER $count $path"
done
