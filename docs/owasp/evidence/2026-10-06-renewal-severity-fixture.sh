#!/bin/bash
set -u
# Isolated mechanism check. Does not touch production logs, hooks, or services.
BASE=/tmp/hc-sev-fixture
rm -rf "$BASE"
mkdir -p "$BASE/vuln" "$BASE/sink" "$BASE/fixed"
chmod 755 "$BASE" "$BASE/sink" "$BASE/fixed"
chown healthcore:healthcore "$BASE/vuln"
chmod 750 "$BASE/vuln"
install -o root -g root -m 644 /dev/null "$BASE/vuln/app.log"
install -o root -g root -m 644 /dev/null "$BASE/sink/sink.txt"
install -o root -g root -m 644 /dev/null "$BASE/fixed/app.log"
chmod 755 "$BASE/fixed"
echo VULN_DIR "$(stat -c '%U %G %a' "$BASE/vuln")"
echo VULN_FILE "$(stat -c '%U %G %a' "$BASE/vuln/app.log")"
runuser -u healthcore -- /bin/rm -f "$BASE/vuln/app.log"
echo RM_EXIT $?
runuser -u healthcore -- /bin/ln -s "$BASE/sink/sink.txt" "$BASE/vuln/app.log"
echo LINK_EXIT $?
if [ -L "$BASE/vuln/app.log" ]; then echo SYMLINK_PRESENT 1; else echo SYMLINK_PRESENT 0; fi
# Root append uses a fixed line, matching the hook's lack of attacker-chosen text.
echo FIXED_HOOK_LINE >> "$BASE/vuln/app.log"
if grep -qx FIXED_HOOK_LINE "$BASE/sink/sink.txt"; then echo SINK_HAS_FIXED 1; else echo SINK_HAS_FIXED 0; fi
if grep -q ATTACKER_CHOSEN "$BASE/sink/sink.txt"; then echo SINK_HAS_ATTACKER_TEXT 1; else echo SINK_HAS_ATTACKER_TEXT 0; fi
echo SINK_OWNER "$(stat -c '%U %G %a' "$BASE/sink/sink.txt")"
runuser -u healthcore -- /bin/mv "$BASE/fixed/app.log" "$BASE/fixed/app.log.replaced"
echo FIXED_MV_EXIT $?
test -f "$BASE/fixed/app.log"
echo FIXED_FILE_PRESENT $?
if [ -e /root/.ssh/authorized_keys ]; then echo ROOT_KEYS_PRESENT 1; stat -c '%U %G %a' /root/.ssh/authorized_keys; else echo ROOT_KEYS_PRESENT 0; fi
rm -rf "$BASE"
test ! -e "$BASE"
echo FIXTURE_REMOVED $?
