PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS evaluations_new;

CREATE TABLE evaluations_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    evaluated_at TEXT NOT NULL,
    decision TEXT NOT NULL,
    content_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    tags TEXT NOT NULL,
    recommendation_reason TEXT NOT NULL,
    full_reasoning TEXT NOT NULL,
    model_name TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

INSERT INTO evaluations_new(
    id, article_id, evaluated_at, decision, content_type, summary,
    tags, recommendation_reason, full_reasoning, model_name, raw_json
)
SELECT
    id, article_id, evaluated_at, decision, content_type, summary,
    tags, recommendation_reason, full_reasoning, model_name, raw_json
FROM evaluations;

DROP TABLE evaluations;
ALTER TABLE evaluations_new RENAME TO evaluations;

CREATE INDEX IF NOT EXISTS idx_evaluations_article_id ON evaluations(article_id);

PRAGMA foreign_keys = ON;
