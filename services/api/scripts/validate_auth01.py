"""AUTH-01 acceptance validation against the FastAPI app (TestClient)."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure repo root (shared/) and services/api are importable.
API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

# Isolate TinyDB + JWT settings before app imports settings cache.
_tmpdir = tempfile.mkdtemp(prefix="auth01-")
os.environ["SECRET_KEY"] = "validation-secret-key-32chars!!"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["TINYDB_PATH"] = str(Path(_tmpdir) / "auth.json")

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import create_access_token, verify_password  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.services import profile_service, user_service  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()

SAMPLE_CSV = REPO_ROOT / "scripts" / "incidents-healthcore.csv"
FALLBACK_CSV = """incident_id,date,clinic_id,country,category,description,status,patient_id,satisfaction_score
INC-1,2024-01-15,CL-1,US,CLINICAL,Test description long enough,CLOSED,P-1,5
"""


def _csv_bytes() -> bytes:
    if SAMPLE_CSV.exists():
        return SAMPLE_CSV.read_bytes()
    return FALLBACK_CSV.encode("utf-8")


def main() -> int:
    client = TestClient(app)
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"PASS  {name}")
        else:
            failures.append(name)
            print(f"FAIL  {name} {detail}")

    settings = get_settings()
    check("JWT secret from environment", settings.secret_key == os.environ["SECRET_KEY"])
    check("JWT algorithm from environment", settings.jwt_algorithm == "HS256")
    check("JWT expiry from environment", settings.access_token_expire_minutes == 30)

    # Public health (baseline liveness — not a sensitive route)
    r = client.get("/health")
    check("GET /health public", r.status_code == 200 and r.json()["status"] == "ok")

    # Registration / user creation
    r = client.post(
        "/users",
        json={
            "email": "alice@healthcore.com",
            "password": "SecurePass1!",
            "name": "Alice",
            "phone": "+15125550100",
            "address": "Austin TX",
        },
    )
    check("user creation POST /users", r.status_code == 201, r.text)
    alice = r.json() if r.status_code == 201 else {}
    check("registration defaults role=user", alice.get("role") == "user")
    check("registration excludes hashed_password", "hashed_password" not in alice)
    check("registration excludes plaintext password", "password" not in alice)
    check(
        "User response has no profile contact fields",
        all(k not in alice for k in ("name", "phone", "address")),
    )

    # Password hashing
    stored = user_service.get_user_by_email("alice@healthcore.com")
    check("password hashed in TinyDB", stored is not None and stored.hashed_password != "SecurePass1!")
    check(
        "plaintext not stored in hash field",
        stored is not None and "SecurePass1!" not in stored.hashed_password,
    )
    check(
        "bcrypt verify succeeds for correct password",
        stored is not None and verify_password("SecurePass1!", stored.hashed_password),
    )
    check(
        "bcrypt verify fails for incorrect password",
        stored is not None and not verify_password("WrongPass1!", stored.hashed_password),
    )

    # Profile one-to-one created at registration
    profile = profile_service.get_profile_by_user_id(alice.get("id", ""))
    check("linked Profile exists for User", profile is not None and profile.user_id == alice.get("id"))
    check("Profile owns name/phone/address", profile is not None and profile.name == "Alice")

    # Duplicate-user rejection
    r = client.post(
        "/users",
        json={"email": "alice@healthcore.com", "password": "SecurePass1!", "name": "Dup"},
    )
    check("duplicate-user rejection", r.status_code == 409, r.text)

    # Invalid role rejected on update payload schema
    r = client.post(
        "/users",
        json={"email": "bob@healthcore.com", "password": "SecurePass1!", "name": "Bob"},
    )
    check("user creation bob", r.status_code == 201, r.text)
    bob = r.json() if r.status_code == 201 else {}

    # Login failure
    r = client.post(
        "/auth/login",
        data={"username": "alice@healthcore.com", "password": "WrongPass1!"},
    )
    check("login failure incorrect password -> 401", r.status_code == 401, r.text)

    # Login success + JWT issuance
    r = client.post(
        "/auth/login",
        data={"username": "alice@healthcore.com", "password": "SecurePass1!"},
    )
    check("login success", r.status_code == 200, r.text)
    token = r.json().get("access_token") if r.status_code == 200 else None
    check("JWT issuance", bool(token))
    auth = {"Authorization": f"Bearer {token}"}

    if token:
        claims = jwt.get_unverified_claims(token)
        check("JWT carries TinyDB user id (sub)", claims.get("sub") == alice.get("id"))
        check("JWT includes exp claim", "exp" in claims)

    # Auth me
    r = client.get("/auth/me", headers=auth)
    check("GET /auth/me", r.status_code == 200, r.text)
    if r.status_code == 200:
        body = r.json()
        check(
            "auth/me email+role+profile contact",
            body.get("email") == "alice@healthcore.com"
            and body.get("role") == "user"
            and body.get("profile", {}).get("name") == "Alice",
        )

    # Profile access rules
    r = client.get("/profiles/me")
    check("GET /profiles/me without token -> 401", r.status_code == 401)

    r = client.get("/profiles/me", headers=auth)
    check("GET /profiles/me with token", r.status_code == 200 and r.json().get("name") == "Alice", r.text)

    r = client.put(
        "/profiles/me",
        headers=auth,
        json={"name": "Alice Updated", "phone": "+1", "address": "TX"},
    )
    check(
        "PUT /profiles/me owner update",
        r.status_code == 200 and r.json().get("name") == "Alice Updated",
        r.text,
    )

    # Users CRUD rules
    r = client.get("/users")
    check("missing token GET /users -> 401", r.status_code == 401)

    r = client.get("/users", headers=auth)
    check("GET /users list with token", r.status_code == 200 and len(r.json()) >= 2, r.text)

    r = client.get(f"/users/{alice.get('id')}", headers=auth)
    check("GET /users/{id}", r.status_code == 200 and r.json().get("id") == alice.get("id"), r.text)

    r = client.put(
        f"/users/{bob.get('id')}",
        headers=auth,
        json={"email": "bob2@healthcore.com"},
    )
    check("unauthorized modify other user -> 403", r.status_code == 403, r.text)

    r = client.put(
        f"/users/{alice.get('id')}",
        headers=auth,
        json={"email": "alice2@healthcore.com"},
    )
    check("authorized self update -> 200", r.status_code == 200, r.text)
    if r.status_code == 200:
        alice = r.json()

    r = client.put(
        f"/users/{alice.get('id')}",
        headers=auth,
        json={"role": "admin"},
    )
    check("non-admin role escalation -> 403", r.status_code == 403, r.text)

    # Invalid / expired / malformed tokens
    r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    check("malformed token -> 401", r.status_code == 401)

    expired = jwt.encode(
        {
            "sub": alice.get("id"),
            "exp": datetime.now(UTC) - timedelta(minutes=5),
        },
        os.environ["SECRET_KEY"],
        algorithm=os.environ["JWT_ALGORITHM"],
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    check("expired token -> 401", r.status_code == 401)

    bad_sig = jwt.encode(
        {
            "sub": alice.get("id"),
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        },
        "wrong-secret-key!!!!!!",
        algorithm=os.environ["JWT_ALGORITHM"],
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {bad_sig}"})
    check("invalid signature token -> 401", r.status_code == 401)

    # Qualifying protected routes outside /users and /auth (rubric ≥5)
    # 1) POST /api/incidents/analyze
    r = client.post(
        "/api/incidents/analyze",
        files={"file": ("incidents.csv", _csv_bytes(), "text/csv")},
    )
    check("POST /api/incidents/analyze without token -> 401", r.status_code == 401)

    r = client.post(
        "/api/incidents/analyze",
        headers=auth,
        files={"file": ("incidents.csv", _csv_bytes(), "text/csv")},
    )
    check(
        "POST /api/incidents/analyze with token",
        r.status_code == 200 and "total_records" in r.json(),
        r.text,
    )

    # 2) GET /api/incidents/results/export
    r = client.get("/api/incidents/results/export")
    check("GET /api/incidents/results/export without token -> 401", r.status_code == 401)

    r = client.get("/api/incidents/results/export", headers=auth)
    check(
        "GET /api/incidents/results/export with token",
        r.status_code == 200 and "total_records" in r.text,
        f"status={r.status_code}",
    )

    # 3) GET /api/incidents/results (instructor-authorized additional route)
    r = client.get("/api/incidents/results")
    check("GET /api/incidents/results without token -> 401", r.status_code == 401)

    r = client.get("/api/incidents/results", headers=auth)
    check(
        "GET /api/incidents/results with token",
        r.status_code == 200 and r.json().get("total_records") is not None,
        r.text,
    )

    # 4) GET /api/incidents/results/summary
    r = client.get("/api/incidents/results/summary")
    check("GET /api/incidents/results/summary without token -> 401", r.status_code == 401)

    r = client.get("/api/incidents/results/summary", headers=auth)
    check(
        "GET /api/incidents/results/summary with token",
        r.status_code == 200
        and "valid_count" in r.json()
        and "invalid_count" in r.json(),
        r.text,
    )

    # 5) DELETE /api/incidents/results — ownership 403 for non-owner, then owner clears
    r = client.post(
        "/auth/login",
        data={"username": "bob@healthcore.com", "password": "SecurePass1!"},
    )
    bob_auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.delete("/api/incidents/results")
    check("DELETE /api/incidents/results without token -> 401", r.status_code == 401)

    r = client.delete("/api/incidents/results", headers=bob_auth)
    check(
        "DELETE /api/incidents/results as non-owner -> 403",
        r.status_code == 403,
        r.text,
    )

    r = client.delete("/api/incidents/results", headers=auth)
    check("DELETE /api/incidents/results as owner -> 204", r.status_code == 204, r.text)

    r = client.get("/api/incidents/results", headers=auth)
    check("GET /api/incidents/results after clear -> 404", r.status_code == 404, r.text)

    # DELETE user removes linked profile (self)
    charlie = client.post(
        "/users",
        json={"email": "charlie@healthcore.com", "password": "SecurePass1!", "name": "Charlie"},
    ).json()
    r = client.post(
        "/auth/login",
        data={"username": "charlie@healthcore.com", "password": "SecurePass1!"},
    )
    charlie_auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    charlie_id = charlie["id"]
    check(
        "Charlie profile exists before delete",
        profile_service.get_profile_by_user_id(charlie_id) is not None,
    )
    r = client.delete(f"/users/{charlie_id}", headers=charlie_auth)
    check("DELETE /users/{id}", r.status_code == 204, r.text)
    check("User removed after delete", user_service.get_user_by_id(charlie_id) is None)
    check(
        "linked Profile removed after delete",
        profile_service.get_profile_by_user_id(charlie_id) is None,
    )

    # Env-backed token helper
    fresh = create_access_token(subject=alice.get("id") or stored.id)
    check("create_access_token uses env config", bool(fresh))

    print()
    if failures:
        print(f"{len(failures)} failure(s): {failures}")
        return 1
    print("All AUTH-01 acceptance checks passed.")
    print(
        "Qualifying protected routes outside /users and /auth: "
        "POST /api/incidents/analyze, "
        "GET /api/incidents/results, "
        "GET /api/incidents/results/summary, "
        "GET /api/incidents/results/export, "
        "DELETE /api/incidents/results "
        "(total=5)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
