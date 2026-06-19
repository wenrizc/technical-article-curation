CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    slug TEXT,
    status TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    duplicate_of INTEGER,
    collected_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT,
    source_tags TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (duplicate_of) REFERENCES articles(id)
);

CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_normalized_url ON articles(normalized_url);
CREATE INDEX IF NOT EXISTS idx_articles_normalized_title ON articles(normalized_title);
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_slug ON articles(slug) WHERE slug IS NOT NULL;

CREATE TABLE IF NOT EXISTS fetches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL,
    content_markdown TEXT,
    error TEXT,
    crawler_metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE INDEX IF NOT EXISTS idx_fetches_article_id ON fetches(article_id);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    evaluated_at TEXT NOT NULL,
    decision TEXT NOT NULL,
    confidence TEXT NOT NULL,
    dimensions TEXT NOT NULL,
    summary TEXT NOT NULL,
    tags TEXT NOT NULL,
    recommendation_reason TEXT NOT NULL,
    full_reasoning TEXT NOT NULL,
    model_name TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE INDEX IF NOT EXISTS idx_evaluations_article_id ON evaluations(article_id);

