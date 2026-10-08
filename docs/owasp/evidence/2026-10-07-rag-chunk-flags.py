"""Print boolean markers for the top cancellation-policy chunk. No chunk body."""

from __future__ import annotations

import os
from pathlib import Path

for line in Path("/etc/healthcore/healthcore.env").read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        continue
    key, value = stripped.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
os.environ["QDRANT_PATH"] = "/tmp/hc-qdrant-copy"

from data.pipelines.rag import _search_scored_points, embed

question = "What notice does the appointment policy require before a cancellation?"
hit = _search_scored_points(embed(question), 1)[0]
payload = getattr(hit, "payload", None) or {}
text = str(payload.get("text", "")).casefold()
section = str(payload.get("section", "")).casefold()
source = str(payload.get("source_document", "")).casefold()
print("TEXT_APPOINTMENT", "appointment" in text)
print("TEXT_CANCEL", "cancel" in text)
print("TEXT_PATIENT", "patient" in text)
print("SECTION_APPOINTMENT", "appointment" in section)
print("SOURCE_APPOINTMENT", "appointment" in source)
print("TEXT_CHARS", len(text))
