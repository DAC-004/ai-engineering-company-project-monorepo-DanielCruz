"""Capture attempts before operations and outcomes before returning responses."""

from __future__ import annotations
import ipaddress, logging
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import compile_path
from starlette.concurrency import run_in_threadpool
from app.core.deps import get_current_user
from app.audit.capture import actor_metadata, configured_store, audit_request_context
from shared.healthcore_audit.store import AuditError, event, opaque_ref

logger = logging.getLogger(__name__)
FAMILIES = (
    ("/auth", "auth"),
    ("/audit-log", "audit"),
    ("/users", "user"),
    ("/roles", "role"),
    ("/departments", "department"),
    ("/access", "department"),
    ("/profiles", "profile"),
    ("/internal-reports", "internal_report"),
    ("/api/incidents", "incident"),
    ("/inventory", "inventory"),
    ("/supplier-contracts", "supplier"),
    ("/suppliers", "supplier"),
    ("/rfp", "rfp"),
    ("/onboarding", "onboarding"),
    ("/financial-close", "financial_close"),
    ("/agent", "agent"),
    ("/knowledge", "knowledge"),
    ("/tasks", "task"),
    ("/reports", "report"),
    ("/reporting", "report"),
)


def classification(path, method):
    kind = next(
        (kind for prefix, kind in FAMILIES if path == prefix or path.startswith(prefix + "/")), None
    )
    if kind is None:
        return None
    verb = {
        "GET": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }.get(method)
    if not verb:
        return None
    action = f"{kind}.{verb}"
    context = "routine_review" if method == "GET" else "resource_change"
    if kind in {"user", "role", "department"}:
        context = "staff_administration"
    if kind == "auth":
        context = "authentication"
        specific = {
            "/auth/login": "auth.login",
            "/auth/forgot-password": "auth.password_reset_requested",
            "/auth/reset-password": "auth.password_reset",
            "/auth/change-password": "auth.password_change",
        }
        action = specific.get(path, action)
        if path.endswith("/callback"):
            action = "auth.federated_login"
        elif path.endswith("/start"):
            action = "auth.federated_start"
        elif method == "DELETE":
            action = "auth.federated_unlink"
    if "/export" in path or path.endswith("/final-document"):
        context = "data_export"
    if kind in {"agent", "knowledge"} and method == "POST":
        action = f"{kind}.execute"
        context = "automated_processing"
    if kind == "audit":
        context = "audit_review"
        action = "audit.verify" if path.endswith("/integrity") else "audit.read"
    return kind, action, context


class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, route_templates):
        super().__init__(app)
        self.templates = [
            (
                path,
                compile_path(path)[0],
                {
                    method.upper()
                    for method in methods
                    if method.lower()
                    in {"get", "post", "put", "patch", "delete", "head", "options"}
                },
            )
            for path, methods in route_templates.items()
        ]

    async def dispatch(self, request, call_next):
        match = None
        # Public OpenAPI route templates avoid relying on FastAPI's internal
        # included-router wrappers, which are not Starlette APIRoutes.
        for path, pattern, methods in self.templates:
            matched = pattern.fullmatch(request.url.path)
            if matched and request.method in methods:
                match = (path, matched.groupdict())
                break
        spec = classification(match[0], request.method) if match else None
        if spec is None:
            return await call_next(request)
        kind, action, context = spec
        actor = {"actor_kind": "anonymous", "actor_ref": str(uuid4()), "actor_department_id": None}
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            try:
                user = await run_in_threadpool(get_current_user, header.split(" ", 1)[1])
                actor = actor_metadata(user)
            except Exception:
                pass  # Invalid bearer stays anonymous; the real dependency enforces access.
        request.state.audit_actor = actor
        operation = str(uuid4())
        origin = request.client.host if request.client else ""
        try:
            origin = str(ipaddress.ip_address(origin))
        except ValueError:
            origin = "process:http-api"
        params = match[1]
        reference = next(
            (value for key, value in reversed(list(params.items())) if key not in {"provider"}),
            None,
        )
        defaults = {
            "resource_kind": kind,
            "resource_ref": opaque_ref(reference),
            "department_id": actor["actor_department_id"],
        }
        store = configured_store()

        def append(outcome, status=None):
            who = request.state.audit_actor
            resource = {**defaults, **getattr(request.state, "audit_target", {})}
            return store.append(
                event(
                    **who,
                    action=resource.pop("action", action),
                    **resource,
                    origin=origin,
                    context=context,
                    outcome=outcome,
                    operation_ref=operation,
                    status_code=status,
                )
            )

        try:
            await run_in_threadpool(append, "attempted")
        except (AuditError, ValueError):
            return JSONResponse(
                status_code=503,
                content={"detail": "Audit storage unavailable; operation not started"},
            )
        try:
            token = audit_request_context.set(
                {"state": request.state, "origin": origin, "operation": operation}
            )
            try:
                response = await call_next(request)
            finally:
                audit_request_context.reset(token)
        except Exception:
            try:
                await run_in_threadpool(append, "failed", 500)
            except (AuditError, ValueError):
                logger.error("audit_outcome_unavailable")
            raise
        outcome = (
            "success"
            if response.status_code < 400
            else "denied" if response.status_code < 500 else "failed"
        )
        try:
            if not (
                getattr(request.state, "audit_domain_event", False) and response.status_code < 400
            ):
                await run_in_threadpool(append, outcome, response.status_code)
            if (
                kind in {"agent", "knowledge"}
                and request.method == "POST"
                and response.status_code < 500
            ):
                who = request.state.audit_actor
                process = event(
                    actor_kind="process",
                    actor_ref="process:support-agent",
                    initiator_ref=who["actor_ref"] if who["actor_kind"] == "human" else None,
                    actor_department_id=None,
                    action="agent.execute",
                    resource_kind=kind,
                    resource_ref=operation,
                    department_id=who["actor_department_id"],
                    origin="process:support-agent",
                    context="automated_processing",
                    outcome=outcome,
                    operation_ref=operation,
                    status_code=response.status_code,
                )
                await run_in_threadpool(store.append, process)
        except (AuditError, ValueError):
            logger.error("audit_outcome_unavailable")
            return JSONResponse(
                status_code=503,
                content={"detail": "Audit outcome unavailable; inspect operation before retrying"},
            )
        return response
