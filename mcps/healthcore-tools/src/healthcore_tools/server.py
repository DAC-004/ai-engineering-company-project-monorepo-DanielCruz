"""HealthCore MCP resource server.

Transport is Streamable HTTP. A remote MCP Playground and any other HTTP client
need a URL, Protected Resource Metadata, and an Authorization bearer header.
stdio cannot carry that OAuth resource-server handshake to an external client.

FastMCP is used only as the MCP tool host. Authentication is mcpauth in
resource-server mode. FastMCP's auth, token_verifier, and AuthSettings are
left unset on purpose.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import re
from datetime import date, datetime
from typing import Literal

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from mcpauth import MCPAuth
from mcpauth.config import AuthServerType
from mcpauth.types import ResourceServerConfig, ResourceServerMetadata
from mcpauth.utils import fetch_server_config
from pydantic import BaseModel, Field
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount

from healthcore_tools.config import (
    CLINIC_ID_MAX,
    CLINIC_ID_MIN,
    INVENTORY_WRITE_ACTIONS,
    SCOPE_INCIDENTS_READ,
    SCOPE_INCIDENTS_WRITE,
    SCOPE_INVENTORY_READ,
    SCOPE_MCP_ACCESS,
    SUPPORTED_SCOPES,
    Settings,
)
from healthcore_tools.errors import ErrorCode, ToolCallError
from healthcore_tools.healthcore_api import (
    HealthCoreApiClient,
    inventory_route_for_action,
    reject_inventory_write,
)
from healthcore_tools.invocation_log import configure_invocation_logging, log_tool_invocation

QUERY_TOOL = "query_medical_supply_inventory"
WRITE_ATTEMPT_TOOL = "attempt_inventory_modification"
CREATE_INCIDENT_TOOL = "create_incident"
UPDATE_INCIDENT_STATUS_TOOL = "update_incident_status"
QUERY_INCIDENTS_TOOL = "query_incidents"

DISCOVERED_TOOLS = (
    QUERY_TOOL,
    WRITE_ATTEMPT_TOOL,
    CREATE_INCIDENT_TOOL,
    UPDATE_INCIDENT_STATUS_TOOL,
    QUERY_INCIDENTS_TOOL,
)

_INCIDENT_ID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class MedicalSupplyRecord(BaseModel):
    """Fields returned by the HealthCore MedicalSupply public schema."""

    id: int
    name: str
    sku: str
    category: str
    unit: str
    country: str
    current_stock: int
    minimum_stock: int
    expiry_date: date | None = None
    clinic_current_stock: int | None = None


class InventoryOrderRecord(BaseModel):
    """Fields returned by the HealthCore inventory order public schema."""

    id: int
    order_type: Literal["delivery", "consumption"]
    supply_id: int
    supply_name: str
    supply_sku: str
    supply_category: str
    supply_unit: str
    supply_country: str
    quantity: int
    clinic_id: int
    created_at: datetime
    user_uuid: str
    vendor_name: str | None = None
    consumption_type: str | None = None
    department: str | None = None


class InventoryQueryOutput(BaseModel):
    """Discoverable result for a read. `code` is `ok` or a documented ErrorCode."""

    ok: bool
    code: str
    message: str
    lookup: str | None = None
    products: list[MedicalSupplyRecord] = Field(default_factory=list)
    orders: list[InventoryOrderRecord] = Field(default_factory=list)


class InventoryWriteAttemptOutput(BaseModel):
    """Discoverable result for a modification attempt. `modified` stays false."""

    ok: bool
    code: str
    message: str
    action: str | None = None
    modified: bool = False


class IncidentRecord(BaseModel):
    """Public Incident Manager fields. The agent must not copy title or description."""

    id: str
    title: str
    description: str
    category: str
    status: str
    origin: str
    branch: str
    created_at: datetime
    updated_at: datetime


class IncidentToolOutput(BaseModel):
    """Discoverable result for create, status update, and query."""

    ok: bool
    code: str
    message: str
    incidents: list[IncidentRecord] = Field(default_factory=list)


def _client_label(mcp_auth: MCPAuth) -> str:
    """OAuth client id, then subject. Never the raw token."""
    auth_info = mcp_auth.auth_info
    if auth_info is None:
        return "unknown"
    if auth_info.client_id:
        return auth_info.client_id
    return auth_info.subject


def _require_scope(mcp_auth: MCPAuth, scope: str) -> None:
    """Tool-level least privilege. Middleware already required healthcore:mcp."""
    auth_info = mcp_auth.auth_info
    scopes = auth_info.scopes if auth_info is not None else []
    if scope not in scopes:
        raise ToolCallError(
            ErrorCode.MISSING_REQUIRED_SCOPES,
            f"This tool requires the {scope} scope.",
        )


def _require_incident_id(incident_id: str) -> str:
    """Incident Manager ids are UUID strings. HC-###### and bare numbers are not."""
    cleaned = incident_id.strip()
    if not _INCIDENT_ID.fullmatch(cleaned):
        raise ToolCallError(
            ErrorCode.VALIDATION_FAILED,
            "incident_id must be the Incident Manager UUID.",
        )
    return cleaned


def _validate_clinic_id(clinic_id: int | None) -> None:
    if clinic_id is None:
        return
    if clinic_id < CLINIC_ID_MIN or clinic_id > CLINIC_ID_MAX:
        raise ToolCallError(
            ErrorCode.VALIDATION_FAILED,
            f"clinic_id must be between {CLINIC_ID_MIN} and {CLINIC_ID_MAX}.",
        )


def _query_failure(lookup: str, error: ToolCallError) -> InventoryQueryOutput:
    return InventoryQueryOutput(
        ok=False,
        code=error.code.value,
        message=error.message,
        lookup=lookup,
    )


def _write_failure(action: str | None, error: ToolCallError) -> InventoryWriteAttemptOutput:
    return InventoryWriteAttemptOutput(
        ok=False,
        code=error.code.value,
        message=error.message,
        action=action,
        modified=False,
    )


def _incident_failure(error: ToolCallError) -> IncidentToolOutput:
    return IncidentToolOutput(ok=False, code=error.code.value, message=error.message)


def create_app(
    settings: Settings,
    *,
    api_client: HealthCoreApiClient | None = None,
) -> Starlette:
    """Build the Streamable HTTP app with MCP Auth in front of the MCP endpoint."""
    configure_invocation_logging()
    auth_server = fetch_server_config(settings.mcp_auth_issuer, AuthServerType.OIDC)
    resource_id = settings.mcp_resource_url
    mcp_auth = MCPAuth(
        protected_resources=[
            ResourceServerConfig(
                metadata=ResourceServerMetadata(
                    resource=resource_id,
                    authorization_servers=[auth_server],
                    scopes_supported=list(SUPPORTED_SCOPES),
                    bearer_methods_supported=["header"],
                    resource_name="HealthCore company tools",
                    resource_documentation=resource_id,
                )
            )
        ]
    )
    inventory_api = api_client or HealthCoreApiClient(
        base_url=settings.healthcore_api_base_url,
        username=settings.healthcore_api_username,
        password=settings.healthcore_api_password.get_secret_value(),
    )

    # host 127.0.0.1 turns on DNS-rebinding checks for localhost. 0.0.0.0 does
    # not, which is what a Codespaces forwarded URL needs.
    mcp = FastMCP(
        name="HealthCore company tools",
        instructions=(
            "Authorized tools for HealthCore inventory and the Incident Manager. "
            "Inventory is read-only: query_medical_supply_inventory reads "
            "MedicalSupply rows and orders, and attempt_inventory_modification "
            "is rejected by the server allowlist before any inventory write is "
            "sent. create_incident, update_incident_status, and query_incidents "
            "call the existing Incident Manager API. Do not send tokens to the "
            "tools; authenticate with the HTTP bearer header."
        ),
        host=settings.mcp_host,
        port=settings.mcp_port,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        auth=None,
        token_verifier=None,
    )

    @mcp.tool(
        name=QUERY_TOOL,
        description=(
            "Read HealthCore medical-supply inventory from the existing API. "
            "lookup=products lists MedicalSupply rows (optional sku filter). "
            "lookup=product requires supply_id and may include clinic_id "
            f"({CLINIC_ID_MIN}-{CLINIC_ID_MAX}) to also return clinic_current_stock. "
            "lookup=orders lists SupplyDelivery and SupplyConsumption rows. "
            "current_stock is computed by the API. Supplying stock or current_stock "
            "is rejected by the inventory write allowlist and does not call the API. "
            f"Requires OAuth scope {SCOPE_INVENTORY_READ}."
        ),
        annotations=ToolAnnotations(
            title="Query medical supply inventory",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    def query_medical_supply_inventory(
        lookup: Literal["products", "product", "orders"],
        supply_id: int | None = None,
        clinic_id: int | None = None,
        sku: str | None = None,
        stock: int | None = None,
        current_stock: int | None = None,
    ) -> InventoryQueryOutput:
        client = _client_label(mcp_auth)
        try:
            _require_scope(mcp_auth, SCOPE_INVENTORY_READ)
            if stock is not None or current_stock is not None:
                target = (
                    f"/inventory/products/{supply_id}"
                    if supply_id is not None
                    else "/inventory/products/{supply_id}"
                )
                reject_inventory_write("PATCH", target)
            _validate_clinic_id(clinic_id)
            if lookup == "product" and (supply_id is None or supply_id < 1):
                raise ToolCallError(
                    ErrorCode.VALIDATION_FAILED,
                    "supply_id is required and must be a positive integer when lookup is product.",
                )
            if lookup == "products":
                rows = [
                    MedicalSupplyRecord.model_validate(row)
                    for row in inventory_api.list_products()
                ]
                if sku:
                    rows = [row for row in rows if row.sku == sku]
                output = InventoryQueryOutput(
                    ok=True,
                    code="ok",
                    message=f"Returned {len(rows)} medical supplies.",
                    lookup=lookup,
                    products=rows,
                )
            elif lookup == "product":
                assert supply_id is not None
                row = inventory_api.get_product(supply_id, clinic_id)
                output = InventoryQueryOutput(
                    ok=True,
                    code="ok",
                    message=f"Returned medical supply {supply_id}.",
                    lookup=lookup,
                    products=[MedicalSupplyRecord.model_validate(row)],
                )
            else:
                orders = [
                    InventoryOrderRecord.model_validate(row)
                    for row in inventory_api.list_orders()
                ]
                output = InventoryQueryOutput(
                    ok=True,
                    code="ok",
                    message=f"Returned {len(orders)} inventory orders.",
                    lookup=lookup,
                    orders=orders,
                )
        except ToolCallError as error:
            log_tool_invocation(tool=QUERY_TOOL, client=client, result=error.code.value)
            return _query_failure(lookup, error)
        log_tool_invocation(tool=QUERY_TOOL, client=client, result="ok")
        return output

    @mcp.tool(
        name=WRITE_ATTEMPT_TOOL,
        description=(
            "Explicitly reject an inventory modification. Inventory permission "
            "design is read-only: this server has no inventory write scope and "
            "calls the same allowlist rejection as every other inventory write. "
            "Recognized actions are create_product, update_product, set_stock, "
            "create_inbound_order, and create_outbound_order. Each names the "
            "upstream route it refused and returns inventory_write_forbidden "
            "with modified=false. The HealthCore API 405 on stock edits is not "
            "this control. An unknown action returns validation_failed. "
            f"Requires OAuth scope {SCOPE_INVENTORY_READ} to reach the rejection."
        ),
        annotations=ToolAnnotations(
            title="Reject inventory modification",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def attempt_inventory_modification(
        action: str,
        supply_id: int | None = None,
        sku: str | None = None,
        quantity: int | None = None,
        stock: int | None = None,
    ) -> InventoryWriteAttemptOutput:
        client = _client_label(mcp_auth)
        normalized_action = action.strip()
        try:
            _require_scope(mcp_auth, SCOPE_INVENTORY_READ)
            if not normalized_action:
                raise ToolCallError(
                    ErrorCode.VALIDATION_FAILED,
                    "action is required. Recognized write actions are rejected, not applied.",
                )
            if normalized_action not in INVENTORY_WRITE_ACTIONS:
                raise ToolCallError(
                    ErrorCode.VALIDATION_FAILED,
                    "Unknown inventory action. Recognized write actions are rejected "
                    "with inventory_write_forbidden and are not applied.",
                )
            method, path = inventory_route_for_action(normalized_action, supply_id)
            # Same function the upstream client uses. Arguments stay local.
            described = ", ".join(
                part
                for part in (
                    f"sku={sku}" if sku else "",
                    f"quantity={quantity}" if quantity is not None else "",
                    f"stock={stock}" if stock is not None else "",
                )
                if part
            )
            try:
                reject_inventory_write(method, path)
            except ToolCallError as rejection:
                detail = f" Attempt was {described}." if described else ""
                raise ToolCallError(
                    rejection.code,
                    f"action={normalized_action}. {rejection.message}{detail}",
                ) from None
        except ToolCallError as error:
            log_tool_invocation(
                tool=WRITE_ATTEMPT_TOOL,
                client=client,
                result=error.code.value,
            )
            return _write_failure(normalized_action or None, error)
        raise RuntimeError("Inventory write rejection did not return a tool result.")

    @mcp.tool(
        name=CREATE_INCIDENT_TOOL,
        description=(
            "Create one Incident Manager ticket with POST /api/incidents. "
            "Fields are title, description, category, status (default open), "
            "origin, and branch. Status, category, origin, and branch must be "
            "HealthCore manager values. The response includes the generated UUID. "
            f"Requires OAuth scope {SCOPE_INCIDENTS_WRITE}."
        ),
        annotations=ToolAnnotations(
            title="Create incident",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    def create_incident(
        title: str,
        description: str,
        category: str,
        origin: str,
        branch: str,
        status: str = "open",
    ) -> IncidentToolOutput:
        client = _client_label(mcp_auth)
        try:
            _require_scope(mcp_auth, SCOPE_INCIDENTS_WRITE)
            created = inventory_api.create_incident(
                {
                    "title": title,
                    "description": description,
                    "category": category,
                    "status": status,
                    "origin": origin,
                    "branch": branch,
                }
            )
            record = IncidentRecord.model_validate(created)
            output = IncidentToolOutput(
                ok=True,
                code="ok",
                message=f"Created incident {record.id}.",
                incidents=[record],
            )
        except ToolCallError as error:
            log_tool_invocation(
                tool=CREATE_INCIDENT_TOOL,
                client=client,
                result=error.code.value,
            )
            return _incident_failure(error)
        log_tool_invocation(tool=CREATE_INCIDENT_TOOL, client=client, result="ok")
        return output

    @mcp.tool(
        name=UPDATE_INCIDENT_STATUS_TOOL,
        description=(
            "Change one Incident Manager ticket with "
            "PATCH /api/incidents/{incident_id}/status. The body is status only. "
            "incident_id is the UUID. Allowed moves are open to in_progress or "
            "discarded, and in_progress to resolved or discarded. resolved and "
            "discarded are final. "
            f"Requires OAuth scope {SCOPE_INCIDENTS_WRITE}."
        ),
        annotations=ToolAnnotations(
            title="Update incident status",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    def update_incident_status(incident_id: str, status: str) -> IncidentToolOutput:
        client = _client_label(mcp_auth)
        try:
            _require_scope(mcp_auth, SCOPE_INCIDENTS_WRITE)
            cleaned_id = _require_incident_id(incident_id)
            updated = inventory_api.update_incident_status(cleaned_id, status)
            record = IncidentRecord.model_validate(updated)
            output = IncidentToolOutput(
                ok=True,
                code="ok",
                message=f"Incident {record.id} status is {record.status}.",
                incidents=[record],
            )
        except ToolCallError as error:
            log_tool_invocation(
                tool=UPDATE_INCIDENT_STATUS_TOOL,
                client=client,
                result=error.code.value,
            )
            return _incident_failure(error)
        log_tool_invocation(tool=UPDATE_INCIDENT_STATUS_TOOL, client=client, result="ok")
        return output

    @mcp.tool(
        name=QUERY_INCIDENTS_TOOL,
        description=(
            "Read Incident Manager tickets. Provide incident_id to GET "
            "/api/incidents/{incident_id}. Omit incident_id to GET /api/incidents "
            "with optional exact filters status, origin, branch, and category. "
            "An id and filters are not combined. "
            f"Requires OAuth scope {SCOPE_INCIDENTS_READ}."
        ),
        annotations=ToolAnnotations(
            title="Query incidents",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    def query_incidents(
        incident_id: str | None = None,
        status: str | None = None,
        origin: str | None = None,
        branch: str | None = None,
        category: str | None = None,
    ) -> IncidentToolOutput:
        client = _client_label(mcp_auth)
        try:
            _require_scope(mcp_auth, SCOPE_INCIDENTS_READ)
            if incident_id is not None and incident_id.strip():
                cleaned_id = _require_incident_id(incident_id)
                rows = [inventory_api.get_incident(cleaned_id)]
            else:
                filters = {
                    key: value
                    for key, value in (
                        ("status", status),
                        ("origin", origin),
                        ("branch", branch),
                        ("category", category),
                    )
                    if value
                }
                rows = inventory_api.list_incidents(filters)
            records = [IncidentRecord.model_validate(row) for row in rows]
            output = IncidentToolOutput(
                ok=True,
                code="ok",
                message=f"Returned {len(records)} incidents.",
                incidents=records,
            )
        except ToolCallError as error:
            log_tool_invocation(
                tool=QUERY_INCIDENTS_TOOL,
                client=client,
                result=error.code.value,
            )
            return _incident_failure(error)
        log_tool_invocation(tool=QUERY_INCIDENTS_TOOL, client=client, result="ok")
        return output

    bearer_middleware = Middleware(
        mcp_auth.bearer_auth_middleware(
            "jwt",
            resource=resource_id,
            audience=resource_id,
            required_scopes=[SCOPE_MCP_ACCESS],
            show_error_details=False,
        )
    )

    @asynccontextmanager
    async def lifespan(_app: Starlette):
        async with mcp.session_manager.run():
            try:
                yield
            finally:
                inventory_api.close()

    # Metadata routes stay outside the bearer mount so clients can discover
    # how to authenticate. CORSMiddleware answers browser preflight before
    # that mount, which an external Playground needs.
    return Starlette(
        routes=[
            *mcp_auth.resource_metadata_router().routes,
            Mount("/", app=mcp.streamable_http_app(), middleware=[bearer_middleware]),
        ],
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
                expose_headers=["WWW-Authenticate", "Mcp-Session-Id"],
            )
        ],
        lifespan=lifespan,
    )


def main() -> None:
    """Start the MCP server. Configuration is read from the environment and .env."""
    settings = Settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.mcp_host, port=settings.mcp_port)


__all__ = [
    "QUERY_TOOL",
    "WRITE_ATTEMPT_TOOL",
    "CREATE_INCIDENT_TOOL",
    "UPDATE_INCIDENT_STATUS_TOOL",
    "QUERY_INCIDENTS_TOOL",
    "DISCOVERED_TOOLS",
    "InventoryQueryOutput",
    "InventoryWriteAttemptOutput",
    "IncidentToolOutput",
    "create_app",
    "main",
]
