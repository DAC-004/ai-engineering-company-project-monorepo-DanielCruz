# `services` folder

This folder contains **all the backend services** (APIs and background workers) related to the company for the cross-functional AI Engineering project.

Each subfolder inside `services/` must correspond to **one specific service** (for example: `admin-api`, `data-processor-worker`) and include its own technical and functional documentation.

- **Main purpose**: to centralize all the backend logic, APIs, and queue consumers that support the company's use cases.
- **Recommendation**: document in this file (or in sub-READMEs) the services you add, their objective, the technology used, and how to run them.

Current services:

- `api/` — HealthCore FastAPI app (JWT, inventory, incident analysis).
- Celery worker for `POST /api/incidents/analyze` — run from `services/api` as documented in the repository-root README (`uv run celery -A app.celery_app:celery_app worker --pool=solo -Q celery -E`). Not inside the uvicorn process.


> _Spanish version: [README.es.md](./README.es.md)._
