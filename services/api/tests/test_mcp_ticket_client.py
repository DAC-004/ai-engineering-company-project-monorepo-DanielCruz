"""Agent MCP credential checks. These do not call Logto or the incident service."""

from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest

from app.agent.mcp_tickets import (
    AGENT_MCP_SCOPES,
    McpTicketError,
    fetch_agent_access_token,
)


def test_preissued_token_is_used_without_a_token_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_AGENT_ACCESS_TOKEN", "preissued-agent-token")

    def reject(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"token request was sent to {request.url}")

    token = fetch_agent_access_token(httpx.Client(transport=httpx.MockTransport(reject)))
    assert token == "preissued-agent-token"


def test_client_credentials_stay_on_the_agent_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_AGENT_ACCESS_TOKEN", "")
    monkeypatch.setenv("MCP_AGENT_CLIENT_ID", "agent-client")
    monkeypatch.setenv("MCP_AGENT_CLIENT_SECRET", "agent-secret")
    monkeypatch.setenv("MCP_AUTH_ISSUER", "https://issuer.example/oidc")
    monkeypatch.setenv("MCP_RESOURCE_URL", "https://codespace.example/mcp")
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={"token_endpoint": "https://issuer.example/oidc/token"},
            )
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"access_token": "minted-agent-token"})

    token = fetch_agent_access_token(httpx.Client(transport=httpx.MockTransport(handler)))
    form = parse_qs(captured["body"])
    assert token == "minted-agent-token"
    assert form["grant_type"] == ["client_credentials"]
    assert form["resource"] == ["https://codespace.example/mcp"]
    assert form["scope"] == [AGENT_MCP_SCOPES]
    assert "incidents:write" not in form["scope"][0]
    assert "inventory:read" not in form["scope"][0]


def test_missing_agent_credential_does_not_invent_a_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MCP_AGENT_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("MCP_AGENT_CLIENT_ID", raising=False)
    monkeypatch.delenv("MCP_AGENT_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("MCP_AUTH_ISSUER", "https://issuer.example/oidc")
    monkeypatch.setenv("MCP_RESOURCE_URL", "https://codespace.example/mcp")
    with pytest.raises(McpTicketError) as caught:
        fetch_agent_access_token(httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(500))))
    assert caught.value.failure == "error"
