# `services` folder

This folder contains **all the backend services** (APIs and background workers) related to the company for the cross-functional AI Engineering project.

Each subfolder inside `services/` must correspond to **one specific service** (for example: `admin-api`, `data-processor-worker`) and include its own technical and functional documentation.

- **Main purpose**: to centralize all the backend logic, APIs, and queue consumers that support the company's use cases.
- **Recommendation**: document in this file (or in sub-READMEs) the services you add, their objective, the technology used, and how to run them.

## Nightly export job control

`job_runner.py` updates `job_runs` for the independent worker `scripts/nightly_export.py`. It is not started by FastAPI. Production scheduling is OS crontab only (`infra/cron/nightly-export.crontab`). `pipeline_runs` remains the ETL control table.

## Async incident analysis (Celery)

`api/app/celery_app.py` and `api/app/tasks.py` run CSV analysis on Redis. The API returns `202` with `task_id` from `POST /api/incidents/analyze`. Poll `GET /tasks/{task_id}`. Local Compose adds `redis`, `worker`, and `flower` alongside the existing API/UI/Qdrant stack.

```bash
# From repository root (requires REDIS_URL and a worker process):
docker compose up -d redis worker flower
cd services/api && uv run celery -A app.celery_app.celery_app worker --loglevel=INFO -Q celery
```

> _Spanish version: [README.es.md](./README.es.md)._
