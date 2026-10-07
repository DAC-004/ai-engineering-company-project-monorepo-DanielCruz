#!/bin/bash
set -u
DEST=/var/backups/healthcore-rag-20261007T020559Z
runuser -u healthcore -- test -w "$DEST"
echo HEALTHCORE_BACKUP_WRITABLE $?
python3 - <<'PY'
from pathlib import Path
import difflib
dest = Path("/var/backups/healthcore-rag-20261007T020559Z")
before = (dest / "rag.py.before").read_bytes().replace(b"\r\n", b"\n").decode("utf-8").splitlines()
candidate = (dest / "rag.py.candidate").read_bytes().replace(b"\r\n", b"\n").decode("utf-8").splitlines()
diff = list(difflib.unified_diff(before, candidate, fromfile="deployed", tofile="candidate", lineterm="", n=2))
out = dest / "rag.py.diff"
out.write_text("\n".join(diff) + "\n", encoding="utf-8")
out.chmod(0o600)
removed = [line[1:] for line in diff if line.startswith("-") and not line.startswith("---")]
added = [line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")]
print("DIFF_LINES", len(diff))
print("ONLY_DEPLOYED", len(removed))
print("ONLY_CANDIDATE", len(added))
print("---REMOVED---")
for line in removed:
    print(line)
print("---ADDED---")
for line in added:
    print(line)
PY
