"""HTTP client for the existing HealthCore API.

Inventory calls are limited to three GET routes. Any other inventory method or
path is rejected in this process before an HTTP write is sent. Incident calls
use the Incident Manager routes: create, status patch, and query.
"""

from __future__ import annotations

from typing import Any

import httpx

from healthcore_tools.errors import ErrorCode, ToolCallError

INVENTORY_PRODUCTS_PATH = "/inventory/products"
INVENTORY_ORDERS_PATH = "/inventory/orders"

# Client-visible write attempts and the upstream route each one would have used.
# The route is named in the rejection. It is not requested.
INVENTORY_WRITE_ROUTES: dict[str, tuple[str, str]] = {
    "create_product": ("POST", INVENTORY_PRODUCTS_PATH),
    "update_product": ("PATCH", "/inventory/products/{supply_id}"),
    "set_stock": ("PATCH", "/inventory/products/{supply_id}"),
    "create_inbound_order": ("POST", "/inventory/orders/inbound"),
    "create_outbound_order": ("POST", "/inventory/orders/outbound"),
}


def inventory_get_is_allowlisted(path: str) -> bool:
    """True only for the three inventory reads this server may send."""
    if path in {INVENTORY_PRODUCTS_PATH, INVENTORY_ORDERS_PATH}:
        return True
    prefix = f"{INVENTORY_PRODUCTS_PATH}/"
    if not path.startswith(prefix):
        return False
    supply_id = path.removeprefix(prefix)
    return supply_id.isdigit() and int(supply_id) > 0


def reject_inventory_write(method: str, path: str) -> None:
    """Refuse an inventory write inside the MCP process, before any HTTP send."""
    raise ToolCallError(
        ErrorCode.INVENTORY_WRITE_FORBIDDEN,
        (
            "Inventory access is read-only. "
            f"The MCP server rejected {method.upper()} {path} "
            "before sending an inventory write."
        ),
    )


def inventory_route_for_action(action: str, supply_id: int | None) -> tuple[str, str]:
    """Return the method and path a recognized write would have called."""
    method, path_template = INVENTORY_WRITE_ROUTES[action]
    if "{supply_id}" in path_template:
        rendered_id = str(supply_id) if supply_id is not None else "{supply_id}"
        return method, path_template.format(supply_id=rendered_id)
    return method, path_template


class HealthCoreApiClient:
    """Service-account caller for allowlisted inventory reads and incident routes."""

    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(base_url=base_url, timeout=30.0)
        self._access_token: str | None = None

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def list_products(self) -> list[dict[str, Any]]:
        """GET /inventory/products."""
        payload = self.call_upstream("GET", INVENTORY_PRODUCTS_PATH)
        if not isinstance(payload, list):
            raise ToolCallError(
                ErrorCode.UPSTREAM_REQUEST_FAILED,
                "HealthCore GET /inventory/products did not return a list.",
            )
        return payload

    def get_product(self, supply_id: int, clinic_id: int | None) -> dict[str, Any]:
        """GET /inventory/products/{id} with the optional clinic_id query."""
        params = {"clinic_id": clinic_id} if clinic_id is not None else None
        payload = self.call_upstream(
            "GET",
            f"{INVENTORY_PRODUCTS_PATH}/{supply_id}",
            params=params,
        )
        if not isinstance(payload, dict):
            raise ToolCallError(
                ErrorCode.UPSTREAM_REQUEST_FAILED,
                "HealthCore GET /inventory/products/{id} did not return an object.",
            )
        return payload

    def list_orders(self) -> list[dict[str, Any]]:
        """GET /inventory/orders."""
        payload = self.call_upstream("GET", INVENTORY_ORDERS_PATH)
        if not isinstance(payload, list):
            raise ToolCallError(
                ErrorCode.UPSTREAM_REQUEST_FAILED,
                "HealthCore GET /inventory/orders did not return a list.",
            )
        return payload

    def create_incident(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /api/incidents. The body is the Incident Manager create contract."""
        body = self.call_upstream("POST", "/api/incidents", json_body=payload)
        if not isinstance(body, dict):
            raise ToolCallError(
                ErrorCode.UPSTREAM_REQUEST_FAILED,
                "HealthCore POST /api/incidents did not return an object.",
            )
        return body

    def update_incident_status(self, incident_id: str, status: str) -> dict[str, Any]:
        """PATCH /api/incidents/{id}/status with a status-only body."""
        body = self.call_upstream(
            "PATCH",
            f"/api/incidents/{incident_id}/status",
            json_body={"status": status},
        )
        if not isinstance(body, dict):
            raise ToolCallError(
                ErrorCode.UPSTREAM_REQUEST_FAILED,
                "HealthCore PATCH /api/incidents/{id}/status did not return an object.",
            )
        return body

    def get_incident(self, incident_id: str) -> dict[str, Any]:
        """GET /api/incidents/{id}."""
        body = self.call_upstream("GET", f"/api/incidents/{incident_id}")
        if not isinstance(body, dict):
            raise ToolCallError(
                ErrorCode.UPSTREAM_REQUEST_FAILED,
                "HealthCore GET /api/incidents/{id} did not return an object.",
            )
        return body

    def list_incidents(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """GET /api/incidents with optional exact filters."""
        body = self.call_upstream("GET", "/api/incidents", params=params or None)
        if not isinstance(body, list):
            raise ToolCallError(
                ErrorCode.UPSTREAM_REQUEST_FAILED,
                "HealthCore GET /api/incidents did not return a list.",
            )
        return body

    def call_upstream(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Send one upstream call, or reject an inventory write before send."""
        if path.startswith("/inventory") and not (
            method.upper() == "GET" and inventory_get_is_allowlisted(path)
        ):
            reject_inventory_write(method, path)
        response = self._send(
            method,
            path,
            params=params,
            json_body=json_body,
            retry_on_unauthorized=True,
        )
        return self._interpret(path, response)

    def _interpret(self, path: str, response: httpx.Response) -> Any:
        if response.status_code == 401:
            raise ToolCallError(
                ErrorCode.UPSTREAM_AUTH_FAILED,
                "The HealthCore API rejected the MCP service credential.",
            )
        if response.status_code == 404 and path.startswith("/inventory"):
            raise ToolCallError(ErrorCode.INVENTORY_NOT_FOUND, "Medical supply not found")
        if response.status_code == 404 and path.startswith("/api/incidents"):
            raise ToolCallError(ErrorCode.INCIDENT_NOT_FOUND, "That incident was not found.")
        if response.status_code == 400 and path.startswith("/api/incidents"):
            # Manager 400 bodies are {field, message}. They are validation, not auth.
            body = _json_object(response)
            field = body.get("field") if isinstance(body.get("field"), str) else "request"
            message = body.get("message") if isinstance(body.get("message"), str) else (
                "The incident request was rejected."
            )
            raise ToolCallError(ErrorCode.VALIDATION_FAILED, f"{field}: {message}")
        if response.status_code >= 400:
            raise ToolCallError(
                ErrorCode.UPSTREAM_REQUEST_FAILED,
                f"HealthCore API returned HTTP {response.status_code} for {path}.",
            )
        return response.json()

    def _send(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        json_body: dict[str, Any] | None,
        retry_on_unauthorized: bool,
    ) -> httpx.Response:
        token = self._service_token()
        response = self._http.request(
            method,
            path,
            params=params,
            json=json_body,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401 and retry_on_unauthorized:
            self._access_token = None
            token = self._service_token()
            response = self._http.request(
                method,
                path,
                params=params,
                json=json_body,
                headers={"Authorization": f"Bearer {token}"},
            )
        return response

    def _service_token(self) -> str:
        """Login once and reuse the HealthCore JWT. The token is not logged."""
        if self._access_token:
            return self._access_token
        response = self._http.post(
            "/auth/login",
            data={"username": self._username, "password": self._password},
        )
        if response.status_code != 200:
            raise ToolCallError(
                ErrorCode.UPSTREAM_AUTH_FAILED,
                "The MCP server could not authenticate to the HealthCore API.",
            )
        body = _json_object(response)
        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            raise ToolCallError(
                ErrorCode.UPSTREAM_AUTH_FAILED,
                "The HealthCore login response did not include an access token.",
            )
        self._access_token = token
        return token


def _json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    if isinstance(body, dict):
        return body
    return {}
