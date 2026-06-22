ALTER TABLE articles
ADD COLUMN source_publish_policy TEXT NOT NULL DEFAULT 'full_content';
