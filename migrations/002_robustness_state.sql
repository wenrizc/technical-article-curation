PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS articles_new;

CREATE TABLE IF NOT EXISTS articles_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    slug TEXT,
    status TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    collected_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT,
    source_tags TEXT NOT NULL DEFAULT '[]'
);

INSERT INTO articles_new(
    id, source_name, title, url, normalized_url, slug, status, retry_count,
    collected_at, created_at, updated_at, error, source_tags
)
SELECT
    id,
    source_name,
    title,
    url,
    normalized_url,
    slug,
    CASE
        WHEN status IN ('failed', 'duplicate') THEN 'candidate'
        ELSE status
    END,
    retry_count,
    collected_at,
    created_at,
    updated_at,
    error,
    source_tags
FROM articles;

DROP TABLE articles;
ALTER TABLE articles_new RENAME TO articles;

CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_normalized_url ON articles(normalized_url);
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_slug ON articles(slug) WHERE slug IS NOT NULL;

CREATE TABLE IF NOT EXISTS source_state (
    source_name TEXT PRIMARY KEY,
    etag TEXT,
    modified TEXT,
    last_status TEXT NOT NULL,
    last_error TEXT,
    checked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    failed_at TEXT NOT NULL,
    error TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    raw_response TEXT
);

CREATE INDEX IF NOT EXISTS idx_evaluation_failures_article_id ON evaluation_failures(article_id);

PRAGMA foreign_keys = ON;
