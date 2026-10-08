"""One malformed payload for each MCP tool family. Does not start the server."""

import importlib.util
import json
import sys
import types
from pathlib import Path

import httpx

root = Path("/opt/healthcore/app/mcps/healthcore-tools/src")
sys.path.insert(0, str(root))
package = types.ModuleType("healthcore_tools")
package.__path__ = [str(root / "healthcore_tools")]
sys.modules["healthcore_tools"] = package


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


errors = load("healthcore_tools.errors", root / "healthcore_tools" / "errors.py")
api = load("healthcore_tools.healthcore_api", root / "healthcore_tools" / "healthcore_api.py")
config = load("healthcore_tools.config", root / "healthcore_tools" / "config.py")
server_text = (root / "healthcore_tools" / "server.py").read_text(encoding="utf-8")
start = server_text.index("def _require_incident_id")
end = server_text.index("def _query_failure")
namespace = {
    "ErrorCode": errors.ErrorCode,
    "ToolCallError": errors.ToolCallError,
    "CLINIC_ID_MIN": config.CLINIC_ID_MIN,
    "CLINIC_ID_MAX": config.CLINIC_ID_MAX,
    "_INCIDENT_ID": __import__("re").compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    ),
}
exec(server_text[start:end], namespace)
require_incident_id = namespace["_require_incident_id"]


def show(family: str, payload: str, outcome: str) -> None:
    print("FAMILY", family)
    print("PAYLOAD", payload)
    print("RESULT", outcome)


def validate_clinic(clinic_id):
    try:
        namespace["_validate_clinic_id"](clinic_id)
    except errors.ToolCallError as exc:
        return exc.code.value
    return "allowed"


try:
    api.reject_inventory_write("GET", "/inventory/products/1")
    query_stock = "allowed"
except errors.ToolCallError as exc:
    query_stock = exc.code.value
show("query_medical_supply_inventory", "stock=1", query_stock)
show("query_medical_supply_inventory", "clinic_id=99", validate_clinic(99))

unknown = "not-a-real-action"
attempt = "validation_failed" if unknown not in config.INVENTORY_WRITE_ACTIONS else "recognized"
show("attempt_inventory_modification", "action=not-a-real-action", attempt)
try:
    api.reject_inventory_write("PATCH", "/inventory/products/1")
    recognized = "allowed"
except errors.ToolCallError as exc:
    recognized = exc.code.value
show("attempt_inventory_modification", "action=update_product", recognized)

seen = []

def handler(request: httpx.Request) -> httpx.Response:
    seen.append(request.url.path)
    if request.url.path == "/auth/login":
        return httpx.Response(200, json={"access_token": "redacted", "token_type": "bearer"})
    return httpx.Response(400, json={"field": "category", "message": "validation"})


http_client = httpx.Client(
    base_url="http://127.0.0.1:8000",
    transport=httpx.MockTransport(handler),
)
client = api.HealthCoreApiClient(
    base_url="http://127.0.0.1:8000",
    username="audit-mcp@example.com",
    password="not-printed",
    http_client=http_client,
)
try:
    client.create_incident(
        {
            "title": "Synthetic probe",
            "description": "https://evil.example/hook",
            "category": "not-a-category",
            "origin": "chat",
            "branch": "north",
        }
    )
    created = "allowed"
except errors.ToolCallError as exc:
    created = exc.code.value
show("create_incident", "category=not-a-category", created)
print("CREATE_PATHS", ",".join(seen))
print("EVIL_HOST_REQUESTED", any("evil.example" in path for path in seen))

try:
    require_incident_id("HC-100001")
    updated = "allowed"
except errors.ToolCallError as exc:
    updated = exc.code.value
show("update_incident_status", "incident_id=HC-100001", updated)

try:
    require_incident_id("not-a-uuid")
    queried = "allowed"
except errors.ToolCallError as exc:
    queried = exc.code.value
show("query_incidents", "incident_id=not-a-uuid", queried)
