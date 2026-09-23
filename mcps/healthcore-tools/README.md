# HealthCore company tools MCP server

Streamable HTTP MCP server for authorized clients that need to read the existing HealthCore inventory module. Authentication is MCP Auth (`mcpauth` 0.2 resource-server mode). FastMCP hosts the tools and does not use its built-in auth provider.

## Transport

Streamable HTTP is the transport. MCP Playground and any other remote client need an HTTP URL, Protected Resource Metadata, and a bearer access token. stdio has no standard place for that OAuth handshake, so it cannot serve the required external client. Local agents use the same HTTP endpoint and the same token checks.

The resource identifier (`MCP_RESOURCE_URL`) is the audience (`aud`) that access tokens must carry. `/mcp` and `/mcp/` are different identifiers. This server does not accept both. For a Codespaces Playground test, set the Logto API indicator, the token `resource` parameter, the metadata `resource` field, and `MCP_RESOURCE_URL` to the same public URL, `https://<forwarded-host>/mcp`, with no slash after `mcp`.

## Run

From this directory:

```bash
uv sync
cp .env.example .env
uv run healthcore-tools
```

Set `MCP_AUTH_ISSUER` to an OAuth 2.1 / OIDC issuer that publishes discovery metadata, advertises the authorization code grant with S256 PKCE, and signs JWTs with a JWKS URI. Bind `MCP_HOST=0.0.0.0` when GitHub Codespaces must forward the port. The HealthCore API must already be running, and `HEALTHCORE_API_USERNAME` / `HEALTHCORE_API_PASSWORD` must be an account on that API. The MCP process uses that account only to call inventory GET routes.

Protected Resource Metadata is public:

`GET /.well-known/oauth-protected-resource/mcp`

The MCP endpoint is `POST /mcp`. A request without a valid bearer token cannot list or call tools.

## Scopes

| Scope | Effect |
| --- | --- |
| `healthcore:mcp` | Required by MCP Auth `required_scopes` before any MCP method, including `tools/list`. |
| `incidents:read` | Required by `query_incidents`. |
| `incidents:write` | Required by `create_incident` and `update_incident_status`. |
| `inventory:read` | Required by the inventory tools, including the write attempt, which is still rejected. |

There is no inventory write scope. A token cannot be granted permission to modify stock. The agent machine-to-machine credential is limited to `healthcore:mcp` and `incidents:read`. The external acceptance client is a separate Logto application with `healthcore:mcp`, `incidents:read`, `incidents:write`, and `inventory:read`.

## Tools

`query_medical_supply_inventory` reads the real API:

- `GET /inventory/products`
- `GET /inventory/products/{id}` with optional `clinic_id` from 1 to 12
- `GET /inventory/orders`

Field names match the HealthCore public schemas (`sku`, `current_stock`, `clinic_current_stock`, `order_type`, and the rest). `current_stock` is computed by the API.

`attempt_inventory_modification` names the upstream route for `create_product`, `update_product`, `set_stock`, `create_inbound_order`, or `create_outbound_order`, then calls the same allowlist rejection the HTTP client uses. `modified` is false. The API's 405 on a direct stock edit is not this control. Supplying `stock` or `current_stock` to the query tool uses that same rejection and does not call the API.

`create_incident` calls `POST /api/incidents`. `update_incident_status` calls `PATCH /api/incidents/{incident_id}/status` with `{status}` only. `query_incidents` calls `GET /api/incidents` or `GET /api/incidents/{incident_id}`. A manager HTTP 400 becomes `validation_failed`. A missing UUID becomes `incident_not_found`. Those are not authentication codes.

## Error codes

Authentication and authorization codes come from MCP Auth on the HTTP response (`error` and `error_description`). Tool results use the same `code` field inside the tool output.

| Code | Where | HTTP | Meaning |
| --- | --- | --- | --- |
| `missing_auth_header` | MCP Auth | 401 | No `Authorization` header. |
| `invalid_auth_header_format` | MCP Auth | 401 | Header is not `Bearer <token>`. |
| `missing_bearer_token` | MCP Auth | 401 | Bearer scheme with an empty token. |
| `invalid_token` | MCP Auth | 401 | Signature, expiry, or JWT validation failed. |
| `invalid_issuer` | MCP Auth | 401 | `iss` is not the configured issuer. |
| `invalid_audience` | MCP Auth | 401 | `aud` is not this server's resource URL. |
| `missing_required_scopes` | MCP Auth or tool | 403 at the gate; tool result when `inventory:read` is missing | Token lacks `healthcore:mcp` or the tool scope. |
| `validation_failed` | tool | tool result | Input does not match the inventory contract, or the write action is unknown. |
| `inventory_write_forbidden` | tool | tool result | A recognized inventory write was rejected and nothing was modified. |
| `inventory_not_found` | tool | tool result | `GET /inventory/products/{id}` returned 404. |
| `incident_not_found` | tool | tool result | `GET` or `PATCH` for an incident id returned 404. |
| `upstream_auth_failed` | tool | tool result | The MCP service credential was rejected by the HealthCore API. The token is not included. |
| `upstream_request_failed` | tool | tool result | The HealthCore API returned another unexpected status. |

## Invocation log

Each tool call logs one line on logger `healthcore_mcp.invocations`:

`tool=<name> client=<oauth client id or subject> result=<ok or error code>`

The bearer token and the upstream password are not written.

## External acceptance

Playground documents an `Authorization` bearer header. It does not run the Logto authorization-code or PKCE login. Obtain a Logto client-credentials token for the acceptance application, with `resource` set to the exact API indicator, and paste only that header into Playground. Do not put the token in Git, logs, reports, or screenshots.

A local OIDC fixture signs tokens for automated checks. That fixture is not a Logto acceptance run. A public Codespaces Playground run is still required before the external checkpoint can pass.

## CSV analyzer

`/api/incidents/analyze` and the results routes belong to the CSV analyzer. The ticket tools call the Incident Manager router, not that analyzer.
