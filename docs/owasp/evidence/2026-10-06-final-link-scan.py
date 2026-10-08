"""Resolve docs/owasp citations and classify candidate secret assignments. Prints no values."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "owasp"
missing: list[str] = []
seen: set[str] = set()
for path in DOCS.rglob("*.md"):
    text = path.read_text(encoding="utf-8", errors="replace")
    for match in re.findall(r"`(docs/owasp/[^`\s]+)`", text):
        target = match.rstrip(".,)")
        if target in seen:
            continue
        seen.add(target)
        if not (ROOT / target).exists():
            missing.append(f"{path.relative_to(ROOT).as_posix()} -> {target}")
print("LINK_COUNT", len(seen))
print("MISSING", len(missing))
for item in missing:
    print("MISSING_LINK", item)

names = re.compile(
    r"(?i)\b(password|secret|api_key|token|private_key)\b\s*[:=]\s*(?P<value>\S+)"
)
candidate = subprocess.check_output(
    ["git", "diff", "--name-only", "HEAD"],
    cwd=ROOT,
    text=True,
).splitlines()
untracked = subprocess.check_output(
    ["git", "ls-files", "--others", "--exclude-standard", "docs/owasp", "tests/pipelines/test_runtime_data_path.py"],
    cwd=ROOT,
    text=True,
).splitlines()
paths = [ROOT / item for item in candidate + untracked if item]
print("SCAN_FILES", len(paths))
for path in paths:
    if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".zip", ".db"}:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print("BINARY", path.relative_to(ROOT).as_posix())
        continue
    for match in names.finditer(text):
        value = match.group("value").strip("'\"")
        kind = "empty" if value in {"", "none", "null", "changeme", "placeholder"} else "nonempty"
        print("ASSIGNMENT", path.relative_to(ROOT).as_posix(), kind)
