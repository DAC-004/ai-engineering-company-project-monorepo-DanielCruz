"""Patient-information access is blocked until stage 4 is approved."""

from __future__ import annotations

from dataclasses import dataclass

from agents.onboarding_orchestrator.state import PATIENT_INFORMATION_SYSTEMS


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    security_event: bool
    notify_claire: bool
    reason: str
    system_id: str


def evaluate_access_request(system_id: str, *, compliance_approved: bool) -> AccessDecision:
    patient_system = system_id in PATIENT_INFORMATION_SYSTEMS
    if patient_system and not compliance_approved:
        return AccessDecision(
            allowed=False,
            security_event=True,
            notify_claire=True,
            reason="patient_system_before_compliance_approval",
            system_id=system_id,
        )
    if not patient_system and system_id not in {"jira", "notion", "slack", "microsoft365"}:
        return AccessDecision(
            allowed=False,
            security_event=False,
            notify_claire=False,
            reason="unknown_system",
            system_id=system_id,
        )
    return AccessDecision(
        allowed=True,
        security_event=False,
        notify_claire=False,
        reason="accepted_request",
        system_id=system_id,
    )
