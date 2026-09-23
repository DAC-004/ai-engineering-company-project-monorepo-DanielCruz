"""Exit B checks for the integrated incident manager.

The lookup is not monkeypatched. The test inserts and later changes status
through the incident service. Isolated TinyDB data is discarded afterward.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.graph import compile_support_graph, run_support_agent
from app.core.config import get_settings
from app.db.database import reset_engine_for_tests
from app.db.tinydb import reset_db_for_tests
from app.main import app
from app.routers import agent as agent_router
from app.routers import incident_manager
from app.schemas.incident import IncidentCreate, IncidentPublic
from app.services import incident_service
from app.services.ticket_lookup import TicketLookupQuery, lookup_ticket

ANALYZER_PATHS = (
    "/api/incidents/analyze",
    "/api/incidents/results",
    "/api/incidents/results/summary",
    "/api/incidents/results/export",
)


@pytest.fixture
def isolated_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point settings at temp files and drop cached handles after the test."""
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "incidents.json"))
    monkeypatch.setenv("SECRET_KEY", "isolated-phase2-secret-key-32b")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'inventory.db').as_posix()}")
    get_settings.cache_clear()
    reset_db_for_tests()
    reset_engine_for_tests()
    yield
    reset_db_for_tests()
    reset_engine_for_tests()
    get_settings.cache_clear()


def test_one_process_imports_graph_and_manager_reads() -> None:
    assert callable(compile_support_graph)
    assert callable(run_support_agent)
    assert callable(incident_service.get_incident)
    assert callable(incident_service.list_incidents)


def _registered_paths() -> list[str]:
    """Paths in include order. This FastAPI build keeps each router nested."""
    paths: list[str] = []
    for route in app.routes:
        original = getattr(route, "original_router", None)
        nested_routes = original.routes if original is not None else [route]
        for nested in nested_routes:
            path = getattr(nested, "path", None)
            if isinstance(path, str):
                paths.append(path)
    return paths


def test_analyzer_routes_are_registered_before_incident_id() -> None:
    incident_paths = [path for path in _registered_paths() if path.startswith("/api/incidents")]
    id_index = incident_paths.index("/api/incidents/{incident_id}")
    for analyzer_path in ANALYZER_PATHS:
        assert incident_paths.index(analyzer_path) < id_index


def test_agent_route_does_not_call_the_incident_service() -> None:
    agent_source = Path(agent_router.__file__).read_text(encoding="utf-8")
    graph_source = Path(compile_support_graph.__code__.co_filename).read_text(encoding="utf-8")
    assert "incident_service" not in agent_source
    assert "lookup_ticket" not in agent_source
    assert "incident_service" not in graph_source
    assert "lookup_ticket" not in graph_source


def test_typed_contract_matches_integrated_manager() -> None:
    assert set(TicketLookupQuery.model_fields) == {
        "incident_id",
        "status",
        "origin",
        "branch",
        "category",
    }
    assert set(IncidentPublic.model_fields) == {
        "id",
        "title",
        "description",
        "category",
        "status",
        "origin",
        "branch",
        "created_at",
        "updated_at",
    }
    service_reads = (
        incident_service.get_incident.__code__.co_names
        + incident_service.list_incidents.__code__.co_names
    )
    assert "get_current_user" not in service_reads
    router_source = Path(incident_manager.__file__).read_text(encoding="utf-8")
    assert "get_current_user" in router_source
    lookup_names = lookup_ticket.__code__.co_names
    assert "get_incident" in lookup_names
    assert "list_incidents" in lookup_names
    assert "create_incident" not in lookup_names
    assert "update_incident_status" not in lookup_names


def test_unpatched_lookup_sees_a_real_status_change(isolated_stores: None) -> None:
    created = incident_service.create_incident(
        IncidentCreate(
            title="Isolated pump alarm",
            description="Phase 2 lookup fixture",
            category="clinical_equipment",
            status="open",
            origin="branch",
            branch="central",
        )
    )

    first_lookup = lookup_ticket(TicketLookupQuery(incident_id=created.id))
    first_read = incident_service.get_incident(created.id)
    assert len(first_lookup) == 1
    assert first_lookup[0].model_dump() == first_read.model_dump()
    assert first_lookup[0].status == "open"

    listed = lookup_ticket(
        TicketLookupQuery(status="open", origin="branch", branch="central", category="clinical_equipment")
    )
    assert [row.id for row in listed] == [created.id]

    incident_service.update_incident_status(created.id, "in_progress")

    second_lookup = lookup_ticket(TicketLookupQuery(incident_id=created.id))
    second_read = incident_service.get_incident(created.id)
    assert second_lookup[0].model_dump() == second_read.model_dump()
    assert second_lookup[0].status == "in_progress"
    assert second_lookup[0].title == second_read.title
    assert lookup_ticket(TicketLookupQuery(status="open")) == []
    assert [row.id for row in lookup_ticket(TicketLookupQuery(status="in_progress"))] == [created.id]
