from __future__ import annotations

import asyncio
import json
import sqlite3
from collections import OrderedDict
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Any
from uuid import uuid4

from tac.infrastructure.db import store as db
from tac.settings import Settings
from tac.shared.utils import utc_now_iso


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"


class JobRejected(RuntimeError):
    pass


class JobConflict(JobRejected):
    pass


class JobQueueFull(JobRejected):
    pass


class JobNotFound(KeyError):
    pass


class JobTrigger(str, Enum):
    manual = "manual"
    schedule = "schedule"


@dataclass
class Job:
    job_id: str
    kind: str
    status: JobStatus
    created_at: str
    trigger: JobTrigger = JobTrigger.manual
    schedule_id: str | None = None
    target_article_id: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    result: Any = None
    error: str | None = None
    _runner: Callable[[], Any] | None = field(default=None, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "status": self.status.value,
            "trigger": self.trigger.value,
            "schedule_id": self.schedule_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "target_article_id": self.target_article_id,
            "result": self.result,
            "error": self.error,
        }


class JobManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._lock = RLock()
        self._execution_semaphore = asyncio.Semaphore(settings.job_max_concurrency)
        with closing(self._connect()) as conn:
            db.migrate(conn)

    def recover_interrupted_jobs(self) -> int:
        with closing(self._connect()) as conn:
            return db.mark_interrupted_job_runs(conn, finished_at=utc_now_iso())

    def submit_job(
        self,
        kind: str,
        runner: Callable[[], Any],
        *,
        trigger: JobTrigger = JobTrigger.manual,
        schedule_id: str | None = None,
        target_article_id: int | None = None,
    ) -> Job:
        with self._lock:
            active = [
                job
                for job in self._jobs.values()
                if job.status in {JobStatus.queued, JobStatus.running}
            ]
            queued = [job for job in active if job.status == JobStatus.queued]
            if len(queued) >= self.settings.job_queue_limit:
                raise JobQueueFull("job queue is full")
            if kind == "run" and active:
                raise JobConflict("another job is already active")
            if kind != "run" and any(job.kind == "run" for job in active):
                raise JobConflict("run job is already active")
            if target_article_id is not None:
                for job in active:
                    if job.kind == kind and job.target_article_id == target_article_id:
                        raise JobConflict("duplicate article job is already active")
            job = Job(
                job_id=uuid4().hex,
                kind=kind,
                status=JobStatus.queued,
                trigger=trigger,
                schedule_id=schedule_id,
                created_at=utc_now_iso(),
                target_article_id=target_article_id,
                _runner=runner,
            )
            self._jobs[job.job_id] = job
            with closing(self._connect()) as conn:
                db.create_job_run(
                    conn,
                    job_id=job.job_id,
                    kind=job.kind,
                    status=job.status.value,
                    trigger=job.trigger.value,
                    schedule_id=job.schedule_id,
                    target_article_id=job.target_article_id,
                    created_at=job.created_at,
                )
            self._prune_locked()
            return job

    def record_skipped_job(
        self,
        kind: str,
        *,
        trigger: JobTrigger,
        schedule_id: str | None = None,
        target_article_id: int | None = None,
        error: str,
    ) -> Job:
        now = utc_now_iso()
        job = Job(
            job_id=uuid4().hex,
            kind=kind,
            status=JobStatus.skipped,
            trigger=trigger,
            schedule_id=schedule_id,
            target_article_id=target_article_id,
            created_at=now,
            finished_at=now,
            error=error,
        )
        with closing(self._connect()) as conn:
            db.create_job_run(
                conn,
                job_id=job.job_id,
                kind=job.kind,
                status=job.status.value,
                trigger=job.trigger.value,
                schedule_id=job.schedule_id,
                target_article_id=job.target_article_id,
                created_at=job.created_at,
            )
            db.finish_job_run(
                conn,
                job.job_id,
                status=job.status.value,
                finished_at=now,
                error=error,
            )
        return job

    async def run_job(self, job_id: str) -> None:
        job = self.get_job(job_id)
        async with self._execution_semaphore:
            with self._lock:
                if job.status != JobStatus.queued:
                    return
                job.status = JobStatus.running
                job.started_at = utc_now_iso()
                with closing(self._connect()) as conn:
                    db.mark_job_started(conn, job.job_id, started_at=job.started_at)
            try:
                if job._runner is None:
                    raise RuntimeError("job runner is missing")
                result = await asyncio.wait_for(
                    asyncio.to_thread(job._runner),
                    timeout=self.settings.job_timeout_seconds,
                )
            except TimeoutError:
                self._finish(job, JobStatus.failed, error="job timed out")
            except Exception as exc:
                self._finish(job, JobStatus.failed, error=str(exc))
            else:
                self._finish(job, JobStatus.succeeded, result=result)

    def get_job(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                return job
        with closing(self._connect()) as conn:
            row = db.get_job_run(conn, job_id)
        if not row:
            raise JobNotFound(job_id)
        return _job_from_row(row)

    def list_jobs(self) -> list[Job]:
        with closing(self._connect()) as conn:
            rows = db.list_job_runs(conn, limit=self.settings.job_history_limit)
        return [_job_from_row(row) for row in rows]

    def _finish(
        self,
        job: Job,
        status: JobStatus,
        *,
        result: Any = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            job.status = status
            job.result = result
            job.error = error
            job.finished_at = utc_now_iso()
            job._runner = None
            with closing(self._connect()) as conn:
                db.finish_job_run(
                    conn,
                    job.job_id,
                    status=status.value,
                    finished_at=job.finished_at,
                    result=result,
                    error=error,
                )
            self._prune_locked()

    def _prune_locked(self) -> None:
        limit = self.settings.job_history_limit
        while len(self._jobs) > limit:
            oldest_id, oldest = next(iter(self._jobs.items()))
            if oldest.status in {JobStatus.queued, JobStatus.running}:
                break
            self._jobs.pop(oldest_id)

    def _connect(self) -> sqlite3.Connection:
        return db.connect(self.settings.state_db, busy_timeout_ms=self.settings.db_busy_timeout_ms)


def _job_from_row(row: sqlite3.Row) -> Job:
    result = None
    if row["result_json"]:
        result = json.loads(row["result_json"])
    return Job(
        job_id=row["job_id"],
        kind=row["kind"],
        status=JobStatus(row["status"]),
        trigger=JobTrigger(row["trigger"]),
        schedule_id=row["schedule_id"],
        target_article_id=row["target_article_id"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        result=result,
        error=row["error"],
    )
