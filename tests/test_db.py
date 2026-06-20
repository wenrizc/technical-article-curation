from pathlib import Path

from tac import db


def _connect(tmp_path):
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    return conn


def test_add_candidate_dedupes_by_normalized_url(tmp_path):
    conn = _connect(tmp_path)
    id1, _, inserted1 = db.add_candidate(
        conn, title="A", url="https://example.com/post?utm_source=rss", source_name="s"
    )
    # 带尾斜杠和追踪参数的同一文章会归一化为同一 URL，应复用已有记录。
    id2, _, inserted2 = db.add_candidate(
        conn, title="A again", url="https://example.com/post/", source_name="s"
    )
    assert inserted1 is True
    assert inserted2 is False
    assert id1 == id2
    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    assert count == 1


def test_add_candidate_same_title_different_url_not_deduped(tmp_path):
    conn = _connect(tmp_path)
    db.add_candidate(conn, title="Weekly Digest", url="https://a.example.com/1", source_name="s")
    db.add_candidate(conn, title="Weekly Digest", url="https://b.example.com/1", source_name="s")
    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    # 标题相同但 URL 不同，应都保留；当前去重只基于 URL。
    assert count == 2


def test_evaluation_failure_does_not_modify_article_or_fetch_state(tmp_path):
    conn = _connect(tmp_path)
    article_id, _, _ = db.add_candidate(
        conn, title="A", url="https://example.com/a", source_name="s"
    )
    db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})

    db.record_evaluation_failure(
        conn,
        article_id,
        error="invalid JSON",
        attempts=3,
        raw_response="{bad",
    )

    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    fetch = conn.execute("SELECT * FROM fetches WHERE article_id = ?", (article_id,)).fetchone()
    failure = conn.execute(
        "SELECT * FROM evaluation_failures WHERE article_id = ?", (article_id,)
    ).fetchone()

    assert article["status"] == "candidate"
    assert fetch["status"] == "success"
    assert failure["attempts"] == 3
    assert failure["raw_response"] == "{bad"


def test_failure_report_separates_fetch_and_evaluation_failures(tmp_path):
    conn = _connect(tmp_path)
    fetch_id, _, _ = db.add_candidate(
        conn, title="Fetch", url="https://example.com/fetch", source_name="s"
    )
    eval_id, _, _ = db.add_candidate(
        conn, title="Eval", url="https://example.com/eval", source_name="s"
    )
    db.record_failure(conn, fetch_id, "network")
    db.record_fetch_success(conn, eval_id, "# Body", {"crawler": "fixture"})
    db.record_evaluation_failure(
        conn,
        eval_id,
        error="schema",
        attempts=2,
        raw_response="{}",
    )

    rows = db.failure_report(conn)

    assert [(row["article_id"], row["stage"], row["error"]) for row in rows] == [
        (fetch_id, "fetch", "network"),
        (eval_id, "evaluation", "schema"),
    ]


def test_robustness_migration_rebuilds_legacy_articles_schema(tmp_path):
    conn = db.connect(tmp_path / "state.db")
    conn.executescript(
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        INSERT INTO schema_migrations(version, applied_at)
        VALUES ('001_initial', '2026-01-01T00:00:00Z');

        CREATE TABLE articles (
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
        CREATE INDEX idx_articles_status ON articles(status);
        CREATE INDEX idx_articles_normalized_url ON articles(normalized_url);
        CREATE INDEX idx_articles_normalized_title ON articles(normalized_title);
        CREATE UNIQUE INDEX idx_articles_slug ON articles(slug) WHERE slug IS NOT NULL;

        CREATE TABLE fetches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            fetched_at TEXT NOT NULL,
            status TEXT NOT NULL,
            content_markdown TEXT,
            error TEXT,
            crawler_metadata TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (article_id) REFERENCES articles(id)
        );
        CREATE TABLE evaluations (
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

        INSERT INTO articles(
            source_name, title, url, normalized_url, normalized_title, slug,
            status, retry_count, created_at, updated_at, source_tags
        )
        VALUES (
            's', 'Legacy', 'https://example.com/legacy',
            'https://example.com/legacy', 'legacy', 'legacy',
            'failed', 1, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', '[]'
        );
        """
    )
    conn.commit()
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "002_robustness_state.sql").write_text(
        Path("migrations/002_robustness_state.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    db.migrate(conn, migrations_dir=migrations_dir)
    db.add_candidate(conn, title="New", url="https://example.com/new", source_name="s")

    legacy = conn.execute("SELECT * FROM articles WHERE slug = 'legacy'").fetchone()
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(articles)").fetchall()]

    assert legacy["status"] == "candidate"
    assert "normalized_title" not in columns
    assert "duplicate_of" not in columns
    assert conn.execute("SELECT COUNT(*) FROM source_state").fetchone()[0] == 0
