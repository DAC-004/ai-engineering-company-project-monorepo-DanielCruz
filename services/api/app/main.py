"""HealthCore FastAPI application entrypoint."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.db.database import get_engine, init_databases  # noqa: E402
from app.routers import auth, incidents, inventory, profiles, telemetry, users  # noqa: E402
from app.services.inventory_seed import seed_inventory_if_empty  # noqa: E402
from data.pipelines.reporting_store import ensure_reporting_tables  # noqa: E402
from services.reporting.router import router as reporting_router  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Open TinyDB + Supabase engines, create inventory tables, then seed if empty."""
    init_databases()
    ensure_reporting_tables(get_engine())
    with Session(get_engine()) as session:
        seed_inventory_if_empty(session)
    yield


app = FastAPI(
    title="HealthCore API",
    description="Centralized HealthCore Digital API",
    version="0.3.0",
    lifespan=lifespan,
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
app.include_router(inventory.router)
app.include_router(telemetry.router)
app.include_router(reporting_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Public liveness probe — intentionally unauthenticated."""
    return {"status": "ok"}
