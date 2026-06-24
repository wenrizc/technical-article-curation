ALTER TABLE articles
ADD COLUMN source_content_markdown TEXT;

ALTER TABLE articles
ADD COLUMN source_content_metadata TEXT NOT NULL DEFAULT '{}';
