import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tac.application.jobs import JobManager, JobStatus
from tac.application.scheduler import CronExpressionError, CronSchedule, SchedulerService
from tac.infrastructure.db import store as db
from tac.settings import Settings


def _settings(tmp_path, **overrides) -> Settings:
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text("sources: []\nmanual_urls: []\n", encoding="utf-8")
    values = {
        "state_db": tmp_path / "state.db",
        "sources_path": sources_path,
        "public_dir": tmp_path / "public",
        "max_retry": 3,
        "model": "fixture-model",
        "base_url": "https://example.invalid/v1",
        "api_key": None,
        "ai_response_path": Path("tests/fixtures/ai/accept.json"),
        "fetch_fixture_path": Path("tests/fixtures/markdown/queue-latency.md"),
        "crawler4ai_enabled": False,
        "fetch_delay_seconds": 0,
        "evaluation_max_attempts": 3,
        "prompt_language": "zh-CN",
        "prompt_path": Path("prompts/zh-CN/evaluate.md"),
        "few_shot_dir": Path("prompts/zh-CN/few_shots"),
        "scheduler_enabled": True,
    }
    values.update(overrides)
    settings = Settings(**values)
    conn = db.connect(settings.state_db)
    db.migrate(conn)
    conn.close()
    return settings


def test_cron_schedule_matches_standard_fields():
    schedule = CronSchedule.parse("*/15 8-9 * * 1-5")

    assert schedule.matches(datetime(2026, 6, 22, 8, 30, tzinfo=ZoneInfo("UTC")))
    assert not schedule.matches(datetime(2026, 6, 21, 8, 30, tzinfo=ZoneInfo("UTC")))
    assert not schedule.matches(datetime(2026, 6, 22, 8, 10, tzinfo=ZoneInfo("UTC")))


def test_cron_schedule_uses_or_when_month_day_and_weekday_are_restricted():
    schedule = CronSchedule.parse("0 8 1 * 1")

    assert schedule.matches(datetime(2026, 6, 1, 8, 0, tzinfo=ZoneInfo("UTC")))
    assert schedule.matches(datetime(2026, 6, 22, 8, 0, tzinfo=ZoneInfo("UTC")))
    assert not schedule.matches(datetime(2026, 6, 23, 8, 0, tzinfo=ZoneInfo("UTC")))


def test_cron_schedule_rejects_invalid_expression():
    with pytest.raises(CronExpressionError):
        CronSchedule.parse("0 8 * *")


def test_scheduler_manual_trigger_submits_persistent_job(tmp_path):
    settings = _settings(tmp_path)
    manager = JobManager(settings)
    scheduler = SchedulerService(settings, manager)

    job = asyncio.run(scheduler.trigger("run", manual=True))
    asyncio.run(manager.run_job(job["job_id"]))
    stored = manager.get_job(job["job_id"])

    assert job["schedule_id"] == "run"
    assert stored.status == JobStatus.succeeded
    assert stored.schedule_id == "run"


def test_scheduler_conflict_records_skipped_job(tmp_path):
    settings = _settings(tmp_path)
    manager = JobManager(settings)
    manager.submit_job("discover", lambda: {})
    scheduler = SchedulerService(settings, manager)

    job = asyncio.run(scheduler.trigger("run", manual=False))

    assert job["status"] == "skipped"
    assert job["trigger"] == "schedule"
    assert job["schedule_id"] == "run"
