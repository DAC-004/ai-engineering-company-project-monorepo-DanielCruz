"""Acceptance checks for the HealthCore MCP server against the real inventory API."""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from healthcore_tools.config import (
    SCOPE_INCIDENTS_READ,
    SCOPE_INCIDENTS_WRITE,
    SCOPE_INVENTORY_READ,
    SCOPE_MCP_ACCESS,
    SUPPORTED_SCOPES,
    Settings,
)
from healthcore_tools.errors import ToolCallError
from healthcore_tools.healthcore_api import HealthCoreApiClient
from healthcore_tools.invocation_log import INVOCATION_LOGGER_NAME
from healthcore_tools.server import (
    CREATE_INCIDENT_TOOL,
    DISCOVERED_TOOLS,
    QUERY_INCIDENTS_TOOL,
    QUERY_TOOL,
    UPDATE_INCIDENT_STATUS_TOOL,
    WRITE_ATTEMPT_TOOL,
    create_app,
)
from oidc_fixture import start_oidc_issuer

API_DIR = Path(__file__).resolve().parents[3] / "services" / "api"
TEST_API_EMAIL = "mcp-inventory-reader@healthcore.com"
TEST_API_PASSWORD = "HealthCoreMcpTest1!"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_started(server: uvicorn.Server, thread: threading.Thread, label: str) -> None:
    for _ in range(100):
        if server.started:
            return
        if not thread.is_alive():
            break
        time.sleep(0.05)
    raise RuntimeError(f"{label} did not start")


class RunningMcp:
    def __init__(self, server: uvicorn.Server, thread: threading.Thread, url: str) -> None:
        self.server = server
        self.thread = thread
        self.url = url

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


def _start_mcp(app: object, port: int) -> RunningMcp:
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="healthcore-mcp", daemon=True)
    thread.start()
    _wait_until_started(server, thread, "MCP server")
    return RunningMcp(server, thread, f"http://127.0.0.1:{port}/mcp")


class ApiProcess:
    """The existing HealthCore API, started with its own uv environment."""

    def __init__(self, extra_env: dict[str, str] | None = None) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="healthcore-mcp-"))
        self.port = _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.log_path = self.temp_dir / "api.log"
        self.log_file = self.log_path.open("w", encoding="utf-8")
        env = os.environ.copy()
        env["SECRET_KEY"] = "mcp-acceptance-secret-key-32"
        env["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
        env["JWT_ALGORITHM"] = "HS256"
        env["TINYDB_PATH"] = str(self.temp_dir / "auth.json")
        env["DATABASE_URL"] = f"sqlite:///{(self.temp_dir / 'inventory.db').resolve().as_posix()}"
        if extra_env:
            env.update(extra_env)
        self.process = subprocess.Popen(
            [
                "uv",
                "run",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--log-level",
                "warning",
            ],
            cwd=API_DIR,
            env=env,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
        )
        self._wait_until_healthy()

    def _wait_until_healthy(self) -> None:
        deadline = time.time() + 30
        last_error = "no response"
        while time.time() < deadline:
            if self.process.poll() is not None:
                break
            try:
                response = httpx.get(f"{self.base_url}/health", timeout=1.0)
            except httpx.HTTPError as exc:
                last_error = str(exc)
                time.sleep(0.2)
                continue
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}"
            time.sleep(0.2)
        log_text = self.log_path.read_text(encoding="utf-8", errors="replace")
        raise RuntimeError(
            f"HealthCore API did not start ({last_error}). Log:\n{log_text[-2000:]}"
        )

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.log_file.close()


class AcceptanceStack:
    def __init__(self) -> None:
        self.oidc = None
        self.api = None
        self.api_http = None
        self.mcp = None
        self.requests: list[tuple[str, str]] = []
        try:
            self.oidc = start_oidc_issuer(_free_port())
            self.api = ApiProcess()
            mcp_port = _free_port()
            self.resource_url = f"http://127.0.0.1:{mcp_port}/mcp"
            self.api_http = httpx.Client(base_url=self.api.base_url, timeout=30.0)
            self.api_http.event_hooks["request"].append(self._record_request)
            created = self.api_http.post(
                "/users",
                json={"email": TEST_API_EMAIL, "password": TEST_API_PASSWORD},
            )
            if created.status_code not in (200, 201):
                raise RuntimeError(
                    f"Could not register API user: {created.status_code} {created.text}"
                )
            settings = Settings(
                MCP_AUTH_ISSUER=self.oidc.issuer,
                MCP_RESOURCE_URL=self.resource_url,
                MCP_HOST="127.0.0.1",
                MCP_PORT=mcp_port,
                HEALTHCORE_API_BASE_URL=self.api.base_url,
                HEALTHCORE_API_USERNAME=TEST_API_EMAIL,
                HEALTHCORE_API_PASSWORD=TEST_API_PASSWORD,
            )
            api_client = HealthCoreApiClient(
                base_url=self.api.base_url,
                username=TEST_API_EMAIL,
                password=TEST_API_PASSWORD,
                http_client=self.api_http,
            )
            self.mcp = _start_mcp(create_app(settings, api_client=api_client), mcp_port)
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        if self.mcp is not None:
            self.mcp.stop()
        if self.oidc is not None:
            self.oidc.stop()
        if self.api_http is not None:
            self.api_http.close()
        if self.api is not None:
            self.api.stop()

    def _record_request(self, request: httpx.Request) -> None:
        self.requests.append((request.method.upper(), request.url.path))

    def token(self, scopes: list[str], *, client_id: str, audience: str | None = None) -> str:
        return self.oidc.mint_access_token(
            audience=audience or self.resource_url,
            scopes=scopes,
            client_id=client_id,
        )

    def inventory_snapshot(self) -> tuple[int, str]:
        login = self.api_http.post(
            "/auth/login",
            data={"username": TEST_API_EMAIL, "password": TEST_API_PASSWORD},
        )
        token = login.json()["access_token"]
        products = self.api_http.get(
            "/inventory/products",
            headers={"Authorization": f"Bearer {token}"},
        )
        orders = self.api_http.get(
            "/inventory/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        return products.status_code, products.text + orders.text


@pytest.fixture(scope="module")
def stack() -> Iterator[AcceptanceStack]:
    running = AcceptanceStack()
    try:
        yield running
    finally:
        running.stop()


def _post_mcp(stack: AcceptanceStack, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.post(
        stack.mcp.url,
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        timeout=10.0,
    )


@asynccontextmanager
async def _mcp_streams(url: str, token: str) -> AsyncIterator[tuple[object, object, object]]:
    """Open the current Streamable HTTP client with a bearer token on the HTTP client."""
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    ) as http_client:
        async with streamable_http_client(url, http_client=http_client) as streams:
            yield streams


def _metadata_url(stack: AcceptanceStack) -> str:
    parsed = httpx.URL(stack.mcp.url)
    return f"{parsed.scheme}://{parsed.host}:{parsed.port}/.well-known/oauth-protected-resource/mcp"


@pytest.fixture
def full_token(stack: AcceptanceStack) -> str:
    return stack.token(
        [SCOPE_MCP_ACCESS, SCOPE_INVENTORY_READ],
        client_id="inventory-reader",
    )


async def test_protected_resource_metadata_is_public(stack: AcceptanceStack) -> None:
    response = httpx.get(_metadata_url(stack), timeout=10.0)
    assert response.status_code == 200
    document = response.json()
    assert document["resource"] == stack.resource_url
    assert document["authorization_servers"] == [stack.oidc.issuer]
    assert document["scopes_supported"] == list(SUPPORTED_SCOPES)
    assert not stack.resource_url.endswith("/")
    assert document["bearer_methods_supported"] == ["header"]
    assert "inventory:write" not in document["scopes_supported"]


async def test_missing_token_cannot_list_tools(stack: AcceptanceStack) -> None:
    response = _post_mcp(stack)
    assert response.status_code == 401
    assert response.json()["error"] == "missing_auth_header"
    assert "resource_metadata" in response.headers["www-authenticate"]


async def test_invalid_token_is_rejected(stack: AcceptanceStack) -> None:
    response = _post_mcp(stack, {"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"


async def test_wrong_audience_is_distinct_from_invalid_token(stack: AcceptanceStack) -> None:
    token = stack.token(
        [SCOPE_MCP_ACCESS, SCOPE_INVENTORY_READ],
        client_id="wrong-audience",
        audience="http://127.0.0.1/some-other-resource",
    )
    response = _post_mcp(stack, {"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_audience"


async def test_missing_gate_scope_is_forbidden(stack: AcceptanceStack) -> None:
    token = stack.token([SCOPE_INVENTORY_READ], client_id="missing-gate")
    response = _post_mcp(stack, {"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "missing_required_scopes"
    assert body["error"] != "invalid_token"


async def test_trailing_slash_audience_is_a_different_resource(stack: AcceptanceStack) -> None:
    """`/mcp` and `/mcp/` are not the same audience."""
    token = stack.token(
        [SCOPE_MCP_ACCESS, SCOPE_INVENTORY_READ],
        client_id="trailing-slash",
        audience=f"{stack.resource_url}/",
    )
    response = _post_mcp(stack, {"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_audience"


async def test_discovery_and_inventory_read(
    stack: AcceptanceStack,
    full_token: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=INVOCATION_LOGGER_NAME)
    async with _mcp_streams(stack.mcp.url, full_token) as (read, write, _session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            by_name = {tool.name: tool for tool in listed.tools}
            assert set(by_name) == set(DISCOVERED_TOOLS)
            helper_names = {
                "_client_label",
                "_require_scope",
                "_validate_clinic_id",
                "create_app",
                "main",
            }
            assert helper_names.isdisjoint(by_name)
            query_tool = by_name[QUERY_TOOL]
            write_tool = by_name[WRITE_ATTEMPT_TOOL]
            for tool_name in DISCOVERED_TOOLS:
                discovered = by_name[tool_name]
                assert discovered.description
                assert discovered.inputSchema.get("properties")
                assert discovered.outputSchema is not None
                assert discovered.outputSchema.get("properties")
            assert "lookup" in query_tool.description
            assert query_tool.inputSchema["properties"]["lookup"]["enum"] == [
                "products",
                "product",
                "orders",
            ]
            assert query_tool.outputSchema is not None
            assert "inventory_write_forbidden" in write_tool.description
            assert write_tool.inputSchema["properties"]["action"]["type"] == "string"
            assert write_tool.outputSchema is not None
            assert write_tool.outputSchema["properties"]["modified"]["type"] == "boolean"

            listed_products = await session.call_tool(QUERY_TOOL, {"lookup": "products"})
            assert listed_products.isError is False
            products_body = listed_products.structuredContent
            assert products_body is not None
            assert products_body["ok"] is True
            assert products_body["code"] == "ok"
            gloves = next(row for row in products_body["products"] if row["sku"] == "HCR-PPE-001")
            assert gloves["current_stock"] == 103
            assert gloves["category"] == "ppe"
            assert gloves["unit"] == "box"
            assert gloves["country"] == "US"

            one_product = await session.call_tool(
                QUERY_TOOL,
                {"lookup": "product", "supply_id": gloves["id"], "clinic_id": 1},
            )
            assert one_product.structuredContent is not None
            assert one_product.structuredContent["products"][0]["clinic_current_stock"] == 68

            orders = await session.call_tool(QUERY_TOOL, {"lookup": "orders"})
            assert orders.structuredContent is not None
            assert orders.structuredContent["ok"] is True
            assert any(row["supply_sku"] == "HCR-PPE-001" for row in orders.structuredContent["orders"])

    assert "tool=query_medical_supply_inventory client=inventory-reader result=ok" in caplog.text
    assert full_token not in caplog.text
    assert TEST_API_PASSWORD not in caplog.text


async def test_tool_scope_validation_and_not_found_are_distinct(
    stack: AcceptanceStack,
    full_token: str,
) -> None:
    limited = stack.token([SCOPE_MCP_ACCESS], client_id="no-inventory-read")
    async with _mcp_streams(stack.mcp.url, limited) as (read, write, _session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            denied = await session.call_tool(QUERY_TOOL, {"lookup": "products"})
            assert denied.structuredContent is not None
            assert denied.structuredContent["code"] == "missing_required_scopes"
            assert denied.structuredContent["ok"] is False

    async with _mcp_streams(stack.mcp.url, full_token) as (read, write, _session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            invalid = await session.call_tool(
                QUERY_TOOL,
                {"lookup": "products", "clinic_id": 99},
            )
            missing = await session.call_tool(
                QUERY_TOOL,
                {"lookup": "product", "supply_id": 999999},
            )
            assert invalid.structuredContent is not None
            assert invalid.structuredContent["code"] == "validation_failed"
            assert "clinic_id" in invalid.structuredContent["message"]
            assert missing.structuredContent is not None
            assert missing.structuredContent["code"] == "inventory_not_found"
            assert invalid.structuredContent["code"] != missing.structuredContent["code"]


async def test_inventory_write_is_rejected_and_data_is_unchanged(
    stack: AcceptanceStack,
    full_token: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=INVOCATION_LOGGER_NAME)
    before_status, before_body = stack.inventory_snapshot()
    assert before_status == 200
    marker = len(stack.requests)
    async with _mcp_streams(stack.mcp.url, full_token) as (read, write, _session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            rejected = await session.call_tool(
                WRITE_ATTEMPT_TOOL,
                {
                    "action": "set_stock",
                    "supply_id": 1,
                    "stock": 1,
                    "sku": "HCR-PPE-001",
                },
            )
            unknown = await session.call_tool(
                WRITE_ATTEMPT_TOOL,
                {"action": "delete_warehouse"},
            )
    assert rejected.structuredContent is not None
    assert rejected.structuredContent["ok"] is False
    assert rejected.structuredContent["code"] == "inventory_write_forbidden"
    assert rejected.structuredContent["modified"] is False
    assert "set_stock" in rejected.structuredContent["message"]
    assert "PATCH /inventory/products/1" in rejected.structuredContent["message"]
    assert unknown.structuredContent is not None
    assert unknown.structuredContent["code"] == "validation_failed"
    assert unknown.structuredContent["modified"] is False

    inventory_writes = [
        (method, path)
        for method, path in stack.requests[marker:]
        if path.startswith("/inventory") and method != "GET"
    ]
    assert inventory_writes == []
    after_status, after_body = stack.inventory_snapshot()
    assert after_status == 200
    assert after_body == before_body
    assert (
        "tool=attempt_inventory_modification client=inventory-reader result=inventory_write_forbidden"
        in caplog.text
    )
    assert full_token not in caplog.text


def test_inventory_allowlist_rejects_post_before_http(stack: AcceptanceStack) -> None:
    marker = len(stack.requests)
    client = HealthCoreApiClient(
        base_url=stack.api.base_url,
        username=TEST_API_EMAIL,
        password=TEST_API_PASSWORD,
        http_client=stack.api_http,
    )
    with pytest.raises(ToolCallError) as caught:
        client.call_upstream(
            "POST",
            "/inventory/orders/inbound",
            json_body={"supply_id": 1, "quantity": 1, "clinic_id": 1},
        )
    assert caught.value.code.value == "inventory_write_forbidden"
    assert stack.requests[marker:] == []


async def test_stock_field_on_query_uses_the_write_allowlist(
    stack: AcceptanceStack,
    full_token: str,
) -> None:
    marker = len(stack.requests)
    async with _mcp_streams(stack.mcp.url, full_token) as (read, write, _session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            rejected = await session.call_tool(
                QUERY_TOOL,
                {"lookup": "products", "current_stock": 1},
            )
    assert rejected.structuredContent is not None
    assert rejected.structuredContent["code"] == "inventory_write_forbidden"
    inventory_calls = [
        (method, path)
        for method, path in stack.requests[marker:]
        if path.startswith("/inventory")
    ]
    assert inventory_calls == []


async def test_incident_manager_lifecycle_through_mcp(stack: AcceptanceStack) -> None:
    writer = stack.token(
        [SCOPE_MCP_ACCESS, SCOPE_INCIDENTS_READ, SCOPE_INCIDENTS_WRITE],
        client_id="incident-writer",
    )
    reader = stack.token(
        [SCOPE_MCP_ACCESS, SCOPE_INCIDENTS_READ],
        client_id="incident-reader",
    )
    async with _mcp_streams(stack.mcp.url, reader) as (read, write, _session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            denied = await session.call_tool(
                CREATE_INCIDENT_TOOL,
                {
                    "title": "Reader cannot create",
                    "description": "Missing write scope",
                    "category": "facility_issue",
                    "origin": "internal",
                    "branch": "central",
                },
            )
    assert denied.structuredContent is not None
    assert denied.structuredContent["code"] == "missing_required_scopes"

    async with _mcp_streams(stack.mcp.url, writer) as (read, write, _session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            created = await session.call_tool(
                CREATE_INCIDENT_TOOL,
                {
                    "title": "MCP acceptance ticket",
                    "description": "Created through the Incident Manager API",
                    "category": "facility_issue",
                    "origin": "internal",
                    "branch": "central",
                },
            )
            assert created.structuredContent is not None
            assert created.structuredContent["ok"] is True
            incident = created.structuredContent["incidents"][0]
            incident_id = incident["id"]
            assert incident["status"] == "open"
            assert incident["title"] == "MCP acceptance ticket"

            invalid = await session.call_tool(
                CREATE_INCIDENT_TOOL,
                {
                    "title": "Bad category",
                    "description": "This category is not allowed",
                    "category": "not_a_category",
                    "origin": "internal",
                    "branch": "central",
                },
            )
            assert invalid.structuredContent is not None
            assert invalid.structuredContent["code"] == "validation_failed"
            assert invalid.structuredContent["code"] != "missing_required_scopes"

            moved = await session.call_tool(
                UPDATE_INCIDENT_STATUS_TOOL,
                {"incident_id": incident_id, "status": "in_progress"},
            )
            assert moved.structuredContent is not None
            assert moved.structuredContent["ok"] is True
            assert moved.structuredContent["incidents"][0]["status"] == "in_progress"

            illegal = await session.call_tool(
                UPDATE_INCIDENT_STATUS_TOOL,
                {"incident_id": incident_id, "status": "open"},
            )
            assert illegal.structuredContent is not None
            assert illegal.structuredContent["code"] == "validation_failed"

            unsupported = await session.call_tool(
                QUERY_INCIDENTS_TOOL,
                {"incident_id": "HC-000001"},
            )
            assert unsupported.structuredContent is not None
            assert unsupported.structuredContent["code"] == "validation_failed"

            missing = await session.call_tool(
                QUERY_INCIDENTS_TOOL,
                {"incident_id": "00000000-0000-4000-8000-000000000001"},
            )
            assert missing.structuredContent is not None
            assert missing.structuredContent["code"] == "incident_not_found"
            assert missing.structuredContent["code"] != "invalid_token"

            found = await session.call_tool(
                QUERY_INCIDENTS_TOOL,
                {"incident_id": incident_id},
            )
            assert found.structuredContent is not None
            assert found.structuredContent["incidents"][0]["status"] == "in_progress"

            listed = await session.call_tool(
                QUERY_INCIDENTS_TOOL,
                {"status": "in_progress", "branch": "central"},
            )
            assert listed.structuredContent is not None
            assert any(
                row["id"] == incident_id for row in listed.structuredContent["incidents"]
            )


def test_agent_reads_the_ticket_through_mcp(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The API agent uses its MCP credential. The direct lookup stays disabled."""
    oidc = None
    api = None
    api_http = None
    mcp = None
    secret_title = "AGENT_LOOKUP_TITLE_QX7"
    try:
        oidc = start_oidc_issuer(_free_port())
        mcp_port = _free_port()
        resource_url = f"http://127.0.0.1:{mcp_port}/mcp"
        agent_token = oidc.mint_access_token(
            audience=resource_url,
            scopes=[SCOPE_MCP_ACCESS, SCOPE_INCIDENTS_READ],
            client_id="healthcore-agent",
        )
        api = ApiProcess(
            extra_env={
                "MCP_RESOURCE_URL": resource_url,
                "MCP_AGENT_ACCESS_TOKEN": agent_token,
            }
        )
        api_http = httpx.Client(base_url=api.base_url, timeout=30.0)
        created_user = api_http.post(
            "/users",
            json={"email": TEST_API_EMAIL, "password": TEST_API_PASSWORD},
        )
        assert created_user.status_code in (200, 201)
        settings = Settings(
            MCP_AUTH_ISSUER=oidc.issuer,
            MCP_RESOURCE_URL=resource_url,
            MCP_HOST="127.0.0.1",
            MCP_PORT=mcp_port,
            HEALTHCORE_API_BASE_URL=api.base_url,
            HEALTHCORE_API_USERNAME=TEST_API_EMAIL,
            HEALTHCORE_API_PASSWORD=TEST_API_PASSWORD,
        )
        mcp = _start_mcp(
            create_app(
                settings,
                api_client=HealthCoreApiClient(
                    base_url=api.base_url,
                    username=TEST_API_EMAIL,
                    password=TEST_API_PASSWORD,
                ),
            ),
            mcp_port,
        )
        login = api_http.post(
            "/auth/login",
            data={"username": TEST_API_EMAIL, "password": TEST_API_PASSWORD},
        )
        assert login.status_code == 200
        healthcore_token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {healthcore_token}"}
        created = api_http.post(
            "/api/incidents",
            headers=headers,
            json={
                "title": secret_title,
                "description": "Created for the agent MCP lookup",
                "category": "facility_issue",
                "origin": "internal",
                "branch": "central",
            },
        )
        assert created.status_code == 200
        incident_id = created.json()["id"]
        caplog.set_level(logging.INFO, logger=INVOCATION_LOGGER_NAME)
        answer = api_http.post(
            "/agent/query",
            headers=headers,
            json={"question": f"What is the status of incident {incident_id}?"},
        )
        assert answer.status_code == 200
        body = answer.json()["answer"]
        assert incident_id in body
        assert "open" in body
        assert "facility_issue" in body
        assert secret_title not in body
        assert secret_title not in answer.text
        assert "tool=query_incidents client=healthcore-agent result=ok" in caplog.text
        assert agent_token not in caplog.text
        assert TEST_API_PASSWORD not in caplog.text
        api_log = api.log_path.read_text(encoding="utf-8", errors="replace")
        assert agent_token not in api_log
    finally:
        if mcp is not None:
            mcp.stop()
        if api_http is not None:
            api_http.close()
        if oidc is not None:
            oidc.stop()
        if api is not None:
            api.stop()
