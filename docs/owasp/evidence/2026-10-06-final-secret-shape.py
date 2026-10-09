"""Classify candidate assignment values by shape. Does not print the values."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
names = re.compile(
    r"(?i)\b(?P<name>password|secret|api_key|token|private_key)\b\s*[:=]\s*(?P<value>\S+)"
)
candidate = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True).splitlines()
untracked = subprocess.check_output(
    [
        "git",
        "ls-files",
        "--others",
        "--exclude-standard",
        "docs/owasp",
        "tests/pipelines/test_runtime_data_path.py",
    ],
    cwd=ROOT,
    text=True,
).splitlines()
counts: dict[tuple[str, str], int] = {}
for item in candidate + untracked:
    path = ROOT / item
    if not path.is_file():
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for match in names.finditer(text):
        value = match.group("value").strip("'\"`,")
        if value in {"", "none", "null"}:
            shape = "empty"
        elif value.startswith(("os.", "secrets.", "settings.", "str(", "json.", "event.", "data.", "body.", "payload.")):
            shape = "expression"
        elif value in {"token", "password", "secret", "access_token"}:
            shape = "identifier"
        elif "example" in value.lower() or value.endswith(")"):
            shape = "expression-or-example"
        else:
            shape = f"literal-len-{len(value)}"
        key = (path.relative_to(ROOT).as_posix(), match.group("name").lower(), shape)
        counts[key] = counts.get(key, 0) + 1
for (path, name, shape), count in sorted(counts.items()):
    print(f"{path} {name} {shape} {count}")
