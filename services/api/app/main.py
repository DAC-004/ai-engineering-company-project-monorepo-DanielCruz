"""HealthCore FastAPI application entrypoint."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGES_SHARED = REPO_ROOT / "packages" / "shared"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(PACKAGES_SHARED) not in sys.path:
    sys.path.insert(0, str(PACKAGES_SHARED))

from app.routers import auth, incident_manager, incidents, profiles, users  # noqa: E402
from app.services.incident_service import (  # noqa: E402
    IncidentFieldError,
    IncidentNotFoundError,
)

logger = logging.getLogger("healthcore.api")

app = FastAPI(
    title="HealthCore API",
    description="Centralized HealthCore Digital API",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profiles.router)
# Analyzer static paths (/results, /analyze) must be registered before /{id}.
app.include_router(incidents.router)
app.include_router(incident_manager.router)


def _is_manager_write_request(request: Request) -> bool:
    """True for assignment-defined manager create/status bodies that must be 400."""
    path = request.url.path.rstrip("/")
    if request.method == "POST" and path == "/api/incidents":
        return True
    if (
        request.method == "PATCH"
        and path.startswith("/api/incidents/")
        and path.endswith("/status")
    ):
        return True
    return False


def _field_from_validation_error(error: dict) -> str:
    location = error.get("loc") or ()
    for part in location:
        if part in {"body", "query", "path"}:
            continue
        return str(part)
    return "request"


def _plain_message_for_validation_error(field: str, error: dict) -> str:
    label = field.replace("_", " ").title() if field != "request" else "This request"
    error_type = str(error.get("type") or "")
    if error_type == "missing":
        return f"{label} is required."
    if "json" in error_type:
        return "The request body must be valid JSON."
    return f"{label} is not valid."


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Manager write validation is HTTP 400. Other routes keep FastAPI 422."""
    if not _is_manager_write_request(request):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    first = exc.errors()[0] if exc.errors() else {}
    field = _field_from_validation_error(first)
    message = _plain_message_for_validation_error(field, first)
    return JSONResponse(status_code=400, content={"field": field, "message": message})


@app.exception_handler(IncidentFieldError)
async def incident_field_error_handler(
    _request: Request,
    exc: IncidentFieldError,
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"field": exc.field, "message": exc.message},
    )


@app.exception_handler(IncidentNotFoundError)
async def incident_not_found_handler(
    _request: Request,
    _exc: IncidentNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"field": "id", "message": "That incident was not found."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never expose a stack trace. HTTPException keeps its own status/body."""
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred. Please try again."},
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Public liveness probe — intentionally unauthenticated."""
    return {"status": "ok"}
