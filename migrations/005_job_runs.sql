CREATE TABLE IF NOT EXISTS job_runs (
    job_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    trigger TEXT NOT NULL,
    schedule_id TEXT,
    target_article_id INTEGER,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    result_json TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_job_runs_created_at
ON job_runs(created_at);

CREATE INDEX IF NOT EXISTS idx_job_runs_schedule_id_created_at
ON job_runs(schedule_id, created_at);
