FROM python:3.13-slim-bookworm

ENV UV_SYSTEM_PYTHON=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/services/api

RUN pip install --no-cache-dir uv

COPY api/requirements.docker.txt ./requirements.docker.txt
RUN sed '/^-e \.$/d' requirements.docker.txt > requirements.txt \
    && uv pip install --system -r requirements.txt

COPY api/ ./
COPY reporting/ /app/services/reporting/
COPY telemetry/ /app/services/telemetry/
COPY __init__.py /app/services/__init__.py

# Dependency smoke only: reporting.router also needs repo-root data/ at runtime.
RUN python -c "import pandas, prefect; import services.reporting, services.telemetry"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
