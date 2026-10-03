"""Runtime settings for the HealthCore MCP resource server.

The OAuth issuer and the HealthCore API credentials come from the environment.
Nothing in this module embeds a token, password, or connection string.
"""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Gate scope required before any MCP method, including tools/list.
SCOPE_MCP_ACCESS = "healthcore:mcp"
# Read scope for inventory queries. There is no inventory write scope.
SCOPE_INVENTORY_READ = "inventory:read"
SCOPE_INCIDENTS_READ = "incidents:read"
SCOPE_INCIDENTS_WRITE = "incidents:write"

SUPPORTED_SCOPES: tuple[str, ...] = (
    SCOPE_MCP_ACCESS,
    SCOPE_INCIDENTS_READ,
    SCOPE_INCIDENTS_WRITE,
    SCOPE_INVENTORY_READ,
)

# Actions the modification tool recognizes and then rejects. Unknown actions
# are validation failures, not silent no-ops.
INVENTORY_WRITE_ACTIONS: frozenset[str] = frozenset(
    {
        "create_product",
        "update_product",
        "set_stock",
        "create_inbound_order",
        "create_outbound_order",
    }
)

CLINIC_ID_MIN = 1
CLINIC_ID_MAX = 12


class Settings(BaseSettings):
    """Environment-backed MCP and upstream API configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    mcp_auth_issuer: str = Field(alias="MCP_AUTH_ISSUER", min_length=1)
    # Exact resource identifier. `/mcp` and `/mcp/` are different audiences.
    # This string is copied into Protected Resource Metadata, the bearer
    # audience, and the token `aud` check. It is not normalized.
    mcp_resource_url: str = Field(
        default="http://127.0.0.1:3001/mcp",
        alias="MCP_RESOURCE_URL",
        min_length=1,
    )
    mcp_host: str = Field(default="127.0.0.1", alias="MCP_HOST", min_length=1)
    mcp_port: int = Field(default=3001, alias="MCP_PORT", ge=1, le=65535)
    healthcore_api_base_url: str = Field(
        default="http://127.0.0.1:8000",
        alias="HEALTHCORE_API_BASE_URL",
        min_length=1,
    )
    healthcore_api_username: str = Field(alias="HEALTHCORE_API_USERNAME", min_length=1)
    healthcore_api_password: SecretStr = Field(alias="HEALTHCORE_API_PASSWORD")
