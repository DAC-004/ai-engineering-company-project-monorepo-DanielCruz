"""Narrow automated identity. Narrower than any human role on the team."""

from __future__ import annotations

AGENT_ACTOR_TYPE = "automated_process"
AGENT_ACTOR_ID = "onboarding-orchestrator"

AGENT_PERMISSIONS: frozenset[str] = frozenset(
    {
        "read_official_onboarding_material",
        "record_comprehension_result",
        "request_human_decision",
        "record_safe_receipt_flags",
        "enqueue_internal_notice",
        "propose_gated_access",
    }
)

FORBIDDEN_AGENT_ACTIONS: frozenset[str] = frozenset(
    {
        "approve_stage",
        "change_user_permissions",
        "provision_real_accounts",
        "read_payroll_or_background_contents",
        "bypass_compliance",
        "send_external_communications",
    }
)


def actor_payload() -> dict[str, str]:
    return {"actor_type": AGENT_ACTOR_TYPE, "actor_id": AGENT_ACTOR_ID}
