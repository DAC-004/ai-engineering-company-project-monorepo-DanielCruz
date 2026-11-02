"""Local operator provisioning for the approved personal Admin identity.

This is not a public route and is not the five-user platform seed. It reuses
user-service validation, hashing, and persistence. Lookup uses an exact-email
TinyDB search so get_user_by_email's normalization write is not a hidden
side effect, and list_users is never used.
"""

from __future__ import annotations

import argparse
import getpass
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from pydantic import ValidationError
from tinydb import Query

from app.access.catalog import DepartmentId, ROLE_RANK
from app.core.config import DEFAULT_TINYDB_PATH, get_settings
from app.db.database import _normalize_database_url
from app.db.tinydb import users_table
from app.schemas.user import UserCreate, UserRole, UserUpdate
from app.services import user_service

APPROVED_EMAIL = "cruzdaniel004@gmail.com"
APPROVED_ROLE = UserRole.admin
APPROVED_DEPARTMENT_ID = DepartmentId.technology.value
APPROVED_ROLE_RANK = ROLE_RANK[UserRole.admin]
PERSISTENT_DATABASE_NAME = "healthcore_main"
LOCAL_IDENTITY_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

PasswordReader = Callable[[], str]


class ProvisionAborted(Exception):
    """Operator command stopped without creating or merging accounts."""


@dataclass(frozen=True)
class ProvisionResult:
    action: str
    email: str
    role: str
    department_id: str


def require_persistent_local_identity(
    tinydb_path: Path | str,
    database_url: str,
    *,
    expected_tinydb: Path,
) -> None:
    """Refuse disposable-test overrides and remote databases. Does not open stores."""
    actual = Path(tinydb_path).expanduser().resolve()
    expected = Path(expected_tinydb).expanduser().resolve()
    if actual != expected:
        raise ProvisionAborted(
            "Refusing to run: identity path is not the persistent local configuration."
        )
    normalized = _normalize_database_url(database_url)
    parsed = urlsplit(normalized)
    scheme = (parsed.scheme or "").lower()
    if scheme.startswith("sqlite") or normalized.startswith("sqlite"):
        raise ProvisionAborted(
            "Refusing to run: sqlite is not the persistent local database."
        )
    host = (parsed.hostname or "").lower()
    if host not in LOCAL_IDENTITY_HOSTS:
        raise ProvisionAborted("Refusing to run: database host is not loopback.")
    db_name = (parsed.path or "").lstrip("/")
    if db_name != PERSISTENT_DATABASE_NAME:
        raise ProvisionAborted(
            "Refusing to run: database name is not the verified local database."
        )


def read_hidden_confirmed_password() -> str:
    """Collect a new-account password via getpass. Abort rather than accept echoed input.

    stdin.isatty is not sufficient: getpass issues GetPassWarning and falls back to
    visible _raw_input when it cannot disable echo. That warning is treated as an
    error so the fallback never runs. Cancellation remains EOFError/KeyboardInterrupt.
    """
    if not sys.stdin.isatty():
        raise ProvisionAborted(
            "Hidden password entry requires an interactive terminal. Aborting rather than echoing input."
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            first = getpass.getpass("New password: ")
            second = getpass.getpass("Confirm password: ")
    except getpass.GetPassWarning as exc:
        raise ProvisionAborted(
            "Hidden password entry is unavailable. Aborting rather than echoing input."
        ) from exc
    except (EOFError, KeyboardInterrupt) as exc:
        raise ProvisionAborted("Password entry cancelled.") from exc
    if first != second:
        raise ProvisionAborted("Passwords do not match.")
    return first


def _canonical_email(email: str) -> str:
    return str(email).strip().lower()


def _assert_approved_email(email: str) -> str:
    canonical = _canonical_email(email)
    if canonical != APPROVED_EMAIL:
        raise ProvisionAborted(
            "This command only provisions the approved local Admin email."
        )
    return canonical


def _matching_identity_rows(canonical: str) -> list[dict]:
    """Match the approved address using create/login lowercasing, including case variants.

    TinyDB equality is case-sensitive, so Query().email == canonical would miss a
    stored CruzDaniel004@gmail.com and create a duplicate. The test predicate does
    not print or return unrelated accounts.
    """
    return list(
        users_table().search(
            Query().email.test(
                lambda value: str(value or "").strip().lower() == canonical
            )
        )
    )


def _row_matches_approved_assignment(row: dict) -> bool:
    """Already-correct requires role, role_id, and department_id together."""
    role = str(row.get("role") or "").lower()
    role_id = str(row.get("role_id") or "").lower()
    return (
        role == APPROVED_ROLE.value
        and role_id == APPROVED_ROLE.value
        and row.get("department_id") == APPROVED_DEPARTMENT_ID
    )


def _row_is_inactive(row: dict) -> bool:
    """Application inactive state is the boolean is_active field used by /auth/login."""
    return row.get("is_active") is False


def _read_new_account_password(password_reader: PasswordReader) -> str:
    try:
        password = password_reader()
    except (EOFError, KeyboardInterrupt) as exc:
        raise ProvisionAborted("Password entry cancelled.") from exc
    try:
        UserCreate(email=APPROVED_EMAIL, password=password)
    except ValidationError as exc:
        raise ProvisionAborted(
            "Password or identity fields failed existing validation."
        ) from exc
    return password


def provision_personal_admin(
    email: str,
    *,
    password_reader: PasswordReader | None = None,
) -> ProvisionResult:
    """Create or upgrade only the approved identity. Repeated calls are idempotent."""
    canonical = _assert_approved_email(email)
    matches = _matching_identity_rows(canonical)
    if len(matches) > 1:
        raise ProvisionAborted(
            "Duplicate matching identities exist; refusing to choose or merge them."
        )
    if len(matches) == 1:
        row = matches[0]
        user_id = row.get("id")
        if not user_id:
            raise ProvisionAborted(
                "Matching identity is missing an id; refusing to rewrite it."
            )
        if _row_is_inactive(row):
            raise ProvisionAborted(
                "Matching identity is inactive; refusing to mutate or activate it."
            )
        if _row_matches_approved_assignment(row):
            return ProvisionResult(
                action="unchanged",
                email=canonical,
                role=APPROVED_ROLE.value,
                department_id=APPROVED_DEPARTMENT_ID,
            )
        # update_user hashes only when password is set. Role/role_id/department
        # update leaves hashed_password, stored email casing, is_active, profile
        # rows, and ownership bindings untouched.
        updated = user_service.update_user(
            str(user_id),
            UserUpdate(role=APPROVED_ROLE, department_id=APPROVED_DEPARTMENT_ID),
        )
        if updated is None:
            raise ProvisionAborted("Matching identity could not be updated.")
        return ProvisionResult(
            action="updated",
            email=canonical,
            role=updated.role.value,
            department_id=updated.department_id or APPROVED_DEPARTMENT_ID,
        )

    if password_reader is None:
        raise ProvisionAborted("A hidden password reader is required to create the account.")
    password = _read_new_account_password(password_reader)
    try:
        created = user_service.create_user(
            UserCreate(email=canonical, password=password),
            role=APPROVED_ROLE,
            department_id=APPROVED_DEPARTMENT_ID,
        )
    except ValueError as exc:
        raise ProvisionAborted(str(exc)) from exc
    return ProvisionResult(
        action="created",
        email=created.email,
        role=created.role.value,
        department_id=created.department_id or APPROVED_DEPARTMENT_ID,
    )


def run_operator_command(
    *,
    password_reader: PasswordReader | None = None,
) -> ProvisionResult:
    """CLI entry: persistent local config, then the approved-email provision path."""
    settings = get_settings()
    require_persistent_local_identity(
        settings.tinydb_path,
        settings.database_url,
        expected_tinydb=DEFAULT_TINYDB_PATH,
    )
    return provision_personal_admin(
        APPROVED_EMAIL,
        password_reader=password_reader or read_hidden_confirmed_password,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Provision the approved local personal Admin account. "
            "Passwords are never accepted as arguments."
        )
    )
    parser.parse_args(argv)
    try:
        result = run_operator_command()
    except ProvisionAborted as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"{result.action}: {result.email} "
        f"role={result.role} rank={APPROVED_ROLE_RANK} "
        f"department_id={result.department_id}"
    )
    return 0
