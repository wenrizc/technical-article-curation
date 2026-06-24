CREATE TABLE IF NOT EXISTS tag_vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tag_vocabulary_normalized_name
ON tag_vocabulary(normalized_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tag_vocabulary_slug
ON tag_vocabulary(slug);
CREATE INDEX IF NOT EXISTS idx_tag_vocabulary_status ON tag_vocabulary(status);

CREATE TABLE IF NOT EXISTS article_tags (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tag_vocabulary(id) ON DELETE CASCADE,
    evaluation_id INTEGER REFERENCES evaluations(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (article_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_article_tags_tag_id ON article_tags(tag_id);

CREATE TABLE IF NOT EXISTS tag_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    evaluation_id INTEGER REFERENCES evaluations(id) ON DELETE SET NULL,
    suggested_tag TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tag_candidates_pending_unique
ON tag_candidates(article_id, normalized_name)
WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_tag_candidates_status ON tag_candidates(status, created_at);

INSERT OR IGNORE INTO tag_vocabulary(
    name, normalized_name, slug, description, status, created_at, updated_at
)
SELECT DISTINCT
    TRIM(json_each.value),
    LOWER(TRIM(json_each.value)),
    LOWER(REPLACE(TRIM(json_each.value), ' ', '-')),
    '历史评估标签迁移导入',
    'active',
    COALESCE(e.evaluated_at, datetime('now')),
    COALESCE(e.evaluated_at, datetime('now'))
FROM evaluations e, json_each(CASE WHEN json_valid(e.tags) THEN e.tags ELSE '[]' END)
WHERE TRIM(json_each.value) != '';

INSERT OR IGNORE INTO article_tags(article_id, tag_id, evaluation_id, created_at)
SELECT
    e.article_id,
    tv.id,
    e.id,
    COALESCE(e.evaluated_at, datetime('now'))
FROM evaluations e, json_each(CASE WHEN json_valid(e.tags) THEN e.tags ELSE '[]' END)
JOIN tag_vocabulary tv ON tv.normalized_name = LOWER(TRIM(json_each.value))
WHERE TRIM(json_each.value) != '';
