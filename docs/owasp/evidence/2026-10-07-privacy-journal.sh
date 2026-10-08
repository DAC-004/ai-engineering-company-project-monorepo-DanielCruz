#!/bin/bash
set -u
OUT=/var/backups/healthcore-rag-20261007T020559Z/api-journal-privacy.txt
journalctl -u healthcore-api --since '2026-10-07 12:32:20 UTC' -o cat --no-pager > "$OUT"
chmod 600 "$OUT"
echo JOURNAL_BYTES "$(wc -c < "$OUT")"
python3 - <<'PY'
from pathlib import Path
text = Path("/var/backups/healthcore-rag-20261007T020559Z/api-journal-privacy.txt").read_text(encoding="utf-8", errors="replace")
needles = (
    "Traceback",
    "Replacing an invented cancellation notice",
    "Refusing an invented cancellation deadline",
    "Retrying grounded generation",
    "medical record",
    "mrn",
    "date of birth",
    "nhs number",
    "national insurance",
)
for needle in needles:
    print(f"COUNT {needle} {text.lower().count(needle.lower())}")
print("---TAIL---")
print(text[-1800:])
PY
