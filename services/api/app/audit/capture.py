"""Trusted structural metadata only. Never accept an HTTP body or profile."""

from pathlib import Path
from app.core.config import get_settings
from shared.healthcore_audit.store import AuditStore, opaque_ref


def configured_store():
    settings = get_settings()
    return AuditStore(
        settings.audit_db_path or Path(settings.tinydb_path).resolve().parent / "audit.sqlite3"
    )


def actor_metadata(user):
    return {"actor_kind": "human", "actor_ref": user.id, "actor_department_id": user.department_id}


def identify(request, user):
    request.state.audit_actor = actor_metadata(user)


def target(request, kind, reference, department_id, action=None):
    request.state.audit_target = {
        "resource_kind": kind,
        "resource_ref": opaque_ref(reference),
        "department_id": department_id,
    }
    if action:
        request.state.audit_target["action"] = action


from contextvars import ContextVar
from functools import wraps
from uuid import uuid4
from shared.healthcore_audit.store import event

audit_request_context = ContextVar("audit_request_context", default=None)
audit_process_context = ContextVar("audit_process_context", default=None)


def audited_user_change(default_action):
    """Capture direct worker/service mutations as well as HTTP mutations."""

    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            from app.services import user_service

            request = audit_request_context.get()
            process = audit_process_context.get() or "process:http-api"
            who = (
                request["state"].audit_actor
                if request
                else {"actor_kind": "process", "actor_ref": process, "actor_department_id": None}
            )
            origin = request["origin"] if request else process
            operation = request["operation"] if request else str(uuid4())
            reference = args[0] if args and isinstance(args[0], str) else kwargs.get("user_id")
            before = user_service.get_user_by_id(reference) if reference else None
            action = default_action
            payload = args[1] if len(args) > 1 else kwargs.get("payload")
            if payload is not None and {"role", "department_id"} & payload.model_fields_set:
                action = "user.assignment"
            store = configured_store()

            def append(outcome, user=None):
                return store.append(
                    event(
                        **who,
                        action=action,
                        resource_kind="user",
                        resource_ref=opaque_ref(user.id if user else reference),
                        department_id=user.department_id if user else None,
                        origin=origin,
                        context="staff_administration",
                        outcome=outcome,
                        operation_ref=operation
                    )
                )

            append("attempted", before)
            try:
                result = fn(*args, **kwargs)
            except Exception:
                append("failed", before)
                raise
            affected = result if hasattr(result, "id") else before
            append("success", affected)
            # A department transfer is relevant to both the former and new scope.
            if before and affected and before.department_id != affected.department_id:
                append("success", before)
            if request:
                request["state"].audit_domain_event = True
            return result

        return wrapped

    return decorate
