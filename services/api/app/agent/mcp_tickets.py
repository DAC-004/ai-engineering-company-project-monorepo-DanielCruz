"""Ticket reads for the support agent through the HealthCore MCP server.

The graph used to call the incident service in-process. That path is disabled.
This module calls ``query_incidents`` with ``langchain-mcp-adapters`` and the
process-level agent credential. It does not fall back to ``incident_service``.
Title and description are dropped here so they never enter graph state.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

import httpx

AGENT_MCP_SCOPES = "healthcore:mcp incidents:read"
QUERY_INCIDENTS_TOOL = "query_incidents"
_HTTP_TIMEOUT_SECONDS = 5.0


class McpTicketError(Exception):
    """Controlled MCP lookup failure. ``failure`` is ``missing`` or ``error``."""

    def __init__(self, failure: str) -> None:
        self.failure = failure
        super().__init__(failure)


@dataclass(frozen=True)
class TicketSnapshot:
    """Fields the agent may quote. The ticket body is intentionally absent."""

    id: str
    status: str
    category: str
    origin: str
    branch: str


def read_tickets_via_mcp(query: Any) -> list[TicketSnapshot]:
    """Call the MCP query tool. A missing credential does not read TinyDB."""
    arguments = _query_arguments(query)
    try:
        payload = asyncio.run(_call_query_incidents(arguments))
    except McpTicketError:
        raise
    except Exception as exc:
        raise McpTicketError("error") from exc
    return _snapshots_from_payload(payload)


def fetch_agent_access_token(http_client: httpx.Client | None = None) -> str:
    """Use a pre-issued token, or Logto client credentials for the agent scopes.

    The client-credentials request asks only for ``healthcore:mcp`` and
    ``incidents:read``. The resource parameter is the exact ``MCP_RESOURCE_URL``.
    The token value is returned to the caller and is not logged.
    """
    issued = os.environ.get("MCP_AGENT_ACCESS_TOKEN", "").strip()
    if issued:
        return issued
    client_id = os.environ.get("MCP_AGENT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("MCP_AGENT_CLIENT_SECRET", "").strip()
    issuer = os.environ.get("MCP_AUTH_ISSUER", "").strip().rstrip("/")
    resource = os.environ.get("MCP_RESOURCE_URL", "").strip()
    if not client_id or not client_secret or not issuer or not resource:
        raise McpTicketError("error")
    owns_client = http_client is None
    client = http_client or httpx.Client(timeout=_HTTP_TIMEOUT_SECONDS)
    try:
        discovery = client.get(f"{issuer}/.well-known/openid-configuration")
        discovery.raise_for_status()
        token_endpoint = discovery.json().get("token_endpoint")
        if not isinstance(token_endpoint, str) or not token_endpoint:
            raise McpTicketError("error")
        token_response = client.post(
            token_endpoint,
            data={
                "grant_type": "client_credentials",
                "resource": resource,
                "scope": AGENT_MCP_SCOPES,
            },
            auth=(client_id, client_secret),
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise McpTicketError("error")
        return access_token
    except McpTicketError:
        raise
    except Exception as exc:
        raise McpTicketError("error") from exc
    finally:
        if owns_client:
            client.close()


def _query_arguments(query: Any) -> dict[str, str]:
    incident_id = (getattr(query, "incident_id", None) or "").strip()
    if incident_id:
        return {"incident_id": incident_id}
    arguments: dict[str, str] = {}
    for field_name in ("status", "origin", "branch", "category"):
        value = getattr(query, field_name, None)
        if isinstance(value, str) and value.strip():
            arguments[field_name] = value.strip()
    return arguments


async def _call_query_incidents(arguments: dict[str, str]) -> dict[str, Any]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    resource_url = os.environ.get("MCP_RESOURCE_URL", "").strip()
    if not resource_url:
        raise McpTicketError("error")
    access_token = fetch_agent_access_token()
    client = MultiServerMCPClient(
        {
            "healthcore": {
                "transport": "streamable_http",
                "url": resource_url,
                "headers": {"Authorization": f"Bearer {access_token}"},
                "timeout": _HTTP_TIMEOUT_SECONDS,
            }
        }
    )
    async with client.session("healthcore") as session:
        result = await session.call_tool(QUERY_INCIDENTS_TOOL, arguments)
    if getattr(result, "isError", False):
        raise McpTicketError("error")
    payload = getattr(result, "structuredContent", None)
    if not isinstance(payload, dict):
        raise McpTicketError("error")
    return payload


def _snapshots_from_payload(payload: dict[str, Any]) -> list[TicketSnapshot]:
    if payload.get("ok") is not True:
        if payload.get("code") == "incident_not_found":
            raise McpTicketError("missing")
        raise McpTicketError("error")
    incidents = payload.get("incidents")
    if not isinstance(incidents, list):
        raise McpTicketError("error")
    snapshots: list[TicketSnapshot] = []
    for incident in incidents:
        if not isinstance(incident, dict):
            raise McpTicketError("error")
        snapshots.append(
            TicketSnapshot(
                id=str(incident.get("id", "")),
                status=str(incident.get("status", "")),
                category=str(incident.get("category", "")),
                origin=str(incident.get("origin", "")),
                branch=str(incident.get("branch", "")),
            )
        )
    return snapshots
