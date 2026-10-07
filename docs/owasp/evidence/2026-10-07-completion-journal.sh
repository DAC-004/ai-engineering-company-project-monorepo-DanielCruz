#!/bin/bash
set -u
OUT=/var/backups/healthcore-rag-20261007T020559Z/api-journal-completion.txt
journalctl -u healthcore-api --since '2026-10-07 13:58:18 UTC' -o cat --no-pager > "$OUT"
chmod 600 "$OUT"
echo JOURNAL_BYTES "$(wc -c < "$OUT")"
python3 - <<'PY'
from pathlib import Path
text = Path("/var/backups/healthcore-rag-20261007T020559Z/api-journal-completion.txt").read_text(encoding="utf-8", errors="replace")
needles = (
    "Traceback",
    "Replacing an invented cancellation notice",
    "Refusing an invented cancellation deadline",
    "Retrying grounded generation",
    "using refusal",
    "generate_answer backend",
)
for needle in needles:
    print(f"COUNT {needle} {text.lower().count(needle.lower())}")
print("JOURNAL_LINES", text.count("\n"))
PY
