#!/bin/bash
set -u
set -a
# shellcheck disable=SC1091
source /etc/healthcore/healthcore.env
set +a
export PYTHONPATH=/opt/healthcore/app:/opt/healthcore/app/services/api
/opt/healthcore/app/services/api/.venv/bin/python - "$@" <<'PY'
import sys

from app.services import profile_service, user_service

removed_users = 0
removed_profiles = 0
for email in sys.argv[1:]:
    user = user_service.get_user_by_email(email)
    if user is None:
        print("PROBE_SKIP", email)
        continue
    removed_profiles += int(profile_service.delete_profile_for_user(user.id))
    removed_users += int(user_service.delete_user(user.id))
    print("PROBE_REMOVED", email)
print("PROBE_USERS_REMOVED", removed_users)
print("PROBE_PROFILES_REMOVED", removed_profiles)
PY
