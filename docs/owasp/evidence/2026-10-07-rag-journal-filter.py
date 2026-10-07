"""Print bounded markers from the API journal captured for this deploy."""

from pathlib import Path

JOURNAL = Path("/var/backups/healthcore-rag-20261007T020559Z/api-journal.txt")
NEEDLES = (
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
PREFIXES = (
    "Replacing an invented cancellation notice",
    "Refusing an invented cancellation deadline",
    "Retrying grounded generation",
    "generate_answer backend=",
    "query sources=",
)

text = JOURNAL.read_text(encoding="utf-8", errors="replace")
lower = text.lower()
print("JOURNAL_CHARS", len(text))
for needle in NEEDLES:
    print(f"JOURNAL_PHI {needle} {lower.count(needle)}")
print("JOURNAL_TRACEBACK", text.count("Traceback"))
for line in text.splitlines():
    if any(line.startswith(prefix) or prefix in line for prefix in PREFIXES):
        print("JOURNAL_LINE", line[:400])
