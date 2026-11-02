"""Isolated preservation regressions for historical RFP demonstration accounts.

Invokes ensure_demonstration_accounts directly. Does not start an HTTP server
or write live identity stores.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlmodel import Session, select

from app.core.security import verify_password
from app.db.database import get_engine, init_databases
from app.rfp_models import RfpDepartmentAccount
from app.schemas.user import UserCreate, UserRole
from app.services import user_service
from app.services.platform_access_seed import USERS_SEED
from app.services.rfp_demonstration_accounts import (
    DEMONSTRATION_ACCOUNTS,
    demonstration_password,
    ensure_demonstration_accounts,
)

EXISTING_PASSWORD = "existing-demo-password-1"
DEMO_PASSWORD = "rfp-preserve-test-password"
LIVE_DATA_MARKER = "services/api/data"


def _assert_isolated_storage(tmp_path: Path) -> None:
    """Fail before provisioning if identity or RFP storage still points at live data."""
    tinydb_path = Path(os.environ["TINYDB_PATH"]).resolve()
    tmp_root = tmp_path.resolve()
    assert LIVE_DATA_MARKER not in tinydb_path.as_posix()
    assert tinydb_path == tmp_root / "auth.json" or tmp_root in tinydb_path.parents
    database_url = os.environ["DATABASE_URL"]
    assert database_url.startswith("sqlite:///")
    sqlite_path = Path(database_url.removeprefix("sqlite:///")).resolve()
    assert LIVE_DATA_MARKER not in sqlite_path.as_posix()
    assert tmp_root in sqlite_path.parents or sqlite_path.parent == tmp_root


def _provision() -> None:
    os.environ["RFP_DEMONSTRATION_PASSWORD"] = DEMO_PASSWORD
    init_databases()
    with Session(get_engine()) as session:
        ensure_demonstration_accounts(session)


def _snapshot_user(email: str) -> dict[str, object]:
    user = user_service.get_user_by_email(email)
    assert user is not None
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "department_id": user.department_id,
        "hashed_password": user.hashed_password,
    }


def _assert_credentials_preserved(before: dict[str, object], after: dict[str, object]) -> None:
    if before["hashed_password"] != after["hashed_password"]:
        raise AssertionError("stored credential changed")
    if not verify_password(EXISTING_PASSWORD, str(after["hashed_password"])):
        raise AssertionError("stored credential no longer matches original password")
    if verify_password(demonstration_password(), str(after["hashed_password"])):
        raise AssertionError("stored credential was replaced with the demonstration password")


def _assert_assignment_preserved(before: dict[str, object], after: dict[str, object]) -> None:
    assert after["id"] == before["id"]
    assert after["email"] == before["email"]
    assert after["role"] == before["role"]
    assert after["department_id"] == before["department_id"]
    _assert_credentials_preserved(before, after)


def _bindings() -> dict[str, RfpDepartmentAccount]:
    with Session(get_engine()) as session:
        rows = session.exec(select(RfpDepartmentAccount)).all()
        return {row.department_id: row for row in rows}


def test_existing_demonstration_accounts_keep_explicit_assignments(tmp_path: Path) -> None:
    _assert_isolated_storage(tmp_path)
    init_databases()
    created = user_service.create_user(
        UserCreate(email="rfp.revenue.demonstration@healthcore.com", password=EXISTING_PASSWORD),
        role=UserRole.employee,
        department_id="technology",
    )
    with Session(get_engine()) as session:
        session.add(
            RfpDepartmentAccount(
                department_id="revenue",
                user_id=created.id,
                owner_name="Existing Revenue Owner",
            )
        )
        session.commit()
    before = _snapshot_user(created.email)

    _provision()

    after = _snapshot_user(created.email)
    _assert_assignment_preserved(before, after)
    assert after["role"] == UserRole.employee
    assert after["department_id"] == "technology"
    binding = _bindings()["revenue"]
    assert binding.user_id == created.id
    assert binding.owner_name == "Existing Revenue Owner"


def test_repeated_provisioning_retains_ids_credentials_assignments_and_bindings(
    tmp_path: Path,
) -> None:
    _assert_isolated_storage(tmp_path)
    init_databases()
    created = user_service.create_user(
        UserCreate(email="rfp.clinical.demonstration@healthcore.com", password=EXISTING_PASSWORD),
        role=UserRole.admin,
        department_id="people_workforce",
    )
    with Session(get_engine()) as session:
        session.add(
            RfpDepartmentAccount(
                department_id="clinical",
                user_id=created.id,
                owner_name="Existing Clinical Owner",
            )
        )
        session.commit()
    first = _snapshot_user(created.email)

    _provision()
    second = _snapshot_user(created.email)
    _assert_assignment_preserved(first, second)
    first_binding = _bindings()["clinical"]

    _provision()
    third = _snapshot_user(created.email)
    _assert_assignment_preserved(second, third)
    second_binding = _bindings()["clinical"]
    assert second_binding.user_id == first_binding.user_id == created.id
    assert second_binding.owner_name == first_binding.owner_name == "Existing Clinical Owner"


def test_specialized_seed_identities_are_not_repurposed_as_demonstration_accounts(
    tmp_path: Path,
) -> None:
    _assert_isolated_storage(tmp_path)
    init_databases()
    specialized = {}
    for spec in USERS_SEED:
        specialized[spec["email"]] = user_service.create_user(
            UserCreate(email=spec["email"], password=EXISTING_PASSWORD, name=spec["name"]),
            role=UserRole(spec["role"]),
            department_id=spec["department"],
        )
    before = {email: _snapshot_user(email) for email in specialized}

    _provision()

    for email, snapshot in before.items():
        _assert_assignment_preserved(snapshot, _snapshot_user(email))
    specialized_ids = {user.id for user in specialized.values()}
    demo_emails = {spec["email"] for spec in DEMONSTRATION_ACCOUNTS}
    assert specialized_ids.isdisjoint(
        {user_service.get_user_by_email(email).id for email in demo_emails}
    )
    for spec in DEMONSTRATION_ACCOUNTS:
        binding = _bindings()[spec["department_id"]]
        assert binding.user_id not in specialized_ids
        demo_user = user_service.get_user_by_email(spec["email"])
        assert demo_user is not None
        assert demo_user.id == binding.user_id
        assert demo_user.email not in specialized


def test_missing_demonstration_account_is_still_created(tmp_path: Path) -> None:
    _assert_isolated_storage(tmp_path)
    assert user_service.get_user_by_email("rfp.compliance.demonstration@healthcore.com") is None

    _provision()

    created = user_service.get_user_by_email("rfp.compliance.demonstration@healthcore.com")
    assert created is not None
    assert created.role == UserRole.supervisor
    assert created.department_id == "compliance"
    if not verify_password(demonstration_password(), created.hashed_password):
        raise AssertionError("missing-account credential does not match the demonstration password")
    binding = _bindings()["compliance"]
    assert binding.user_id == created.id
    assert binding.owner_name == "Claire Whitfield"
