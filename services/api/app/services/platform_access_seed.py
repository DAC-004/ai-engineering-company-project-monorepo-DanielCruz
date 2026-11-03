"""Seed exact specialized roles, departments, users, and internal reports.

Does not modify RFP demonstration accounts. Matching display names are not
treated as the same identities.
"""

from __future__ import annotations

import logging
import os

from tinydb import Query

from app.access.catalog import DEPARTMENTS, ROLES
from app.db.tinydb import departments_table, internal_reports_table, roles_table
from app.schemas.user import UserCreate, UserRole
from app.services import profile_service, user_service
from app.services.internal_report_service import create_report, list_reports

logger = logging.getLogger(__name__)

USERS_SEED: tuple[dict[str, str], ...] = (
    {
        "email": "marcus.clinical@healthcore.example",
        "role": "supervisor",
        "department": "clinical_operations",
        "name": "Dr. Marcus Reid",
    },
    {
        "email": "tom.billing@healthcore.example",
        "role": "supervisor",
        "department": "revenue_cycle",
        "name": "Tom Callahan",
    },
    {
        "email": "priya.access@healthcore.example",
        "role": "employee",
        "department": "patient_experience",
        "name": "Priya Nair",
    },
    {
        "email": "claire.compliance@healthcore.example",
        "role": "employee",
        "department": "compliance",
        "name": "Claire Whitfield",
    },
    {
        "email": "james.admin@healthcore.example",
        "role": "admin",
        "department": "technology",
        "name": "James Osei",
    },
)

REPORTS_SEED: tuple[dict[str, str], ...] = (
    {
        "department": "clinical_operations",
        "owner_email": "marcus.clinical@healthcore.example",
        "title": "Austin North — documentation time spike",
        "body": "Average documentation minutes per encounter up 12% week over week. No patient identifiers.",
    },
    {
        "department": "revenue_cycle",
        "owner_email": "tom.billing@healthcore.example",
        "title": "US denial rate — coding mismatch cluster",
        "body": "14% denial rate driven by three CPT mismatch patterns. No member IDs in this note.",
    },
)


def seed_password() -> str | None:
    value = os.environ.get("PLATFORM_SEED_PASSWORD", "").strip()
    if len(value) < 8:
        return None
    return value


def ensure_roles_and_departments() -> None:
    roles = roles_table()
    departments = departments_table()
    for spec in ROLES:
        code = str(spec["code"])
        if roles.get(Query().code == code) is None:
            roles.insert(
                {"id": code, "code": code, "name": spec["name"], "rank": spec["rank"]}
            )
    for spec in DEPARTMENTS:
        code = spec["id"]
        if departments.get(Query().id == code) is None:
            departments.insert({"id": code, "code": code, "name": spec["name"]})


def ensure_platform_access_seed() -> None:
    """Insert catalog rows always; insert the five users when a seed password is set."""
    ensure_roles_and_departments()
    password = seed_password()
    if password is None:
        logger.info("platform_access_seed users=skipped reason=password_not_configured")
        return
    for spec in USERS_SEED:
        existing = user_service.get_user_by_email(spec["email"])
        if existing is None:
            user = user_service.create_user(
                UserCreate(email=spec["email"], password=password, name=spec["name"]),
                role=UserRole(spec["role"]),
                department_id=spec["department"],
            )
            profile_service.create_profile(user_id=user.id, name=spec["name"])
        if existing is not None and profile_service.get_profile_by_user_id(existing.id) is None:
            profile_service.create_profile(user_id=existing.id, name=spec["name"])
    existing_reports = list_reports()
    titles = {row.title for row in existing_reports}
    for spec in REPORTS_SEED:
        if spec["title"] in titles:
            continue
        owner = user_service.get_user_by_email(spec["owner_email"])
        if owner is None:
            continue
        create_report(
            department_id=spec["department"],
            title=spec["title"],
            body=spec["body"],
            created_by=owner.id,
        )
