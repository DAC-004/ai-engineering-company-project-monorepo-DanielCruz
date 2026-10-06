#!/bin/bash
set -u
diff -u /tmp/checkpointer.py /opt/healthcore/app/data/pipelines/rfp_intake/checkpointer.py || true
echo '---GRAPH---'
diff -u /tmp/graph.py /opt/healthcore/app/services/api/app/agent/graph.py || true
echo '---MEMORY---'
diff -u /tmp/memory_store.py /opt/healthcore/app/services/api/app/agent/memory_store.py || true
echo '---TRACE---'
diff -u /tmp/tracing.py /opt/healthcore/app/services/api/app/agent/tracing.py || true
echo '---DATABASE---'
diff -u /tmp/database.py /opt/healthcore/app/services/api/app/database.py || true
rm -f /tmp/checkpointer.py /tmp/graph.py /tmp/memory_store.py /tmp/tracing.py /tmp/database.py
