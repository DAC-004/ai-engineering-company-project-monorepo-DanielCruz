"""Read the deployed retrieval result for the three live questions.

Print source names and policy markers. Do not print a generation API key.
"""

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

from data.pipelines.rag import _search_scored_points, embed, retrieve

QUESTIONS = (
    "What notice does the appointment policy require before a cancellation?",
    "When is the last reminder sent before an appointment?",
    "What is the average availability for a routine appointment?",
)
print("GENERATION_API_KEY_SET", bool(os.environ.get("GENERATION_API_KEY")))
wide_question = QUESTIONS[0]
print("WIDE", wide_question)
for index, hit in enumerate(_search_scored_points(embed(wide_question), 8)):
    payload = getattr(hit, "payload", None) or {}
    text = str(payload.get("text", ""))
    lowered = text.lower()
    print(
        "HIT",
        index,
        "SCORE",
        f"{float(getattr(hit, 'score', 0.0)):.4f}",
        "SOURCE",
        payload.get("source_document"),
        "SECTION",
        str(payload.get("section", ""))[:80],
        "HAS_24_HOUR_CANCELL",
        "24 hour" in lowered and "cancell" in lowered,
    )
for question in QUESTIONS:
    print("QUESTION", question)
    chunks = retrieve(question)
    print("KEPT", len(chunks))
    for index, chunk in enumerate(chunks):
        source = str(chunk.get("source_document", ""))
        section = str(chunk.get("section", ""))
        text = str(chunk.get("text", ""))
        lowered = text.lower()
        print(
            "CHUNK",
            index,
            "SOURCE",
            source,
            "SECTION",
            section,
            "HAS_24_HOUR_CANCELL",
            "24 hour" in lowered and "cancell" in lowered,
            "HAS_2_HOUR",
            "2 hour" in lowered or "2h" in lowered,
            "HAS_3_TO_5",
            "3 to 5" in lowered,
        )
        if source.endswith("healthcore-appointment-policy.en.md"):
            for line in text.splitlines():
                probe = line.lower()
                if "cancell" in probe or "remind" in probe or "3 to 5" in probe:
                    print("POLICY_LINE", line.strip())
