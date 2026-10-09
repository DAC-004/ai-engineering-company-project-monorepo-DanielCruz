#!/bin/bash
set -u
DEST=/var/backups/healthcore-rag-20261007T020559Z
echo LIVE_START "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
API_PID="$(systemctl show healthcore-api -p MainPID --value)"
ps -o user=,uid=,lstart=,pid=,cmd= -p "$API_PID"
echo API_ENTER "$(systemctl show healthcore-api -p ActiveEnterTimestamp --value)"
echo DEPLOYED_RAG "$(sha256sum /opt/healthcore/app/data/pipelines/rag.py)"
echo DEPLOYED_GUARD "$(sha256sum /opt/healthcore/app/services/api/app/agent/guardrails/untrusted_content.py)"
echo WEB_PID "$(systemctl show healthcore-web -p MainPID --value)"
install -o root -g root -m 600 /tmp/hc-rag-live-queries.py "$DEST/live_queries.py"
install -o root -g root -m 600 /tmp/hc-rag-journal-filter.py "$DEST/journal_filter.py"
rm -f /tmp/hc-rag-live-queries.py /tmp/hc-rag-journal-filter.py
/usr/bin/python3 "$DEST/live_queries.py"
echo '---JOURNAL---'
journalctl -u healthcore-api --since '2026-10-07 11:28:01 UTC' -o cat --no-pager > "$DEST/api-journal-written-hours.txt"
chmod 600 "$DEST/api-journal-written-hours.txt"
/usr/bin/python3 - <<'PY'
from pathlib import Path
journal = Path("/var/backups/healthcore-rag-20261007T020559Z/api-journal-written-hours.txt")
needles = (
    "medical record",
    "mrn",
    "date of birth",
    "nhs number",
    "national insurance",
    "insurance number",
    "lab result",
    "clinical note",
    "member identifier",
    "diagnosis",
)
prefixes = (
    "Replacing an invented cancellation notice",
    "Refusing an invented cancellation deadline",
    "Retrying grounded generation",
    "generate_answer backend=",
    "query sources=",
)
text = journal.read_text(encoding="utf-8", errors="replace")
lower = text.lower()
print("JOURNAL_CHARS", len(text))
for needle in needles:
    print(f"JOURNAL_PHI {needle} {lower.count(needle)}")
print("JOURNAL_TRACEBACK", text.count("Traceback"))
for line in text.splitlines():
    if any(prefix in line for prefix in prefixes):
        print("JOURNAL_LINE", line[:400])
PY
echo LIVE_END "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
