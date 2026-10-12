"""Acceptance checks for the HealthCore MCP server against the real inventory API."""

from __future__ import annotations

import ctypes
import json
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


class ApiProcessCleanupError(RuntimeError):
    """Raised when owned API processes or the owned listener were not released."""


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


def _services_api_venv_python() -> Path:
    """Return the services/api virtualenv interpreter (must exist before ApiProcess starts)."""
    if os.name == "nt":
        candidate = API_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = API_DIR / ".venv" / "bin" / "python"
    if not candidate.is_file():
        raise FileNotFoundError(
            f"HealthCore API virtualenv interpreter not found at {candidate}. "
            "Run `uv sync` in services/api before MCP acceptance."
        )
    resolved = candidate.resolve()
    venv_root = (API_DIR / ".venv").resolve()
    if venv_root not in resolved.parents:
        raise RuntimeError(
            f"Interpreter {resolved} is not under services/api virtualenv {venv_root}"
        )
    return resolved


def _api_launch_command(port: int) -> list[str]:
    uvicorn_args = [
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    if os.name == "nt":
        return [str(_services_api_venv_python()), *uvicorn_args]
    return ["uv", "run", *uvicorn_args]


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"exit [int](-not (Get-Process -Id {pid} -ErrorAction SilentlyContinue))",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return result.returncode == 0
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _windows_process_row(pid: int) -> dict[str, object] | None:
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                f"$p = Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\" | "
                "Select-Object ProcessId, ParentProcessId, CommandLine, ExecutablePath; "
                "if ($null -eq $p) {{ exit 1 }}; "
                "$p | ConvertTo-Json -Compress"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        return None
    payload = json.loads(result.stdout.strip())
    if not isinstance(payload, dict):
        return None
    return payload


def _parent_chain_contains(pid: int, ancestor_pid: int, *, max_depth: int = 32) -> bool:
    if pid <= 0 or ancestor_pid <= 0:
        return False
    current = pid
    for _ in range(max_depth):
        if current == ancestor_pid:
            return True
        row = _windows_process_row(current)
        if row is None:
            return False
        parent = int(row.get("ParentProcessId", 0))
        if parent <= 0:
            return False
        current = parent
    return False


def _launcher_command_line_binds_port(row: dict[str, object], port: int, venv_python: Path) -> bool:
    command = str(row.get("CommandLine") or "")
    executable = str(row.get("ExecutablePath") or "")
    if str(port) not in command:
        return False
    if "uvicorn" not in command or "app.main:app" not in command:
        return False
    venv_markers = {venv_python.name.lower(), str(venv_python).lower(), str(venv_python.resolve()).lower()}
    haystack = f"{command} {executable}".lower()
    if not any(marker and marker in haystack for marker in venv_markers):
        return False
    return True


def _windows_process_tree_pids(root_pid: int) -> set[int]:
    """Collect root_pid and its descendant PIDs using Win32_Process parent links."""
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "$rows = Get-CimInstance Win32_Process | "
                "Select-Object ProcessId, ParentProcessId; "
                "$rows | ConvertTo-Json -Compress"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    payload = json.loads(result.stdout.strip() or "[]")
    if isinstance(payload, dict):
        payload = [payload]
    children: dict[int, list[int]] = {}
    for row in payload:
        pid = int(row["ProcessId"])
        parent = int(row["ParentProcessId"])
        children.setdefault(parent, []).append(pid)
    owned = {root_pid}
    pending = [root_pid]
    while pending:
        current = pending.pop()
        for child in children.get(current, []):
            if child not in owned:
                owned.add(child)
                pending.append(child)
    return owned


def _owned_process_snapshot(root_pid: int) -> set[int]:
    """Snapshot PIDs tied to this ApiProcess launch.

    On Windows, walks the Win32 parent graph from the recorded root PID at capture
    time so descendants spawned after health are included before shutdown.
    On other platforms only the direct Popen PID is tracked (no tree walk).
    """
    if os.name == "nt":
        return _windows_process_tree_pids(root_pid)
    return {root_pid}


def _port_is_available(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", port))
    except OSError:
        return False
    return True


if os.name == "nt":
    _KERNEL32: ctypes.WinDLL | None = ctypes.WinDLL("kernel32", use_last_error=True)
else:
    _KERNEL32 = None


if os.name == "nt":
    _STILL_ACTIVE = 259
    _PROCESS_TERMINATE = 0x0001
    _SYNCHRONIZE = 0x00100000
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _KERNEL32.GetProcessId.argtypes = [ctypes.c_void_p]
    _KERNEL32.GetProcessId.restype = ctypes.c_uint32
    _KERNEL32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    _KERNEL32.OpenProcess.restype = ctypes.c_void_p
    _KERNEL32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _KERNEL32.TerminateProcess.restype = ctypes.c_int
    _KERNEL32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    _KERNEL32.GetExitCodeProcess.restype = ctypes.c_int
    _KERNEL32.CloseHandle.argtypes = [ctypes.c_void_p]
    _KERNEL32.CloseHandle.restype = ctypes.c_int
    _KERNEL32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _KERNEL32.WaitForSingleObject.restype = ctypes.c_uint32
    _KERNEL32.GetCurrentProcess.argtypes = []
    _KERNEL32.GetCurrentProcess.restype = ctypes.c_void_p
    _KERNEL32.DuplicateHandle.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint32,
    ]
    _KERNEL32.DuplicateHandle.restype = ctypes.c_int
    _DUPLICATE_SAME_ACCESS = 0x00000002


class _WindowsOwnedProcessHandle:
    """Kernel handle to one API launcher process captured while lineage was valid."""

    def __init__(self, pid_at_registration: int, handle: int) -> None:
        self.pid_at_registration = pid_at_registration
        self.handle = handle

    def identity_matches(self) -> bool:
        if not self.handle:
            return False
        return int(_KERNEL32.GetProcessId(self.handle)) == self.pid_at_registration

    def is_still_running(self) -> bool:
        if not self.handle or not self.identity_matches():
            return False
        exit_code = ctypes.c_uint32()
        if not _KERNEL32.GetExitCodeProcess(self.handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == _STILL_ACTIVE

    def terminate(self) -> None:
        if self.handle and self.identity_matches() and self.is_still_running():
            _KERNEL32.TerminateProcess(self.handle, 1)

    def close(self) -> None:
        if self.handle:
            _KERNEL32.CloseHandle(self.handle)
            self.handle = 0


class _WindowsProcessRegistry:
    """Registers OpenProcess handles for the Popen root and verified descendants.

    Termination uses only registered handles (never taskkill /T by numeric PID).
    """

    def __init__(
        self,
        *,
        root_pid: int,
        port: int,
        venv_python: Path,
        popen: subprocess.Popen[bytes],
    ) -> None:
        self._root_pid = root_pid
        self._port = port
        self._venv_python = venv_python
        self._popen = popen
        self._entries: dict[int, _WindowsOwnedProcessHandle] = {}

    def registered_pids(self) -> set[int]:
        return set(self._entries)

    def _corroborate_launcher_pid(self, pid: int) -> bool:
        if pid == self._root_pid:
            return self._popen.pid == pid
        if pid not in _windows_process_tree_pids(self._root_pid):
            return False
        row = _windows_process_row(pid)
        if row is None:
            return False
        if not _launcher_command_line_binds_port(row, self._port, self._venv_python):
            return False
        return _parent_chain_contains(pid, self._root_pid)

    def _open_registration_handle(self, pid: int) -> int:
        """Open a handle bound to the process instance corroborated for ``pid``.

        The root uses DuplicateHandle on the Popen-owned handle (same kernel object
        as ``subprocess.Popen``). Descendants use OpenProcess immediately after
        corroboration in this call (minimal discover→open gap).
        """
        if pid == self._root_pid:
            popen_handle = getattr(self._popen, "_handle", None)
            if popen_handle is not None:
                source = ctypes.c_void_p(int(popen_handle))
                if int(_KERNEL32.GetProcessId(source)) != pid:
                    return 0
                duplicated = ctypes.c_void_p()
                ok = _KERNEL32.DuplicateHandle(
                    _KERNEL32.GetCurrentProcess(),
                    source,
                    _KERNEL32.GetCurrentProcess(),
                    ctypes.byref(duplicated),
                    0,
                    False,
                    _DUPLICATE_SAME_ACCESS,
                )
                if ok and duplicated.value:
                    return int(duplicated.value)
        return int(
            _KERNEL32.OpenProcess(
                _PROCESS_TERMINATE | _SYNCHRONIZE | _PROCESS_QUERY_LIMITED_INFORMATION,
                False,
                pid,
            )
            or 0
        )

    def register_pid(self, pid: int) -> bool:
        if pid in self._entries:
            return self._entries[pid].identity_matches()
        if not self._corroborate_launcher_pid(pid):
            return False
        handle = self._open_registration_handle(pid)
        if not handle:
            return False
        if int(_KERNEL32.GetProcessId(handle)) != pid:
            _KERNEL32.CloseHandle(handle)
            return False
        if pid == self._root_pid and self._popen.pid != pid:
            _KERNEL32.CloseHandle(handle)
            return False
        self._entries[pid] = _WindowsOwnedProcessHandle(pid, handle)
        return True

    def register_launch_tree(self) -> None:
        if not _pid_is_running(self._root_pid):
            return
        self.register_pid(self._root_pid)
        for pid in _owned_process_snapshot(self._root_pid):
            self.register_pid(pid)

    def terminate_registered(self) -> None:
        if self._popen.poll() is None:
            self._popen.terminate()
            try:
                self._popen.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        self.register_launch_tree()
        for pid in sorted(self._entries, reverse=True):
            self._entries[pid].terminate()
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if not any(entry.is_still_running() for entry in self._entries.values()):
                break
            time.sleep(0.15)

    def survivor_pids(self) -> list[int]:
        return sorted(
            pid
            for pid, entry in self._entries.items()
            if entry.identity_matches() and entry.is_still_running()
        )

    def close_all(self) -> None:
        for entry in self._entries.values():
            entry.close()
        self._entries.clear()


class ApiProcess:
    """The existing HealthCore API, started with its own uv environment."""

    def __init__(self, extra_env: dict[str, str] | None = None) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="healthcore-mcp-"))
        self.port = _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.log_path = self.temp_dir / "api.log"
        self.log_file = self.log_path.open("w", encoding="utf-8")
        self._root_pid: int | None = None
        self._owned_pids: set[int] = set()
        self._cleanup_succeeded = False
        self._venv_python = _services_api_venv_python()
        self._windows_registry: _WindowsProcessRegistry | None = None
        self.process: subprocess.Popen[bytes] | None = None
        env = os.environ.copy()
        env["SECRET_KEY"] = "mcp-acceptance-secret-key-32"
        env["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
        env["JWT_ALGORITHM"] = "HS256"
        env["TINYDB_PATH"] = str(self.temp_dir / "auth.json")
        env["DATABASE_URL"] = f"sqlite:///{(self.temp_dir / 'inventory.db').resolve().as_posix()}"
        if extra_env:
            env.update(extra_env)
        try:
            self.process = subprocess.Popen(
                _api_launch_command(self.port),
                cwd=API_DIR,
                env=env,
                stdout=self.log_file,
                stderr=subprocess.STDOUT,
            )
            self._root_pid = self.process.pid
            self._wait_until_healthy()
        except Exception:
            self.stop()
            raise

    def _wait_until_healthy(self) -> None:
        assert self.process is not None
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
                self._register_owned_windows_processes()
                return
            last_error = f"HTTP {response.status_code}"
            time.sleep(0.2)
        log_text = self.log_path.read_text(encoding="utf-8", errors="replace")
        raise RuntimeError(
            f"HealthCore API did not start ({last_error}). Log:\n{log_text[-2000:]}"
        )

    def _register_owned_windows_processes(self) -> None:
        if os.name != "nt" or self.process is None or self._root_pid is None:
            self._owned_pids = (
                _owned_process_snapshot(self._root_pid) if self._root_pid is not None else set()
            )
            return
        if self._windows_registry is None:
            self._windows_registry = _WindowsProcessRegistry(
                root_pid=self._root_pid,
                port=self.port,
                venv_python=self._venv_python,
                popen=self.process,
            )
        self._windows_registry.register_launch_tree()
        self._owned_pids = self._windows_registry.registered_pids()

    def _shutdown_windows_owned_tree(self) -> None:
        assert self.process is not None
        assert self._root_pid is not None
        if self._windows_registry is None:
            self._windows_registry = _WindowsProcessRegistry(
                root_pid=self._root_pid,
                port=self.port,
                venv_python=self._venv_python,
                popen=self.process,
            )
        self._windows_registry.register_launch_tree()
        self._owned_pids = self._windows_registry.registered_pids()
        self._windows_registry.terminate_registered()
        self._owned_pids = self._windows_registry.registered_pids()

    def _shutdown_process(self) -> None:
        if self.process is None:
            return
        if os.name == "nt" and self._root_pid is not None:
            self._shutdown_windows_owned_tree()
            return

        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def _verify_cleanup(self) -> None:
        if os.name == "nt" and self._windows_registry is not None:
            survivors = self._windows_registry.survivor_pids()
        else:
            survivors = sorted(pid for pid in self._owned_pids if _pid_is_running(pid))
        port_busy = not _port_is_available(self.port)
        if survivors or port_busy:
            raise ApiProcessCleanupError(
                "Owned API teardown incomplete "
                f"(survivor_pids={survivors}, port={self.port}, "
                f"port_released={not port_busy}, root_pid={self._root_pid})"
            )

    def stop(self) -> None:
        if self._cleanup_succeeded:
            return
        error: BaseException | None = None
        try:
            self._shutdown_process()
            self._verify_cleanup()
            self._cleanup_succeeded = True
        except BaseException as exc:
            error = exc
        finally:
            if self._windows_registry is not None:
                self._windows_registry.close_all()
            if not self.log_file.closed:
                self.log_file.close()
        if error is not None:
            raise error


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
