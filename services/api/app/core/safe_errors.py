"""Keep failure metadata without reflecting request or exception bodies.

CONTEXT forbids sensitive content in logs and responses. Exception text,
traceback attachments, raw validation ``input`` values, custom validator
messages, submitted dictionary keys in ``loc``, and raw URL paths can carry
that content. Callers keep status codes and short fixed messages.
"""

from __future__ import annotations

import logging
from typing import Any

# Declared schema field names and FastAPI location roots. Submitted dictionary
# keys and extra-body keys are not listed here and are replaced with "*".
_SAFE_LOC_SEGMENTS = frozenset(
    {
        "body",
        "query",
        "path",
        "header",
        "cookie",
        "question",
        "categories",
        "name",
        "country",
        "currency",
        "status",
        "monthly_rate",
        "email",
        "password",
        "events",
        "properties",
        "eventId",
        "timestamp",
        "sessionId",
        "userId",
        "event_type",
        "schemaVersion",
        "requestId",
        "title",
        "description",
        "category",
        "origin",
        "branch",
        "sku",
        "unit",
        "quantity",
        "vendor_name",
        "clinic_id",
        "supply_id",
        "consumption_type",
        "department",
        "contract_renewal_date",
        "compliance_agreement",
        "contact_email",
        "notes",
        "phone",
        "address",
        "is_active",
        "role",
        "decision",
        "note",
        "resolution",
        "expiry_date",
        "minimum_stock",
        "text",
        "token",
        "session_id",
        "new_input",
        "id",
        "field",
        "message",
        "detail",
    }
)

_SAFE_MSG_BY_TYPE: dict[str, str] = {
    "missing": "Field required.",
    "string_type": "Expected a string.",
    "list_type": "Expected a list.",
    "dict_type": "Expected an object.",
    "int_type": "Expected an integer.",
    "int_parsing": "Expected an integer.",
    "float_type": "Expected a number.",
    "float_parsing": "Expected a number.",
    "bool_type": "Expected a boolean.",
    "bool_parsing": "Expected a boolean.",
    "literal_error": "Value is not an allowed option.",
    "enum": "Value is not an allowed option.",
    "extra_forbidden": "Unexpected field.",
    "value_error": "Invalid value.",
    "greater_than": "Value is out of range.",
    "greater_than_equal": "Value is out of range.",
    "less_than": "Value is out of range.",
    "less_than_equal": "Value is out of range.",
    "string_too_short": "Value is too short.",
    "string_too_long": "Value is too long.",
    "too_short": "Value is too short.",
    "too_long": "Value is too long.",
    "json_invalid": "The request body must be valid JSON.",
}


def log_failure(logger: logging.Logger, message: str, *args: object) -> None:
    """Record that a failure occurred without attaching ``exc_info``."""
    logger.error(message, *args)


def safe_route_template(request: Any) -> str:
    """Return the matched route template, or ``<unmatched>``.

    ``request.url.path`` can contain submitted path segments. The Starlette
    route ``path`` attribute is the template (for example ``/items/{item_id}``).
    """
    route = getattr(request, "scope", {}).get("route")
    if route is None:
        return "<unmatched>"
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return "<unmatched>"


def _safe_validation_message(error_type: str) -> str:
    if error_type in _SAFE_MSG_BY_TYPE:
        return _SAFE_MSG_BY_TYPE[error_type]
    if error_type.endswith("_type"):
        return "Value has the wrong type."
    if "missing" in error_type:
        return "Field required."
    if "parsing" in error_type:
        return "Value could not be parsed."
    return "Invalid value."


def _safe_loc(loc: Any) -> list[Any]:
    if not isinstance(loc, (list, tuple)):
        return ["body"]
    sanitized: list[Any] = []
    for part in loc:
        if isinstance(part, int):
            sanitized.append(part)
            continue
        text = str(part)
        if text in _SAFE_LOC_SEGMENTS:
            sanitized.append(text)
            continue
        # Submitted dictionary keys and extra-body keys are not schema fields.
        sanitized.append("*")
    return sanitized


def public_validation_errors(errors: list[Any]) -> list[dict[str, Any]]:
    """Keep type and a safe location. Replace ``msg``. Drop ``input`` and ``ctx``.

    Custom validator text and submitted dictionary keys must not leave the
    process. Schema field names and list indexes remain for client guidance.
    """
    sanitized: list[dict[str, Any]] = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        error_type = str(item.get("type") or "value_error")
        entry: dict[str, Any] = {
            "type": error_type,
            "loc": _safe_loc(item.get("loc")),
            "msg": _safe_validation_message(error_type),
        }
        sanitized.append(entry)
    return sanitized
