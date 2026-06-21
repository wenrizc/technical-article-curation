import asyncio
from pathlib import Path

import pytest

from tac.config import Settings
from tac.jobs import JobConflict, JobManager, JobQueueFull, JobStatus


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
    return Settings(**values)


def test_job_runs_to_success(tmp_path):
    manager = JobManager(_settings(tmp_path))
    job = manager.submit_job("discover", lambda: {"inserted": 1})

    asyncio.run(manager.run_job(job.job_id))

    stored = manager.get_job(job.job_id)
    assert stored.status == JobStatus.succeeded
    assert stored.result == {"inserted": 1}


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
