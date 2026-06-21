from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Any
from uuid import uuid4

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


@dataclass
class Job:
    job_id: str
    kind: str
    status: JobStatus
    created_at: str
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

    def submit_job(
        self,
        kind: str,
        runner: Callable[[], Any],
        *,
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
                created_at=utc_now_iso(),
                target_article_id=target_article_id,
                _runner=runner,
            )
            self._jobs[job.job_id] = job
            self._prune_locked()
            return job

    async def run_job(self, job_id: str) -> None:
        job = self.get_job(job_id)
        async with self._execution_semaphore:
            with self._lock:
                if job.status != JobStatus.queued:
                    return
                job.status = JobStatus.running
                job.started_at = utc_now_iso()
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
            if not job:
                raise JobNotFound(job_id)
            return job

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return list(reversed(list(self._jobs.values())))

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
            self._prune_locked()

    def _prune_locked(self) -> None:
        limit = self.settings.job_history_limit
        while len(self._jobs) > limit:
            oldest_id, oldest = next(iter(self._jobs.items()))
            if oldest.status in {JobStatus.queued, JobStatus.running}:
                break
            self._jobs.pop(oldest_id)
