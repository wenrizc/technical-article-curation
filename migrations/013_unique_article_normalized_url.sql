UPDATE articles
SET normalized_url = normalized_url || '#duplicate-' || id
WHERE id IN (
    SELECT a.id
    FROM articles a
    WHERE EXISTS (
        SELECT 1
        FROM articles b
        WHERE b.normalized_url = a.normalized_url
          AND b.id < a.id
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_normalized_url_unique
ON articles(normalized_url);
