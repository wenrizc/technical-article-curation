ALTER TABLE articles ADD COLUMN previous_status TEXT;
ALTER TABLE articles ADD COLUMN archived_at TEXT;

CREATE INDEX IF NOT EXISTS idx_articles_status_updated_at
ON articles(status, updated_at);

CREATE INDEX IF NOT EXISTS idx_articles_source_name
ON articles(source_name);

CREATE INDEX IF NOT EXISTS idx_articles_updated_at
ON articles(updated_at);

CREATE INDEX IF NOT EXISTS idx_articles_collected_at
ON articles(collected_at);
