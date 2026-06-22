from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tac.application import pipeline
from tac.application.jobs import JobConflict, JobManager, JobQueueFull, JobTrigger
from tac.infrastructure.db import store as db
from tac.settings import Settings


class CronExpressionError(ValueError):
    pass


@dataclass(frozen=True)
class CronSchedule:
    expression: str
    minutes: frozenset[int]
    hours: frozenset[int]
    month_days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]

    @classmethod
    def parse(cls, expression: str) -> CronSchedule:
        parts = expression.split()
        if len(parts) != 5:
            raise CronExpressionError("cron expression must have 5 fields")
        return cls(
            expression=expression,
            minutes=_parse_field(parts[0], minimum=0, maximum=59),
            hours=_parse_field(parts[1], minimum=0, maximum=23),
            month_days=_parse_field(parts[2], minimum=1, maximum=31),
            months=_parse_field(parts[3], minimum=1, maximum=12),
            weekdays=_parse_weekday_field(parts[4]),
        )

    def matches(self, value: datetime) -> bool:
        cron_weekday = (value.weekday() + 1) % 7
        return (
            value.minute in self.minutes
            and value.hour in self.hours
            and value.day in self.month_days
            and value.month in self.months
            and cron_weekday in self.weekdays
        )

    def next_after(self, value: datetime) -> datetime | None:
        candidate = (value + timedelta(minutes=1)).replace(second=0, microsecond=0)
        deadline = candidate + timedelta(days=366)
        while candidate <= deadline:
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)
        return None


@dataclass(frozen=True)
class ScheduleDefinition:
    schedule_id: str
    kind: str
    cron: CronSchedule
    timezone: ZoneInfo
    runner_factory: Callable[[], Callable[[], object]]


class SchedulerService:
    def __init__(self, settings: Settings, job_manager: JobManager) -> None:
        self.settings = settings
        self.job_manager = job_manager
        self._schedules = _load_schedules(settings)
        self._task: asyncio.Task[None] | None = None
        self._last_fired: set[tuple[str, str]] = set()

    @property
    def enabled(self) -> bool:
        return self.settings.scheduler_enabled and bool(self._schedules)

    def start(self) -> None:
        if not self.enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="tac-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def schedules(self) -> list[dict[str, object]]:
        now_utc = datetime.now(tz=ZoneInfo("UTC"))
        items: list[dict[str, object]] = []
        for schedule in self._schedules:
            now = now_utc.astimezone(schedule.timezone)
            next_run = schedule.cron.next_after(now)
            latest = None
            with closing(
                db.connect(self.settings.state_db, busy_timeout_ms=self.settings.db_busy_timeout_ms)
            ) as conn:
                row = db.latest_schedule_job_run(conn, schedule.schedule_id)
                if row:
                    latest = _job_row_to_dict(row)
            items.append(
                {
                    "schedule_id": schedule.schedule_id,
                    "kind": schedule.kind,
                    "cron": schedule.cron.expression,
                    "timezone": str(schedule.timezone),
                    "enabled": self.enabled,
                    "next_run_at": next_run.isoformat() if next_run else None,
                    "latest_job": latest,
                }
            )
        return items

    async def trigger(self, schedule_id: str, *, manual: bool = False) -> dict[str, object]:
        schedule = self._schedule_by_id(schedule_id)
        job = self._submit_schedule(schedule, manual=manual)
        return job.as_dict()

    async def _run(self) -> None:
        while True:
            now_utc = datetime.now(tz=ZoneInfo("UTC"))
            for schedule in self._schedules:
                now = now_utc.astimezone(schedule.timezone)
                fire_key = (schedule.schedule_id, now.strftime("%Y-%m-%dT%H:%M"))
                if fire_key in self._last_fired or not schedule.cron.matches(now):
                    continue
                self._last_fired.add(fire_key)
                job = self._submit_schedule(schedule, manual=False)
                if job.status.value != "skipped":
                    asyncio.create_task(self.job_manager.run_job(job.job_id))
            await asyncio.sleep(self.settings.scheduler_poll_seconds)

    def _submit_schedule(self, schedule: ScheduleDefinition, *, manual: bool):
        trigger = JobTrigger.manual if manual else JobTrigger.schedule
        try:
            return self.job_manager.submit_job(
                schedule.kind,
                schedule.runner_factory(),
                trigger=trigger,
                schedule_id=schedule.schedule_id,
            )
        except (JobConflict, JobQueueFull) as exc:
            return self.job_manager.record_skipped_job(
                schedule.kind,
                trigger=trigger,
                schedule_id=schedule.schedule_id,
                error=str(exc),
            )

    def _schedule_by_id(self, schedule_id: str) -> ScheduleDefinition:
        for schedule in self._schedules:
            if schedule.schedule_id == schedule_id:
                return schedule
        raise KeyError(schedule_id)


def _load_schedules(settings: Settings) -> list[ScheduleDefinition]:
    if not settings.scheduler_enabled:
        return []
    try:
        timezone = ZoneInfo(settings.schedule_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"TAC_SCHEDULE_TIMEZONE is invalid: {settings.schedule_timezone}") from exc
    return [
        ScheduleDefinition(
            schedule_id="run",
            kind="run",
            cron=CronSchedule.parse(settings.schedule_run_cron),
            timezone=timezone,
            runner_factory=lambda: lambda: pipeline.run_all(settings),
        )
    ]


def _parse_field(raw: str, *, minimum: int, maximum: int) -> frozenset[int]:
    values: set[int] = set()
    for token in raw.split(","):
        values.update(_parse_token(token, minimum=minimum, maximum=maximum))
    if not values:
        raise CronExpressionError("cron field cannot be empty")
    return frozenset(values)


def _parse_weekday_field(raw: str) -> frozenset[int]:
    values = _parse_field(raw, minimum=0, maximum=7)
    normalized = {0 if value == 7 else value for value in values}
    return frozenset(normalized)


def _parse_token(raw: str, *, minimum: int, maximum: int) -> set[int]:
    if not raw:
        raise CronExpressionError("cron field contains an empty token")
    base, step = raw, 1
    if "/" in raw:
        base, step_raw = raw.split("/", 1)
        step = int(step_raw)
        if step <= 0:
            raise CronExpressionError("cron step must be positive")
    if base == "*":
        start, end = minimum, maximum
    elif "-" in base:
        start_raw, end_raw = base.split("-", 1)
        start, end = int(start_raw), int(end_raw)
    else:
        start = end = int(base)
    if start < minimum or end > maximum or start > end:
        raise CronExpressionError(f"cron value must be between {minimum} and {maximum}")
    return set(range(start, end + 1, step))


def _job_row_to_dict(row) -> dict[str, object]:
    result = None
    if row["result_json"]:
        import json

        result = json.loads(row["result_json"])
    return {
        "job_id": row["job_id"],
        "kind": row["kind"],
        "status": row["status"],
        "trigger": row["trigger"],
        "schedule_id": row["schedule_id"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "target_article_id": row["target_article_id"],
        "result": result,
        "error": row["error"],
    }
