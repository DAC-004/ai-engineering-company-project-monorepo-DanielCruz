#!/bin/bash
set -u
# Read-only. Does not reload nginx, write a log, or change a unit.
echo NGINX_T_BEGIN
nginx -t
echo NGINX_T_EXIT $?
echo INCLUDES_BEGIN
nginx -T 2>/dev/null | grep -E '^[[:space:]]*include[[:space:]]' | sort -u
echo INCLUDES_END
python3 - << 'PY'
import glob
import os
import re
import stat as statmod
import subprocess
text = subprocess.check_output(["nginx", "-T"], stderr=subprocess.DEVNULL, text=True, errors="replace")
paths = set(re.findall(r"(?:include|ssl_certificate|ssl_certificate_key)\s+([^;]+);", text))
expanded = []
for raw in sorted(paths):
    token = raw.strip().strip('"').strip("'")
    matches = glob.glob(token) if any(ch in token for ch in "*?[") else [token]
    expanded.extend(matches or [token])
seen = []
for path in expanded:
    if path in seen:
        continue
    seen.append(path)
    if not os.path.lexists(path):
        print(f"MISSING {path}")
        continue
    st = os.lstat(path)
    mode = statmod.S_IMODE(st.st_mode)
    writable = subprocess.call(["runuser", "-u", "healthcore", "--", "test", "-w", path])
    kind = "link" if statmod.S_ISLNK(st.st_mode) else "file"
    print(f"SRC kind={kind} mode={mode:04o} uid={st.st_uid} healthcore_w={writable} path={path}")
PY
echo UNIT
systemctl show nginx -p FragmentPath -p DropInPaths --no-pager
FRAG=$(systemctl show nginx -p FragmentPath --value --no-pager)
if [ -n "$FRAG" ]; then
  runuser -u healthcore -- test -w "$FRAG"
  echo UNIT_W $?
  stat -c 'UNIT_STAT %U %G %a %n' "$FRAG"
fi
echo SERVICES
systemctl is-active healthcore-api healthcore-web nginx certbot-renew.timer
