-- Nightly orchestration table for Ticket #DEV-53.
-- job_runs is separate from reporting.pipeline_runs (ETL lifecycle).
-- Applied by SQLModel create_all and by app.db.database._ensure_job_runs_schema.

CREATE TABLE IF NOT EXISTS job_runs (
  id SERIAL PRIMARY KEY,
  job_name TEXT NOT NULL,
  target_date DATE NOT NULL,
  status TEXT NOT NULL
    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotency lookups are per (job_name, target_date).
CREATE INDEX IF NOT EXISTS ix_job_runs_job_name_target_date
  ON job_runs (job_name, target_date);

-- `processing` is the distributed lock. At most one row per job_name may
-- hold that status. This is not a second lock table or lock column.
CREATE UNIQUE INDEX IF NOT EXISTS ux_job_runs_job_name_processing
  ON job_runs (job_name)
  WHERE status = 'processing';
