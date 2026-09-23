"""Read-only ticket lookup over the integrated incident service.

The graph node calls ``lookup_ticket`` only after ``caller_is_authenticated``
is true. This function itself does not accept a token. ``get_incident`` and
``list_incidents`` do not read a token either. The HTTP routes in
``app.routers.incident_manager`` do require ``get_current_user``. This
lookup does not invent a service token and does not read ``SECRET_KEY``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.incident import IncidentPublic
from app.services import incident_service


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
    """Return live incident rows. This function does not create or update."""
    incident_id = (query.incident_id or "").strip()
    if incident_id:
        return [incident_service.get_incident(incident_id)]
    return incident_service.list_incidents(
        status=query.status,
        origin=query.origin,
        branch=query.branch,
        category=query.category,
    )
