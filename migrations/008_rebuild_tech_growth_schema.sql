PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS article_queue;
DROP TABLE IF EXISTS evaluation_failures;
DROP TABLE IF EXISTS evaluations;
DROP TABLE IF EXISTS fetches;
DROP TABLE IF EXISTS source_state;
DROP TABLE IF EXISTS job_runs;
DROP TABLE IF EXISTS articles;

CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    slug TEXT,
    status TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    published_at TEXT,
    collected_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT,
    source_tags TEXT NOT NULL DEFAULT '[]',
    source_publish_policy TEXT NOT NULL DEFAULT 'full_content'
);

CREATE INDEX idx_articles_status ON articles(status);
CREATE INDEX idx_articles_normalized_url ON articles(normalized_url);
CREATE UNIQUE INDEX idx_articles_slug ON articles(slug) WHERE slug IS NOT NULL;
CREATE INDEX idx_articles_status_updated_at ON articles(status, updated_at);
CREATE INDEX idx_articles_source_name ON articles(source_name);
CREATE INDEX idx_articles_updated_at ON articles(updated_at);
CREATE INDEX idx_articles_collected_at ON articles(collected_at);
CREATE INDEX idx_articles_published_at ON articles(published_at);

CREATE TABLE fetches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL,
    content_markdown TEXT,
    error TEXT,
    crawler_metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE INDEX idx_fetches_article_id ON fetches(article_id);

CREATE TABLE source_state (
    source_name TEXT PRIMARY KEY,
    etag TEXT,
    modified TEXT,
    last_status TEXT NOT NULL,
    last_error TEXT,
    checked_at TEXT NOT NULL
);

CREATE TABLE evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    evaluated_at TEXT NOT NULL,
    decision TEXT NOT NULL,
    content_type TEXT NOT NULL,
    dimensions TEXT NOT NULL,
    summary TEXT NOT NULL,
    tags TEXT NOT NULL,
    recommendation_reason TEXT NOT NULL,
    full_reasoning TEXT NOT NULL,
    model_name TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE INDEX idx_evaluations_article_id ON evaluations(article_id);

CREATE TABLE evaluation_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    failed_at TEXT NOT NULL,
    error TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    raw_response TEXT
);

CREATE INDEX idx_evaluation_failures_article_id ON evaluation_failures(article_id);

CREATE TABLE job_runs (
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

CREATE INDEX idx_job_runs_created_at ON job_runs(created_at);
CREATE INDEX idx_job_runs_schedule_id_created_at ON job_runs(schedule_id, created_at);

CREATE TABLE article_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    job_id TEXT,
    range_since TEXT,
    range_until TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE INDEX idx_article_queue_status_stage ON article_queue(stage, status, id);
CREATE INDEX idx_article_queue_article_stage ON article_queue(article_id, stage);
CREATE UNIQUE INDEX idx_article_queue_active
ON article_queue(article_id, stage)
WHERE status IN ('queued', 'running');

PRAGMA foreign_keys = ON;
