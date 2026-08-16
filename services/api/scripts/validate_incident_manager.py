"""Runtime checks for the Centralized Incident Manager (TestClient)."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
PACKAGES_SHARED = REPO_ROOT / "packages" / "shared"
SCRIPTS_DIR = REPO_ROOT / "scripts"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(PACKAGES_SHARED))
sys.path.insert(0, str(SCRIPTS_DIR))

_tmpdir = tempfile.mkdtemp(prefix="incident-mgr-")
os.environ["SECRET_KEY"] = "validation-secret-key-32chars!!"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["TINYDB_PATH"] = str(Path(_tmpdir) / "auth.json")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from seed_incidents import seed  # noqa: E402
from shared.incident_analyzer import analyze_csv_path  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()

SAMPLE_CSV = REPO_ROOT / "scripts" / "incidents-healthcore.csv"
RAW_INCIDENT_ID = re.compile(r"HC-\d{6}")

EXPECTED_STATUS = {"open": 28, "resolved": 52, "discarded": 14, "in_progress": 0}
EXPECTED_CATEGORY = {
    "patient_experience": 61,
    "billing_error": 20,
    "other": 13,
}
EXPECTED_BRANCH = {
    "manchester_central": 15,
    "atlanta_midtown": 12,
    "savannah": 10,
    "austin_north": 9,
    "london_west": 9,
    "london_city": 9,
    "miami_brickell": 8,
    "tampa_bay": 7,
    "central": 7,
    "houston_med_center": 4,
    "orlando_east": 4,
}


def main() -> int:
    client = TestClient(app)
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"PASS  {name}")
        else:
            failures.append(name)
            print(f"FAIL  {name} {detail}")

    unauth = client.get("/api/incidents")
    check("List requires JWT", unauth.status_code == 401, str(unauth.status_code))

    register = client.post(
        "/users",
        json={"email": "ops@healthcore.com", "password": "SecurePass1!"},
    )
    check(
        "Register user for manager tests",
        register.status_code == 201,
        f"{register.status_code} {register.text}",
    )

    login = client.post(
        "/auth/login",
        data={"username": "ops@healthcore.com", "password": "SecurePass1!"},
    )
    check("Login for manager tests", login.status_code == 200, str(login.status_code))
    token = login.json().get("access_token", "")
    headers = {"Authorization": f"Bearer {token}"}

    empty_list = client.get("/api/incidents", headers=headers)
    check(
        "Empty list is []",
        empty_list.status_code == 200 and empty_list.json() == [],
        str(empty_list.json()),
    )

    empty_summary = client.get("/api/incidents/summary", headers=headers)
    summary_body = empty_summary.json() if empty_summary.status_code == 200 else {}
    check(
        "Empty summary is zero-filled",
        empty_summary.status_code == 200
        and summary_body.get("by_status", {}).get("open") == 0
        and summary_body.get("by_category", {}).get("other") == 0
        and summary_body.get("by_origin", {}).get("customer") == 0
        and summary_body.get("by_branch", {}).get("central") == 0,
        str(summary_body),
    )

    missing = client.post("/api/incidents", headers=headers, json={"origin": "customer"})
    check(
        "Missing create fields return 400",
        missing.status_code == 400
        and missing.json().get("field")
        and missing.json().get("message"),
        f"{missing.status_code} {missing.json()}",
    )

    invalid_cases = [
        ("category", "APPOINTMENT"),
        ("status", "OPEN"),
        ("origin", "clinic"),
        ("branch", "US-TX-01"),
    ]
    base_create = {
        "title": "Portal timeout at check-in",
        "description": "The patient portal failed during morning clinic hours.",
        "category": "it_system",
        "status": "open",
        "origin": "internal",
        "branch": "central",
    }
    for field, bad_value in invalid_cases:
        payload = {**base_create, field: bad_value}
        response = client.post("/api/incidents", headers=headers, json=payload)
        body = response.json()
        check(
            f"Invalid {field} returns 400 with field identity",
            response.status_code == 400
            and body.get("field") == field
            and isinstance(body.get("message"), str)
            and body["message"],
            f"{response.status_code} {body}",
        )

    created = client.post("/api/incidents", headers=headers, json=base_create)
    check("Create incident 200/201", created.status_code in {200, 201}, str(created.status_code))
    incident = created.json() if created.status_code in {200, 201} else {}
    incident_id = incident.get("id", "")
    created_at = incident.get("created_at")
    updated_at = incident.get("updated_at")
    check("Create assigns generated id", bool(incident_id))
    check("Create timestamps present", bool(created_at) and bool(updated_at))

    missing_id = client.get("/api/incidents/does-not-exist", headers=headers)
    check("Missing incident is 404", missing_id.status_code == 404, str(missing_id.status_code))

    bad_patch = client.patch(
        f"/api/incidents/{incident_id}/status",
        headers=headers,
        json={"status": "resolved"},
    )
    check(
        "Illegal open->resolved is 400",
        bad_patch.status_code == 400 and bad_patch.json().get("field") == "status",
        f"{bad_patch.status_code} {bad_patch.json()}",
    )

    missing_status = client.patch(
        f"/api/incidents/{incident_id}/status",
        headers=headers,
        json={},
    )
    check(
        "Missing PATCH status is 400 not 422",
        missing_status.status_code == 400 and missing_status.json().get("field"),
        f"{missing_status.status_code} {missing_status.json()}",
    )

    legal = client.patch(
        f"/api/incidents/{incident_id}/status",
        headers=headers,
        json={"status": "in_progress"},
    )
    legal_body = legal.json() if legal.status_code == 200 else {}
    check("Legal open->in_progress is 200", legal.status_code == 200, str(legal.status_code))
    check(
        "created_at unchanged after status update",
        bool(created_at)
        and bool(legal_body.get("created_at"))
        and legal_body.get("created_at") == created_at,
        f"{created_at} -> {legal_body.get('created_at')}",
    )
    check(
        "updated_at advanced after status update",
        bool(legal_body.get("updated_at")) and legal_body.get("updated_at") != updated_at,
        f"{updated_at} -> {legal_body.get('updated_at')}",
    )

    auth_422 = client.post("/users", json={"email": "not-an-email", "password": "password12"})
    check(
        "AUTH validation remains 422",
        auth_422.status_code == 422,
        str(auth_422.status_code),
    )

    analyze = client.post(
        "/api/incidents/analyze",
        headers=headers,
        files={"file": ("incidents-healthcore.csv", SAMPLE_CSV.read_bytes(), "text/csv")},
    )
    check(
        "Analyzer route still works",
        analyze.status_code == 200 and analyze.json().get("valid_count") == 94,
        f"{analyze.status_code} {analyze.json().get('valid_count')}",
    )

    first = seed(SAMPLE_CSV)
    second = seed(SAMPLE_CSV)
    check("First seed exits 0", first == 0, str(first))
    check("Second seed exits 0", second == 0, str(second))

    seeded_list = client.get("/api/incidents", headers=headers)
    seeded = seeded_list.json() if seeded_list.status_code == 200 else []
    # One operator-created incident plus 94 historical rows.
    check(
        "First seed yields 94 historical incidents",
        isinstance(seeded, list) and sum(1 for item in seeded if item.get("origin") == "customer") == 94,
        str(len(seeded)),
    )
    check(
        "Second seed inserts no extra customer incidents",
        sum(1 for item in seeded if item.get("origin") == "customer") == 94,
        str(len(seeded)),
    )

    seeded_summary = client.get("/api/incidents/summary", headers=headers).json()
    # Summary includes the extra operator-created it_system/internal/central/in_progress row.
    historical_status = dict(EXPECTED_STATUS)
    historical_status["in_progress"] = 1
    check(
        "Summary status totals include 94 historical plus one created",
        seeded_summary.get("by_status", {}).get("open") == 28
        and seeded_summary.get("by_status", {}).get("resolved") == 52
        and seeded_summary.get("by_status", {}).get("discarded") == 14
        and seeded_summary.get("by_status", {}).get("in_progress") == 1,
        str(seeded_summary.get("by_status")),
    )
    check(
        "Summary category totals match historical plus created it_system",
        seeded_summary.get("by_category", {}).get("patient_experience") == 61
        and seeded_summary.get("by_category", {}).get("billing_error") == 20
        and seeded_summary.get("by_category", {}).get("other") == 13
        and seeded_summary.get("by_category", {}).get("it_system") == 1,
        str(seeded_summary.get("by_category")),
    )
    for branch, count in EXPECTED_BRANCH.items():
        actual = seeded_summary.get("by_branch", {}).get(branch)
        expected = count + (1 if branch == "central" else 0)
        check(
            f"Summary branch {branch} == {expected}",
            actual == expected,
            str(actual),
        )

    db_text = Path(os.environ["TINYDB_PATH"]).read_text(encoding="utf-8")
    check("No raw CSV incident_id persisted", RAW_INCIDENT_ID.search(db_text) is None)
    check("No patient_id persisted", "patient_id" not in db_text and "PAT-" not in db_text)
    check("No satisfaction_score persisted", "satisfaction_score" not in db_text)

    analyzer = analyze_csv_path(SAMPLE_CSV)
    check("Analyzer re-export still reports 94 valid", analyzer.valid_count == 94)

    form_path = REPO_ROOT / "uis" / "incidents" / "components" / "IncidentRegistrationForm.tsx"
    form_text = form_path.read_text(encoding="utf-8")
    warning_before_title = form_text.find("phi-warning") < form_text.find("incident-title")
    warning_before_description = form_text.find("phi-warning") < form_text.find(
        "incident-description"
    )
    covers_free_text = "Title and description" in form_text
    check(
        "PHI warning precedes free-text fields in the form",
        warning_before_title and warning_before_description and covers_free_text,
    )

    if failures:
        print(f"\n{len(failures)} check(s) failed.")
        return 1
    print("\nAll incident-manager checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
