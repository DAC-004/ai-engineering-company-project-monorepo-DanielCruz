"""Disabled in-process ticket lookup.

The support-agent graph no longer calls this function. Ticket questions go
through ``app.agent.mcp_tickets``. The query model remains so callers can
describe an id read or a filter read without inventing a second contract.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.incident import IncidentPublic


class TicketLookupQuery(BaseModel):
    """Accepted lookup forms from the integrated incident API.

    ``incident_id`` is the GET ``/api/incidents/{incident_id}`` form.
    The four filters are the GET ``/api/incidents`` query form. The service
    has no combined id-plus-filter endpoint, so a non-blank id is a single
    read and the filters are used only when no id is present.
    """

    model_config = ConfigDict(extra="ignore")

    incident_id: str | None = None
    status: str | None = None
    origin: str | None = None
    branch: str | None = None
    category: str | None = None


def lookup_ticket(query: TicketLookupQuery) -> list[IncidentPublic]:
    """Refuse the old in-process read. ``query`` is unused on purpose."""
    del query
    raise RuntimeError(
        "Direct incident lookup is disabled. The support agent reads tickets through MCP."
    )
