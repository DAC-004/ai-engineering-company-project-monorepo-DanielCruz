#!/bin/bash
set -eu
STAMP=20261007T020559Z
DEST=/var/backups/healthcore-rag-${STAMP}
mkdir -p "$DEST"
chmod 700 "$DEST"
install -o root -g root -m 600 /opt/healthcore/app/data/pipelines/rag.py "$DEST/rag.py.before"
install -o root -g root -m 600 /tmp/hc-rag-candidate.py "$DEST/rag.py.candidate"
rm -f /tmp/hc-rag-candidate.py /tmp/hc-rag-inspect.sh
echo BACKUP_DIR "$DEST"
stat -c '%U %G %a %n' "$DEST" "$DEST/rag.py.before" "$DEST/rag.py.candidate"
sha256sum "$DEST/rag.py.before" "$DEST/rag.py.candidate"
runuser -u healthcore -- test -w "$DEST"; echo HEALTHCORE_BACKUP_WRITABLE $?
python3 - <<'PY'
from pathlib import Path
before = Path("/var/backups/healthcore-rag-20261007T020559Z/rag.py.before").read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
candidate = Path("/var/backups/healthcore-rag-20261007T020559Z/rag.py.candidate").read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
import difflib
diff = list(difflib.unified_diff(before.splitlines(), candidate.splitlines(), fromfile="deployed", tofile="candidate", lineterm="", n=1))
out = Path("/var/backups/healthcore-rag-20261007T020559Z/rag.py.diff")
out.write_text("\n".join(diff) + "\n", encoding="utf-8")
out.chmod(0o600)
print("DIFF_LINES", len(diff))
print("ONLY_DEPLOYED", sum(1 for line in diff if line.startswith("-") and not line.startswith("---")))
print("ONLY_CANDIDATE", sum(1 for line in diff if line.startswith("+") and not line.startswith("+++")))
PY
echo '---HUNKS---'
grep -n '^@@' /var/backups/healthcore-rag-20261007T020559Z/rag.py.diff
