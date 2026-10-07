#!/bin/bash
set -u
for p in /etc/nginx /etc/nginx/conf.d /etc/nginx/sites-available /etc/nginx/sites-enabled /etc/nginx/modules-enabled /etc/letsencrypt /etc/letsencrypt/live /etc/letsencrypt/live/150.136.171.59 /usr/lib/systemd/system /etc/systemd/system; do
  if [ -e "$p" ]; then
    runuser -u healthcore -- test -w "$p"
    echo "DIR_W $? $(stat -c '%U %G %a %F' "$p") $p"
  else
    echo "ABSENT $p"
  fi
done
for p in /etc/letsencrypt/live/150.136.171.59/fullchain.pem /etc/letsencrypt/live/150.136.171.59/privkey.pem /etc/nginx/sites-enabled/healthcore.conf; do
  target=$(readlink -f "$p")
  runuser -u healthcore -- test -w "$target"
  echo "TARGET_W $? $(stat -c '%U %G %a %F' "$target") $p"
done
