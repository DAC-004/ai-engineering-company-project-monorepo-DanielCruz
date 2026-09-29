"""Fixed HealthCore departments for Part 1 intake.

Contacts come from the company context. They are not read out of the RFP,
so a model cannot replace them with a name from the document.
"""

from __future__ import annotations

DEPARTMENT_IDS: tuple[str, ...] = ("revenue", "clinical", "compliance")

DEPARTMENTS: dict[str, dict[str, str]] = {
    "revenue": {
        "department_name": "Revenue Cycle",
        "contact_name": "Tom Callahan",
        "focus": "Financial terms, currency, and payment structure. Owns the ticket.",
    },
    "clinical": {
        "department_name": "Clinical Operations",
        "contact_name": "Dr. Marcus Reid",
        "focus": "Clinic and staffing feasibility.",
    },
    "compliance": {
        "department_name": "Compliance and Data Governance",
        "contact_name": "Claire Whitfield",
        "focus": "Regulatory review and country-appropriate BAA or DPA requirements.",
    },
}


def country_rule(client_country: str | None) -> str:
    """State the currency and agreement required by the extracted country.

    The country value has to come from the document. This function does not
    choose a country. It only applies the HealthCore rule once that value exists.
    """
    if client_country == "US":
        return "US client: quote in USD and include a Business Associate Agreement."
    if client_country == "UK":
        return "UK client: quote in GBP and include a Data Processing Agreement referencing UK GDPR."
    return "Client country was not stated. Currency and the BAA or DPA choice stay unresolved."
