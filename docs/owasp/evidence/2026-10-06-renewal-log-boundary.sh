#!/bin/bash
set -u
echo BEFORE_DATE "$(date -u)"
echo BEFORE_ID "$(id healthcore)"
echo BEFORE_GROUPS "$(id -nG healthcore)"
sha256sum /etc/iptables/rules.v4 /etc/iptables/rules.v6 /etc/nginx/sites-available/healthcore.conf /etc/letsencrypt/renewal/150.136.171.59.conf /etc/systemd/system/certbot-renew.service /etc/systemd/system/certbot-renew.timer > /tmp/healthcore-boundary-before.sha
sshd -T | grep -i permitrootlogin
openssl x509 -in /etc/letsencrypt/live/150.136.171.59/fullchain.pem -noout -issuer -dates -ext subjectAltName
install -d -o root -g root -m 755 /var/log/healthcore-renewal
if [ -f /var/log/healthcore/certbot-deploy-hook.log ]; then
  mv /var/log/healthcore/certbot-deploy-hook.log /var/log/healthcore-renewal/certbot-deploy-hook.log
fi
chown root:root /var/log/healthcore-renewal /var/log/healthcore-renewal/certbot-deploy-hook.log
chmod 755 /var/log/healthcore-renewal
chmod 644 /var/log/healthcore-renewal/certbot-deploy-hook.log
install -o root -g root -m 755 /tmp/healthcore-nginx-hook /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx
echo HOOK_LOG_LINE "$(grep '^LOG=' /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx)"
stat -c '%U %G %a %n' /var/log /var/log/healthcore /var/log/healthcore-renewal /var/log/healthcore-renewal/certbot-deploy-hook.log /etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx
runuser -u healthcore -- /usr/bin/test -w /var/log/healthcore-renewal
echo DIR_W $?
runuser -u healthcore -- /usr/bin/test -w /var/log/healthcore-renewal/certbot-deploy-hook.log
echo FILE_W $?
runuser -u healthcore -- /bin/mv /var/log/healthcore-renewal/certbot-deploy-hook.log /var/log/healthcore-renewal/certbot-deploy-hook.log.replaced
echo MV_FILE $?
runuser -u healthcore -- /bin/mv /var/log/healthcore-renewal /var/log/healthcore-renewal.replaced
echo MV_DIR $?
test -f /var/log/healthcore-renewal/certbot-deploy-hook.log
echo FILE_STILL_PRESENT $?
test ! -e /var/log/healthcore-renewal.replaced
echo DIR_NOT_REPLACED $?
test ! -e /var/log/healthcore-renewal/certbot-deploy-hook.log.replaced
echo FILE_NOT_REPLACED $?
test ! -e /var/log/healthcore/certbot-deploy-hook.log
echo OLD_PATH_ABSENT $?
before=$(wc -l < /var/log/healthcore-renewal/certbot-deploy-hook.log)
/etc/letsencrypt/renewal-hooks/deploy/healthcore-nginx
echo HOOK_EXIT $?
echo NEW_MARKERS
tail -n +"$((before + 1))" /var/log/healthcore-renewal/certbot-deploy-hook.log | grep -E 'DEPLOY_HOOK_|NGINX_TEST_EXIT|NGINX_RELOAD_EXIT|^[A-Z][a-z]{2} '
runuser -u healthcore -- /usr/bin/test -w /var/log/healthcore-renewal
echo DIR_W_AFTER $?
runuser -u healthcore -- /usr/bin/test -w /var/log/healthcore-renewal/certbot-deploy-hook.log
echo FILE_W_AFTER $?
echo AFTER_ACTIVE
systemctl is-active healthcore-api
systemctl is-active healthcore-web
systemctl is-active nginx
systemctl is-active ssh
systemctl is-active certbot-renew.timer
echo AFTER_SSHD
sshd -T | grep -i permitrootlogin
echo AFTER_CERT
openssl x509 -in /etc/letsencrypt/live/150.136.171.59/fullchain.pem -noout -issuer -dates -ext subjectAltName
echo AFTER_TIMER
systemctl show certbot-renew.timer -p ActiveState -p UnitFileState -p NextElapseUSecRealtime --no-pager
echo AFTER_SERVICE
systemctl cat certbot-renew.service
sha256sum /etc/iptables/rules.v4 /etc/iptables/rules.v6 /etc/nginx/sites-available/healthcore.conf /etc/letsencrypt/renewal/150.136.171.59.conf /etc/systemd/system/certbot-renew.service /etc/systemd/system/certbot-renew.timer > /tmp/healthcore-boundary-after.sha
echo SHA_MATCH
cmp /tmp/healthcore-boundary-before.sha /tmp/healthcore-boundary-after.sha && echo UNCHANGED || echo CHANGED
rm -f /tmp/healthcore-boundary-before.sha /tmp/healthcore-boundary-after.sha /tmp/healthcore-nginx-hook
echo AFTER_DATE "$(date -u)"
