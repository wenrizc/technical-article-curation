import asyncio
from pathlib import Path

import pytest

from tac.application.jobs import JobConflict, JobManager, JobQueueFull, JobStatus, JobTrigger
from tac.infrastructure.db import store as db
from tac.settings import Settings


def _settings(tmp_path, **overrides) -> Settings:
    values = {
        "state_db": tmp_path / "state.db",
        "sources_path": tmp_path / "sources.yaml",
        "public_dir": tmp_path / "public",
        "max_retry": 3,
        "model": "fixture-model",
        "base_url": "https://example.invalid/v1",
        "api_key": None,
        "ai_response_path": None,
        "fetch_fixture_path": None,
        "crawler4ai_enabled": False,
        "fetch_delay_seconds": 0,
        "evaluation_max_attempts": 3,
        "prompt_language": "zh-CN",
        "prompt_path": Path("prompts/zh-CN/evaluate.md"),
        "few_shot_dir": Path("prompts/zh-CN/few_shots"),
    }
    values.update(overrides)
    settings = Settings(**values)
    conn = db.connect(settings.state_db)
    db.migrate(conn)
    conn.close()
    return settings


def test_job_runs_to_success(tmp_path):
    manager = JobManager(_settings(tmp_path))
    job = manager.submit_job("discover", lambda: {"inserted": 1})

    asyncio.run(manager.run_job(job.job_id))

    stored = manager.get_job(job.job_id)
    assert stored.status == JobStatus.succeeded
    assert stored.result == {"inserted": 1}
    assert stored.trigger == JobTrigger.manual


def test_job_queue_limit_returns_rejection(tmp_path):
    manager = JobManager(_settings(tmp_path, job_queue_limit=1))
    manager.submit_job("discover", lambda: {})

    with pytest.raises(JobQueueFull):
        manager.submit_job("fetch", lambda: {})


def test_job_conflict_when_run_is_active(tmp_path):
    manager = JobManager(_settings(tmp_path))
    manager.submit_job("run", lambda: {})

    with pytest.raises(JobConflict):
        manager.submit_job("fetch", lambda: {})


def test_duplicate_article_stage_job_is_rejected(tmp_path):
    manager = JobManager(_settings(tmp_path))
    manager.submit_job("retry-fetch", lambda: {}, target_article_id=1)

    with pytest.raises(JobConflict):
        manager.submit_job("retry-fetch", lambda: {}, target_article_id=1)


def test_job_timeout_marks_failed(tmp_path):
    manager = JobManager(_settings(tmp_path, job_timeout_seconds=0.01))

    def slow():
        import time

        time.sleep(0.05)

    job = manager.submit_job("slow", slow)

    asyncio.run(manager.run_job(job.job_id))

    stored = manager.get_job(job.job_id)
    assert stored.status == JobStatus.failed
    assert stored.error == "job timed out"


def test_job_history_survives_manager_recreation(tmp_path):
    settings = _settings(tmp_path)
    manager = JobManager(settings)
    job = manager.submit_job("discover", lambda: {"inserted": 1})
    asyncio.run(manager.run_job(job.job_id))

    restored = JobManager(settings).get_job(job.job_id)

    assert restored.status == JobStatus.succeeded
    assert restored.result == {"inserted": 1}


def test_recover_interrupted_jobs_marks_active_runs_failed(tmp_path):
    settings = _settings(tmp_path)
    manager = JobManager(settings)
    queued = manager.submit_job("discover", lambda: {})

    recovered = JobManager(settings).recover_interrupted_jobs()
    stored = JobManager(settings).get_job(queued.job_id)

    assert recovered == 1
    assert stored.status == JobStatus.failed
    assert stored.error == "job interrupted by service restart"


def test_record_skipped_job_persists_audit_row(tmp_path):
    settings = _settings(tmp_path)
    manager = JobManager(settings)

    skipped = manager.record_skipped_job(
        "run",
        trigger=JobTrigger.schedule,
        schedule_id="run",
        error="another job is already active",
    )
    stored = JobManager(settings).get_job(skipped.job_id)

    assert stored.status == JobStatus.skipped
    assert stored.trigger == JobTrigger.schedule
    assert stored.schedule_id == "run"
