"""Isolated preservation tests for the local personal Admin operator command.

Temporary identity and ownership stores are selected by conftest before imports
touch TinyDB. Live services/api/data is not opened. Credentials are never printed.
"""

from __future__ import annotations

import getpass
import os
import warnings
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, select
from tinydb import Query
from tinydb.operations import delete as delete_field

from app.access.catalog import ROLE_RANK
from app.core.config import DEFAULT_TINYDB_PATH
from app.core.security import hash_password, verify_password
from app.db.database import get_engine
from app.db.tinydb import profiles_table, users_table
from app.rfp_models import RfpDepartmentAccount
from app.schemas.user import UserCreate, UserRole, UserUpdate
from app.services import profile_service, user_service
from app.services.personal_admin_provision import (
    APPROVED_DEPARTMENT_ID,
    APPROVED_EMAIL,
    APPROVED_ROLE,
    ProvisionAborted,
    ProvisionResult,
    provision_personal_admin,
    read_hidden_confirmed_password,
    require_persistent_local_identity,
    run_operator_command,
)

LIVE_DATA_MARKER = "services/api/data"
NEW_ACCOUNT_PASSWORD = "isolated-new-admin-8"
EXISTING_ACCOUNT_PASSWORD = "isolated-existing-9"
UNRELATED_EMAIL = "unrelated.operator@healthcore.example"
UNRELATED_PASSWORD = "isolated-unrelated-8"
BINDING_DEPARTMENT = "clinical_operations"
BINDING_OWNER_NAME = "preserve-ownership-row"


def _explode_if_password_requested() -> str:
    raise AssertionError("password reader must not run for an existing account")


def _assert_isolated_identity(identity_file: Path) -> None:
    tinydb_path = Path(os.environ["TINYDB_PATH"]).resolve()
    expected = identity_file.resolve()
    assert LIVE_DATA_MARKER not in tinydb_path.as_posix()
    assert tinydb_path == expected
    assert LIVE_DATA_MARKER not in expected.as_posix()


def _approved_rows() -> list[dict]:
    return list(users_table().search(Query().email == APPROVED_EMAIL))


def _canonical_approved_rows() -> list[dict]:
    return list(
        users_table().search(
            Query().email.test(
                lambda value: str(value or "").strip().lower() == APPROVED_EMAIL
            )
        )
    )


def _raw_row(email: str) -> dict:
    rows = list(users_table().search(Query().email == email))
    assert len(rows) == 1
    return rows[0]


def _bind_rfp_owner(user_id: str) -> None:
    SQLModel.metadata.create_all(get_engine())
    with Session(get_engine()) as session:
        session.add(
            RfpDepartmentAccount(
                department_id=BINDING_DEPARTMENT,
                user_id=user_id,
                owner_name=BINDING_OWNER_NAME,
            )
        )
        session.commit()


def _rfp_bindings(user_id: str) -> list[RfpDepartmentAccount]:
    with Session(get_engine()) as session:
        return list(
            session.exec(
                select(RfpDepartmentAccount).where(RfpDepartmentAccount.user_id == user_id)
            ).all()
        )


def test_new_account_receives_approved_role_department_and_hashed_password(
    isolated_identity_store: Path,
) -> None:
    _assert_isolated_identity(isolated_identity_store)
    result = provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=lambda: NEW_ACCOUNT_PASSWORD,
    )
    assert result == ProvisionResult(
        action="created",
        email=APPROVED_EMAIL,
        role=APPROVED_ROLE.value,
        department_id=APPROVED_DEPARTMENT_ID,
    )
    rows = _approved_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["role"] == "admin"
    assert row["role_id"] == "admin"
    assert row["department_id"] == "technology"
    assert ROLE_RANK[UserRole.admin] == 3
    stored_hash = row["hashed_password"]
    assert stored_hash != NEW_ACCOUNT_PASSWORD
    assert NEW_ACCOUNT_PASSWORD not in str(stored_hash)
    if not verify_password(NEW_ACCOUNT_PASSWORD, stored_hash):
        raise AssertionError("stored password was not hashed with existing hashing behavior")
    assert profile_service.get_profile_by_user_id(row["id"]) is None


def test_existing_account_upgrade_preserves_id_credential_profile_and_ownership(
    isolated_identity_store: Path,
) -> None:
    _assert_isolated_identity(isolated_identity_store)
    existing = user_service.create_user(
        UserCreate(email=APPROVED_EMAIL, password=EXISTING_ACCOUNT_PASSWORD),
        role=UserRole.employee,
        department_id="clinical_operations",
    )
    profile = profile_service.create_profile(user_id=existing.id, name="Existing Operator")
    _bind_rfp_owner(existing.id)
    unrelated = user_service.create_user(
        UserCreate(email=UNRELATED_EMAIL, password=UNRELATED_PASSWORD),
        role=UserRole.employee,
        department_id="patient_experience",
    )
    before_hash = existing.hashed_password
    before_unrelated = _raw_row(UNRELATED_EMAIL)

    result = provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=_explode_if_password_requested,
    )
    assert result.action == "updated"
    after_rows = _approved_rows()
    assert len(after_rows) == 1
    after = after_rows[0]
    assert after["id"] == existing.id
    if after["hashed_password"] != before_hash:
        raise AssertionError("existing credential hash changed")
    if not verify_password(EXISTING_ACCOUNT_PASSWORD, after["hashed_password"]):
        raise AssertionError("existing credential no longer matches original password")
    assert after["role"] == "admin"
    assert after["role_id"] == "admin"
    assert after["department_id"] == "technology"
    kept_profile = profile_service.get_profile_by_user_id(existing.id)
    assert kept_profile is not None
    assert kept_profile.id == profile.id
    assert kept_profile.name == "Existing Operator"
    bindings = _rfp_bindings(existing.id)
    assert len(bindings) == 1
    assert bindings[0].department_id == BINDING_DEPARTMENT
    assert bindings[0].user_id == existing.id
    assert bindings[0].owner_name == BINDING_OWNER_NAME
    after_unrelated = _raw_row(UNRELATED_EMAIL)
    assert after_unrelated == before_unrelated
    assert after_unrelated["id"] == unrelated.id


def test_existing_account_without_profile_does_not_create_one(
    isolated_identity_store: Path,
) -> None:
    existing = user_service.create_user(
        UserCreate(email=APPROVED_EMAIL, password=EXISTING_ACCOUNT_PASSWORD),
        role=UserRole.supervisor,
        department_id="revenue_cycle",
    )
    assert profile_service.get_profile_by_user_id(existing.id) is None
    provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=_explode_if_password_requested,
    )
    assert profile_service.get_profile_by_user_id(existing.id) is None
    assert len(profiles_table().all()) == 0


def test_repeated_execution_is_idempotent_and_does_not_duplicate(
    isolated_identity_store: Path,
) -> None:
    first = provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=lambda: NEW_ACCOUNT_PASSWORD,
    )
    row = _raw_row(APPROVED_EMAIL)
    before_id = row["id"]
    before_hash = row["hashed_password"]
    second = provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=_explode_if_password_requested,
    )
    third = provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=_explode_if_password_requested,
    )
    assert first.action == "created"
    assert second.action == "unchanged"
    assert third.action == "unchanged"
    rows = _approved_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == before_id
    if rows[0]["hashed_password"] != before_hash:
        raise AssertionError("repeated execution changed the credential hash")
    assert rows[0]["role"] == "admin"
    assert rows[0]["role_id"] == "admin"
    assert rows[0]["department_id"] == "technology"


def test_non_target_email_is_rejected_without_mutation(
    isolated_identity_store: Path,
) -> None:
    unrelated = user_service.create_user(
        UserCreate(email=UNRELATED_EMAIL, password=UNRELATED_PASSWORD),
        role=UserRole.employee,
        department_id="compliance",
    )
    before = _raw_row(UNRELATED_EMAIL)
    with pytest.raises(ProvisionAborted, match="approved local Admin email"):
        provision_personal_admin(
            UNRELATED_EMAIL,
            password_reader=lambda: NEW_ACCOUNT_PASSWORD,
        )
    assert _approved_rows() == []
    assert _raw_row(UNRELATED_EMAIL) == before
    assert _raw_row(UNRELATED_EMAIL)["id"] == unrelated.id


def test_duplicate_matching_identities_abort_without_choosing(
    isolated_identity_store: Path,
) -> None:
    users_table().insert(
        {
            "id": "dup-one",
            "email": APPROVED_EMAIL,
            "hashed_password": "placeholder-hash-one",
            "role": "employee",
            "department_id": "clinical_operations",
        }
    )
    users_table().insert(
        {
            "id": "dup-two",
            "email": APPROVED_EMAIL,
            "hashed_password": "placeholder-hash-two",
            "role": "supervisor",
            "department_id": "technology",
        }
    )
    before = _approved_rows()
    with pytest.raises(ProvisionAborted, match="Duplicate matching identities"):
        provision_personal_admin(
            APPROVED_EMAIL,
            password_reader=lambda: NEW_ACCOUNT_PASSWORD,
        )
    after = _approved_rows()
    assert after == before
    assert {row["id"] for row in after} == {"dup-one", "dup-two"}


def test_cancelled_password_input_does_not_create_an_account(
    isolated_identity_store: Path,
) -> None:
    def _cancel() -> str:
        raise KeyboardInterrupt

    with pytest.raises(ProvisionAborted, match="cancelled"):
        provision_personal_admin(APPROVED_EMAIL, password_reader=_cancel)
    assert _approved_rows() == []
    assert users_table().all() == []


def test_invalid_password_does_not_create_an_account(
    isolated_identity_store: Path,
) -> None:
    with pytest.raises(ProvisionAborted, match="existing validation"):
        provision_personal_admin(APPROVED_EMAIL, password_reader=lambda: "short")
    assert _approved_rows() == []
    assert users_table().all() == []


def test_single_case_variant_match_preserves_id_and_stored_email(
    isolated_identity_store: Path,
) -> None:
    stored_email = "CruzDaniel004@gmail.com"
    stored_hash = hash_password(EXISTING_ACCOUNT_PASSWORD)
    users_table().insert(
        {
            "id": "case-variant-one",
            "email": stored_email,
            "hashed_password": stored_hash,
            "is_active": True,
            "role": "employee",
            "role_id": "employee",
            "department_id": "clinical_operations",
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    result = provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=_explode_if_password_requested,
    )
    assert result.action == "updated"
    rows = _canonical_approved_rows()
    assert len(rows) == 1
    after = rows[0]
    assert after["id"] == "case-variant-one"
    assert after["email"] == stored_email
    if after["hashed_password"] != stored_hash:
        raise AssertionError("case-variant credential hash changed")
    assert after["role"] == "admin"
    assert after["role_id"] == "admin"
    assert after["department_id"] == "technology"
    assert _approved_rows() == []


def test_multiple_case_variant_identities_abort_without_mutation(
    isolated_identity_store: Path,
) -> None:
    users_table().insert(
        {
            "id": "case-dup-one",
            "email": "CruzDaniel004@gmail.com",
            "hashed_password": "placeholder-hash-one",
            "is_active": True,
            "role": "employee",
            "role_id": "employee",
            "department_id": "clinical_operations",
        }
    )
    users_table().insert(
        {
            "id": "case-dup-two",
            "email": "CRUZDANIEL004@GMAIL.COM",
            "hashed_password": "placeholder-hash-two",
            "is_active": True,
            "role": "supervisor",
            "role_id": "supervisor",
            "department_id": "technology",
        }
    )
    before = _canonical_approved_rows()
    with pytest.raises(ProvisionAborted, match="Duplicate matching identities"):
        provision_personal_admin(
            APPROVED_EMAIL,
            password_reader=lambda: NEW_ACCOUNT_PASSWORD,
        )
    after = _canonical_approved_rows()
    assert after == before
    assert {row["id"] for row in after} == {"case-dup-one", "case-dup-two"}
    assert {row["email"] for row in after} == {
        "CruzDaniel004@gmail.com",
        "CRUZDANIEL004@GMAIL.COM",
    }
    assert {row["role"] for row in after} == {"employee", "supervisor"}


def test_missing_role_id_uses_assignment_update_then_stays_unchanged(
    isolated_identity_store: Path,
) -> None:
    existing = user_service.create_user(
        UserCreate(email=APPROVED_EMAIL, password=EXISTING_ACCOUNT_PASSWORD),
        role=UserRole.admin,
        department_id=APPROVED_DEPARTMENT_ID,
    )
    profile = profile_service.create_profile(user_id=existing.id, name="Role Ref Operator")
    _bind_rfp_owner(existing.id)
    users_table().update(delete_field("role_id"), Query().id == existing.id)
    before = _raw_row(APPROVED_EMAIL)
    assert "role_id" not in before
    before_hash = before["hashed_password"]

    first = provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=_explode_if_password_requested,
    )
    second = provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=_explode_if_password_requested,
    )
    assert first.action == "updated"
    assert second.action == "unchanged"
    after = _raw_row(APPROVED_EMAIL)
    assert after["id"] == existing.id
    if after["hashed_password"] != before_hash:
        raise AssertionError("missing role_id repair changed the credential hash")
    assert after["role"] == "admin"
    assert after["role_id"] == "admin"
    assert after["department_id"] == "technology"
    kept_profile = profile_service.get_profile_by_user_id(existing.id)
    assert kept_profile is not None
    assert kept_profile.id == profile.id
    bindings = _rfp_bindings(existing.id)
    assert len(bindings) == 1
    assert bindings[0].user_id == existing.id
    assert bindings[0].owner_name == BINDING_OWNER_NAME


def test_inconsistent_role_id_uses_assignment_update_then_stays_unchanged(
    isolated_identity_store: Path,
) -> None:
    existing = user_service.create_user(
        UserCreate(email=APPROVED_EMAIL, password=EXISTING_ACCOUNT_PASSWORD),
        role=UserRole.admin,
        department_id=APPROVED_DEPARTMENT_ID,
    )
    assert profile_service.get_profile_by_user_id(existing.id) is None
    users_table().update({"role_id": "employee"}, Query().id == existing.id)
    before_hash = _raw_row(APPROVED_EMAIL)["hashed_password"]

    first = provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=_explode_if_password_requested,
    )
    second = provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=_explode_if_password_requested,
    )
    assert first.action == "updated"
    assert second.action == "unchanged"
    after = _raw_row(APPROVED_EMAIL)
    assert after["id"] == existing.id
    if after["hashed_password"] != before_hash:
        raise AssertionError("inconsistent role_id repair changed the credential hash")
    assert after["role"] == "admin"
    assert after["role_id"] == "admin"
    assert after["department_id"] == "technology"
    assert profile_service.get_profile_by_user_id(existing.id) is None
    assert len(_approved_rows()) == 1


def test_inactive_account_is_not_mutated(
    isolated_identity_store: Path,
) -> None:
    existing = user_service.create_user(
        UserCreate(email=APPROVED_EMAIL, password=EXISTING_ACCOUNT_PASSWORD),
        role=UserRole.employee,
        department_id="clinical_operations",
    )
    inactivated = user_service.update_user(existing.id, UserUpdate(is_active=False))
    assert inactivated is not None
    assert inactivated.is_active is False
    before = _raw_row(APPROVED_EMAIL)

    with pytest.raises(ProvisionAborted, match="inactive"):
        provision_personal_admin(
            APPROVED_EMAIL,
            password_reader=_explode_if_password_requested,
        )
    after = _raw_row(APPROVED_EMAIL)
    assert after == before
    assert after["id"] == existing.id
    assert after["is_active"] is False
    assert after["role"] == "employee"
    assert after["role_id"] == "employee"
    assert after["department_id"] == "clinical_operations"


def test_getpass_warning_fallback_aborts_before_persistence(
    isolated_identity_store: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def _fallback_getpass(prompt: str = "") -> str:
        warnings.warn("Can not control echo on the terminal.", getpass.GetPassWarning, stacklevel=2)
        return "echoed-must-not-persist-8"

    monkeypatch.setattr(
        "app.services.personal_admin_provision.getpass.getpass",
        _fallback_getpass,
    )
    with pytest.raises(ProvisionAborted, match="echoing input"):
        provision_personal_admin(
            APPROVED_EMAIL,
            password_reader=read_hidden_confirmed_password,
        )
    assert users_table().all() == []


def test_hidden_reader_aborts_when_stdin_is_not_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    def _must_not_echo(prompt: str = "") -> str:
        raise AssertionError("getpass must not run when hidden input is unavailable")

    monkeypatch.setattr("app.services.personal_admin_provision.getpass.getpass", _must_not_echo)
    with pytest.raises(ProvisionAborted, match="interactive terminal"):
        read_hidden_confirmed_password()


def test_cli_refuses_disposable_identity_overrides(
    isolated_identity_store: Path,
) -> None:
    with pytest.raises(ProvisionAborted, match="persistent local configuration"):
        run_operator_command(password_reader=lambda: NEW_ACCOUNT_PASSWORD)
    assert users_table().all() == []


def test_persistent_guard_rejects_sqlite_and_remote_targets() -> None:
    expected = DEFAULT_TINYDB_PATH
    with pytest.raises(ProvisionAborted, match="sqlite"):
        require_persistent_local_identity(
            expected,
            "sqlite:///C:/tmp/not-live.db",
            expected_tinydb=expected,
        )
    with pytest.raises(ProvisionAborted, match="loopback"):
        require_persistent_local_identity(
            expected,
            "postgresql://healthcore:unused@db.example.supabase.co:5432/healthcore_main",
            expected_tinydb=expected,
        )
    with pytest.raises(ProvisionAborted, match="verified local database"):
        require_persistent_local_identity(
            expected,
            "postgresql://healthcore:unused@127.0.0.1:54331/other_db",
            expected_tinydb=expected,
        )
    require_persistent_local_identity(
        expected,
        "postgresql://healthcore:unused@127.0.0.1:54331/healthcore_main",
        expected_tinydb=expected,
    )
