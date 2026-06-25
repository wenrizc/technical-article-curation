import sqlite3
from pathlib import Path

import pytest

from tac.application.use_cases import manage_articles as articles
from tac.application.use_cases import manage_tags as tags
from tac.domain.models import ArticleStatus, EvaluationResult
from tac.infrastructure.db import store as db


def _connect(tmp_path):
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    return conn


def _accepted_result(
    tags: list[str] | None = None,
    suggested_tags: list[str] | None = None,
) -> EvaluationResult:
    return EvaluationResult.model_validate(
        {
            "decision": "accept",
            "content_type": "engineering_case",
            "summary": "摘要",
            "tags": tags or ["Architecture"],
            "suggested_tags": suggested_tags or [],
            "recommendation_reason": "推荐理由",
        }
    )


def test_add_candidate_dedupes_by_safe_url_normalization(tmp_path):
    conn = _connect(tmp_path)
    id1, _, inserted1 = db.add_candidate(
        conn, title="A", url="HTTPS://Example.com:443/post", source_name="s"
    )
    id2, _, inserted2 = db.add_candidate(
        conn, title="A again", url="https://example.com/post", source_name="s"
    )
    assert inserted1 is True
    assert inserted2 is False
    assert id1 == id2
    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    assert count == 1


def test_normalized_url_unique_index_rejects_raw_duplicates(tmp_path):
    conn = _connect(tmp_path)
    db.add_candidate(conn, title="A", url="https://example.com/post", source_name="s")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO articles(
                source_name, title, url, normalized_url, slug,
                status, created_at, updated_at, source_tags
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "s2",
                "A duplicate",
                "https://example.com/post",
                "https://example.com/post",
                "s2-a-duplicate",
                "candidate",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                "[]",
            ),
        )


def test_add_candidate_recovers_from_unique_conflict_race(tmp_path, monkeypatch):
    conn = _connect(tmp_path)
    id1, _, _ = db.add_candidate(
        conn, title="A", url="https://example.com/post", source_name="s"
    )
    original_find_existing = db.find_existing
    calls = 0

    def stale_first_read(conn_arg, normalized_url):
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return original_find_existing(conn_arg, normalized_url)

    monkeypatch.setattr(db, "find_existing", stale_first_read)

    id2, status, inserted = db.add_candidate(
        conn,
        title="A from another worker",
        url="https://example.com/post",
        source_name="s2",
        published_at="2026-06-01T00:00:00Z",
        source_content_markdown="Body from feed",
        source_content_metadata={"source": "feed_entry"},
    )
    article = conn.execute("SELECT * FROM articles WHERE id = ?", (id1,)).fetchone()

    assert id2 == id1
    assert status is ArticleStatus.candidate
    assert inserted is False
    assert article["published_at"] == "2026-06-01T00:00:00Z"
    assert article["source_content_markdown"] == "Body from feed"


def test_unique_normalized_url_migration_preserves_legacy_duplicates(tmp_path):
    conn = db.connect(tmp_path / "state.db")
    conn.executescript(
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        INSERT INTO schema_migrations(version, applied_at)
        VALUES ('012_drop_article_publish_policy', '2026-01-01T00:00:00Z');

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
            source_content_markdown TEXT,
            source_content_metadata TEXT NOT NULL DEFAULT '{}'
        );

        INSERT INTO articles(source_name, title, url, normalized_url, slug, status, created_at, updated_at)
        VALUES
            ('a', 'First', 'https://example.com/post', 'https://example.com/post', 'a-first', 'candidate', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'),
            ('b', 'Second', 'https://example.com/post', 'https://example.com/post', 'b-second', 'candidate', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z');
        """
    )
    conn.commit()
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "013_unique_article_normalized_url.sql").write_text(
        Path("migrations/013_unique_article_normalized_url.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    applied = db.migrate(conn, migrations_dir=migrations_dir)
    rows = conn.execute("SELECT id, normalized_url FROM articles ORDER BY id").fetchall()
    indexes = conn.execute("PRAGMA index_list(articles)").fetchall()

    assert applied == ["013_unique_article_normalized_url"]
    assert [row["normalized_url"] for row in rows] == [
        "https://example.com/post",
        "https://example.com/post#duplicate-2",
    ]
    assert any(row["name"] == "idx_articles_normalized_url_unique" for row in indexes)


def test_add_candidate_keeps_query_trailing_slash_and_fragment_distinct(tmp_path):
    conn = _connect(tmp_path)
    db.add_candidate(
        conn, title="A", url="https://example.com/post?utm_source=rss", source_name="s"
    )
    db.add_candidate(conn, title="A slash", url="https://example.com/post/", source_name="s")
    db.add_candidate(conn, title="A fragment", url="https://example.com/post#comments", source_name="s")

    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    # query、尾斜杠和 fragment 可能参与定位内容，保守起见不再合并。
    assert count == 3


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


def test_set_status_updates_article_state(tmp_path):
    conn = _connect(tmp_path)
    article_id, _, _ = db.add_candidate(
        conn, title="A", url="https://example.com/a", source_name="s"
    )

    restored = articles.set_article_status(conn, article_id, ArticleStatus.low_confidence)

    assert restored["status"] == "low_confidence"


def test_recover_article_queue_resets_running_items(tmp_path):
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn, title="Queued", url="https://example.com/queued", source_name="s"
    )
    queue_id, _ = db.enqueue_article(conn, article_id=article_id, stage="fetch")
    assert db.mark_queue_running(conn, queue_id, job_id="job-1") is True

    recovered = db.recover_article_queue(conn)
    queue = conn.execute("SELECT * FROM article_queue WHERE id = ?", (queue_id,)).fetchone()

    assert recovered == 1
    assert queue["status"] == "queued"
    assert queue["job_id"] is None
    assert queue["started_at"] is None


def test_public_queries_only_include_accepted(tmp_path):
    conn = _connect(tmp_path)
    article_id, _, _ = db.add_candidate(
        conn, title="Accepted", url="https://example.com/a", source_name="s"
    )
    db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})
    db.record_evaluation(conn, article_id, _accepted_result(), "fixture-model", "{}")
    assert articles.list_public_articles(conn).total == 1

    articles.set_article_status(conn, article_id, ArticleStatus.low_confidence)

    assert articles.list_public_articles(conn).total == 0


def test_evaluation_routes_unknown_tags_to_candidates(tmp_path):
    conn = _connect(tmp_path)
    article_id, _, _ = db.add_candidate(
        conn, title="A", url="https://example.com/a", source_name="s"
    )
    db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})

    db.record_evaluation(
        conn,
        article_id,
        _accepted_result(["New Niche Tag"]),
        "fixture-model",
        "{}",
    )

    public_article = articles.list_public_articles(conn).items[0]
    candidates = tags.list_tag_candidates(conn)

    assert public_article["tags"] == []
    assert candidates["total"] == 1
    assert candidates["items"][0]["suggested_tag"] == "New Niche Tag"


def test_approved_tag_candidate_becomes_public_tag(tmp_path):
    conn = _connect(tmp_path)
    article_id, _, _ = db.add_candidate(
        conn, title="A", url="https://example.com/a", source_name="s"
    )
    db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})
    db.record_evaluation(
        conn,
        article_id,
        _accepted_result(["New Niche Tag"]),
        "fixture-model",
        "{}",
    )
    candidate_id = tags.list_tag_candidates(conn)["items"][0]["id"]

    tags.approve_candidate(conn, candidate_id)

    public_article = articles.list_public_articles(conn).items[0]
    assert public_article["tags"] == ["New Niche Tag"]
    assert tags.list_tag_candidates(conn)["total"] == 0


def test_evaluation_routes_suggested_tags_to_candidates(tmp_path):
    conn = _connect(tmp_path)
    article_id, _, _ = db.add_candidate(
        conn, title="A", url="https://example.com/a", source_name="s"
    )
    db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})

    db.record_evaluation(
        conn,
        article_id,
        _accepted_result(tags=["Architecture"], suggested_tags=["Queueing Theory"]),
        "fixture-model",
        "{}",
    )

    public_article = articles.list_public_articles(conn).items[0]
    candidates = tags.list_tag_candidates(conn)

    assert public_article["tags"] == ["Architecture"]
    assert candidates["total"] == 1
    assert candidates["items"][0]["suggested_tag"] == "Queueing Theory"


def test_seeded_vocabulary_tag_links_during_evaluation(tmp_path):
    conn = _connect(tmp_path)
    article_id, _, _ = db.add_candidate(
        conn, title="A", url="https://example.com/a", source_name="s"
    )
    db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})

    db.record_evaluation(conn, article_id, _accepted_result(), "fixture-model", "{}")

    public_article = articles.list_public_articles(conn).items[0]
    assert public_article["tags"] == ["Architecture"]
    assert tags.list_tag_candidates(conn)["total"] == 0


def test_prompt_aligned_tag_vocabulary_is_seeded(tmp_path):
    conn = _connect(tmp_path)

    names = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM tag_vocabulary WHERE status = 'active'"
        ).fetchall()
    }

    assert {
        "AI",
        "Architecture",
        "Computer Systems",
        "Database",
        "Engineering",
        "Incident Review",
        "Learning Path",
        "Performance",
        "Query Optimizer",
        "Research",
    }.issubset(names)


def test_fetch_evaluation_can_rewrite_current_status(tmp_path):
    conn = _connect(tmp_path)
    article_id, _, _ = db.add_candidate(
        conn, title="A", url="https://example.com/a", source_name="s"
    )

    assert db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"}) is True
    db.record_evaluation(conn, article_id, _accepted_result(), "fixture-model", "{}")
    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    fetch_count = conn.execute(
        "SELECT COUNT(*) FROM fetches WHERE article_id = ?", (article_id,)
    ).fetchone()[0]

    assert article["status"] == "accepted"
    assert fetch_count == 1


def test_admin_articles_pagination_search_and_failed_only(tmp_path):
    conn = _connect(tmp_path)
    id1, _, _ = db.add_candidate(
        conn, title="Queue Latency", url="https://example.com/queue", source_name="alpha"
    )
    id2, _, _ = db.add_candidate(
        conn, title="Storage Notes", url="https://example.com/storage", source_name="beta"
    )
    db.record_failure(conn, id2, "network")

    first_page = articles.list_admin_articles(conn, page=1, page_size=1)
    search_page = articles.list_admin_articles(conn, q="queue")
    failed_page = articles.list_admin_articles(conn, failed_only=True)

    assert first_page.total == 2
    assert len(first_page.items) == 1
    assert search_page.total == 1
    assert search_page.items[0]["id"] == id1
    assert failed_page.total == 1
    assert failed_page.items[0]["id"] == id2


def test_destructive_migration_rebuilds_legacy_articles_schema(tmp_path):
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
            content_type TEXT NOT NULL,
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
    (migrations_dir / "006_article_publish_policy.sql").write_text(
        Path("migrations/006_article_publish_policy.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (migrations_dir / "007_rebuild_published_queue.sql").write_text(
        Path("migrations/007_rebuild_published_queue.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (migrations_dir / "008_rebuild_tech_growth_schema.sql").write_text(
        Path("migrations/008_rebuild_tech_growth_schema.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (migrations_dir / "010_feed_entry_content.sql").write_text(
        Path("migrations/010_feed_entry_content.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (migrations_dir / "012_drop_article_publish_policy.sql").write_text(
        Path("migrations/012_drop_article_publish_policy.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (migrations_dir / "014_drop_evaluation_dimensions.sql").write_text(
        Path("migrations/014_drop_evaluation_dimensions.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (migrations_dir / "015_drop_evaluation_full_reasoning.sql").write_text(
        Path("migrations/015_drop_evaluation_full_reasoning.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    db.migrate(conn, migrations_dir=migrations_dir)
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(articles)").fetchall()]
    evaluation_columns = [
        row["name"] for row in conn.execute("PRAGMA table_info(evaluations)").fetchall()
    ]
    db.add_candidate(
        conn,
        title="New",
        url="https://example.com/new",
        source_name="s",
        published_at="2026-06-01T00:00:00Z",
    )
    new_article = conn.execute("SELECT * FROM articles WHERE slug = 's-new'").fetchone()

    assert conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1
    assert new_article["published_at"] == "2026-06-01T00:00:00Z"
    assert "published_at" in columns
    assert "source_content_markdown" in columns
    assert "source_publish_policy" not in columns
    assert "normalized_title" not in columns
    assert "duplicate_of" not in columns
    assert "content_type" in evaluation_columns
    assert "dimensions" not in evaluation_columns
    assert "full_reasoning" not in evaluation_columns
    assert conn.execute("SELECT COUNT(*) FROM source_state").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM article_queue").fetchone()[0] == 0


def test_drop_evaluation_confidence_migration_preserves_rows(tmp_path):
    conn = db.connect(tmp_path / "state.db")
    conn.executescript(
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        INSERT INTO schema_migrations(version, applied_at)
        VALUES
            ('001_initial', '2026-01-01T00:00:00Z'),
            ('002_robustness_state', '2026-01-01T00:00:00Z'),
            ('003_fastapi_admin_state', '2026-01-01T00:00:00Z');

        CREATE TABLE articles (
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
        CREATE INDEX idx_evaluations_article_id ON evaluations(article_id);

        INSERT INTO articles(
            source_name, title, url, normalized_url, status, created_at, updated_at
        )
        VALUES (
            's', 'A', 'https://example.com/a', 'https://example.com/a',
            'accepted', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
        );
        INSERT INTO evaluations(
            article_id, evaluated_at, decision, confidence, dimensions, summary,
            tags, recommendation_reason, full_reasoning, model_name, raw_json
        )
        VALUES (
            1, '2026-01-01T00:00:00Z', 'accept', 'high', '{}', '摘要',
            '[]', '理由', '内部原因', 'fixture-model', '{}'
        );
        """
    )
    conn.commit()
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "004_drop_evaluation_confidence.sql").write_text(
        Path("migrations/004_drop_evaluation_confidence.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    applied = db.migrate(conn, migrations_dir=migrations_dir)

    columns = [row["name"] for row in conn.execute("PRAGMA table_info(evaluations)").fetchall()]
    row = conn.execute("SELECT decision, summary FROM evaluations").fetchone()
    assert applied == ["004_drop_evaluation_confidence"]
    assert "confidence" not in columns
    assert row["decision"] == "accept"
    assert row["summary"] == "摘要"


def test_drop_evaluation_dimensions_migration_preserves_rows(tmp_path):
    conn = db.connect(tmp_path / "state.db")
    conn.executescript(
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        INSERT INTO schema_migrations(version, applied_at)
        VALUES ('013_unique_article_normalized_url', '2026-01-01T00:00:00Z');

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
            source_content_markdown TEXT,
            source_content_metadata TEXT NOT NULL DEFAULT '{}'
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

        INSERT INTO articles(
            source_name, title, url, normalized_url, status, created_at, updated_at
        )
        VALUES (
            's', 'A', 'https://example.com/a', 'https://example.com/a',
            'accepted', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
        );
        INSERT INTO evaluations(
            article_id, evaluated_at, decision, content_type, dimensions, summary,
            tags, recommendation_reason, full_reasoning, model_name, raw_json
        )
        VALUES (
            1, '2026-01-01T00:00:00Z', 'accept', 'engineering_case', '{}', '摘要',
            '["Architecture"]', '理由', '内部原因', 'fixture-model', '{}'
        );
        """
    )
    conn.commit()
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "014_drop_evaluation_dimensions.sql").write_text(
        Path("migrations/014_drop_evaluation_dimensions.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    applied = db.migrate(conn, migrations_dir=migrations_dir)

    columns = [row["name"] for row in conn.execute("PRAGMA table_info(evaluations)").fetchall()]
    row = conn.execute("SELECT decision, content_type, summary FROM evaluations").fetchone()
    assert applied == ["014_drop_evaluation_dimensions"]
    assert "dimensions" not in columns
    assert row["decision"] == "accept"
    assert row["content_type"] == "engineering_case"
    assert row["summary"] == "摘要"


def test_drop_evaluation_full_reasoning_migration_preserves_rows(tmp_path):
    conn = db.connect(tmp_path / "state.db")
    conn.executescript(
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        INSERT INTO schema_migrations(version, applied_at)
        VALUES ('014_drop_evaluation_dimensions', '2026-01-01T00:00:00Z');

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
            source_content_markdown TEXT,
            source_content_metadata TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE evaluations (
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
        CREATE INDEX idx_evaluations_article_id ON evaluations(article_id);

        INSERT INTO articles(
            source_name, title, url, normalized_url, status, created_at, updated_at
        )
        VALUES (
            's', 'A', 'https://example.com/a', 'https://example.com/a',
            'accepted', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
        );
        INSERT INTO evaluations(
            article_id, evaluated_at, decision, content_type, summary,
            tags, recommendation_reason, full_reasoning, model_name, raw_json
        )
        VALUES (
            1, '2026-01-01T00:00:00Z', 'accept', 'engineering_case', '摘要',
            '["Architecture"]', '理由', '内部原因', 'fixture-model', '{}'
        );
        """
    )
    conn.commit()
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "015_drop_evaluation_full_reasoning.sql").write_text(
        Path("migrations/015_drop_evaluation_full_reasoning.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    applied = db.migrate(conn, migrations_dir=migrations_dir)

    columns = [row["name"] for row in conn.execute("PRAGMA table_info(evaluations)").fetchall()]
    row = conn.execute("SELECT decision, content_type, summary FROM evaluations").fetchone()
    assert applied == ["015_drop_evaluation_full_reasoning"]
    assert "full_reasoning" not in columns
    assert row["decision"] == "accept"
    assert row["content_type"] == "engineering_case"
    assert row["summary"] == "摘要"
