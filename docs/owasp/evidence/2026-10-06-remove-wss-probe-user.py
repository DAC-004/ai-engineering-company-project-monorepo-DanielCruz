"""Remove the synthetic WebSocket account created by the public check."""

from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path("/opt/healthcore/app")
sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(APP_ROOT / "services" / "api"))

from app.services import profile_service, user_service

EMAIL = "audit.wss.20261006@example.com"


def main() -> int:
    user = user_service.get_user_by_email(EMAIL)
    if user is None:
        print("PROBE_USERS_REMOVED", 0)
        print("PROBE_PROFILES_REMOVED", 0)
        return 0
    profile_removed = profile_service.delete_profile_for_user(user.id)
    user_removed = user_service.delete_user(user.id)
    print("PROBE_USERS_REMOVED", int(user_removed))
    print("PROBE_PROFILES_REMOVED", int(profile_removed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
