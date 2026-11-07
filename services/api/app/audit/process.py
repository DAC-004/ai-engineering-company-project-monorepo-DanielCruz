"""Audit real worker executions without copying arguments, results or errors."""

from functools import wraps
from uuid import uuid4
from app.audit.capture import configured_store, audit_process_context
from shared.healthcore_audit.store import event, opaque_ref


def audited_process(process, department):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            task = args[0] if args else None
            task_id = getattr(getattr(task, "request", None), "id", None)
            operation = str(uuid4())
            fields = dict(
                actor_kind="process",
                actor_ref=process,
                action="task.execute",
                resource_kind="task",
                resource_ref=opaque_ref(task_id) or operation,
                department_id=department,
                origin=process,
                context="automated_processing",
                operation_ref=operation,
            )
            store = configured_store()
            store.append(event(**fields, outcome="attempted"))
            try:
                token = audit_process_context.set(process)
                try:
                    result = fn(*args, **kwargs)
                finally:
                    audit_process_context.reset(token)
            except BaseException:
                store.append(event(**fields, outcome="failed"))
                raise
            store.append(event(**fields, outcome="success"))
            return result

        return wrapped

    return decorate
