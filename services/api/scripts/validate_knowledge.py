"""Validate POST /knowledge/query reuses pipeline query() and returns answer only."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "knowledge-validation-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from app.main import app
from app.routers import knowledge as knowledge_router


def main() -> int:
    generated = "HealthCore coordinators should verify undocumented coverage with billing."

    def fake_query(question: str) -> str:
        assert question == "Which insurance is accepted?"
        return generated

    knowledge_router.pipeline_query = fake_query  # type: ignore[assignment]
    client = TestClient(app)
    response = client.post("/knowledge/query", json={"question": "Which insurance is accepted?"})
    if response.status_code != 200:
        print(f"FAIL status={response.status_code} body={response.text}")
        return 1
    body = response.json()
    if body != {"answer": generated}:
        print(f"FAIL unexpected body={body}")
        return 1
    if any(key in body for key in ("chunks", "score", "vector", "payload")):
        print(f"FAIL retrieval fields leaked: {body}")
        return 1
    print("PASS POST /knowledge/query returns generated answer only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
