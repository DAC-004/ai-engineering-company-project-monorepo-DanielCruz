"""Stable error codes returned by MCP Auth and by HealthCore tools.

Authentication and authorization failures are produced by mcpauth bearer
middleware as HTTP responses. Validation and inventory-write failures are
produced by the tool itself so an external agent can read the code without
guessing from a generic exception string.
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """Distinct failure codes. Do not collapse these into a single 'error'."""

    MISSING_AUTH_HEADER = "missing_auth_header"
    INVALID_AUTH_HEADER_FORMAT = "invalid_auth_header_format"
    MISSING_BEARER_TOKEN = "missing_bearer_token"
    INVALID_TOKEN = "invalid_token"
    INVALID_ISSUER = "invalid_issuer"
    INVALID_AUDIENCE = "invalid_audience"
    MISSING_REQUIRED_SCOPES = "missing_required_scopes"
    VALIDATION_FAILED = "validation_failed"
    INVENTORY_WRITE_FORBIDDEN = "inventory_write_forbidden"
    INVENTORY_NOT_FOUND = "inventory_not_found"
    INCIDENT_NOT_FOUND = "incident_not_found"
    UPSTREAM_AUTH_FAILED = "upstream_auth_failed"
    UPSTREAM_REQUEST_FAILED = "upstream_request_failed"


# mcpauth maps these bearer codes to HTTP status. Tool-level scope checks reuse
# the same authorization code so clients see one vocabulary.
HTTP_STATUS_BY_AUTH_CODE: dict[ErrorCode, int] = {
    ErrorCode.MISSING_AUTH_HEADER: 401,
    ErrorCode.INVALID_AUTH_HEADER_FORMAT: 401,
    ErrorCode.MISSING_BEARER_TOKEN: 401,
    ErrorCode.INVALID_TOKEN: 401,
    ErrorCode.INVALID_ISSUER: 401,
    ErrorCode.INVALID_AUDIENCE: 401,
    ErrorCode.MISSING_REQUIRED_SCOPES: 403,
}


class ToolCallError(Exception):
    """Controlled tool failure with a documented code and a client-safe message."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
