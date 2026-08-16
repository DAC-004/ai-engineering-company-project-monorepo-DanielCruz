"""HealthCore FastAPI application entrypoint."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.routers import auth, incidents, profiles, users  # noqa: E402

logger = logging.getLogger(__name__)

app = FastAPI(
    title="HealthCore API",
    description="Centralized HealthCore Digital API",
    version="0.2.0",
)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Keep FastAPI's 422 `detail` array so existing field parsers stay compatible."""
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return a client-safe 500 without exception text, paths, or secrets."""
    if isinstance(exc, (HTTPException, StarletteHTTPException, RequestValidationError)):
        raise exc
    logger.error("Unhandled exception: %s", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
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
app.include_router(incidents.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Public liveness probe — intentionally unauthenticated."""
    return {"status": "ok"}
