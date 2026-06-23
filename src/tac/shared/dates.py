from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from time import struct_time
from typing import Any


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_datetime(value: Any, *, date_as_end: bool = False) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return utc_iso(value)
    if isinstance(value, date):
        return utc_iso(datetime.combine(value, time.min, tzinfo=UTC))
    if isinstance(value, struct_time) or (
        isinstance(value, tuple)
        and len(value) >= 9
        and all(isinstance(item, int) for item in value[:6])
    ):
        return utc_iso(datetime.fromtimestamp(calendar.timegm(value[:9]), tz=UTC))
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) == 10:
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError:
            pass
        else:
            parsed = datetime.combine(parsed_date, time.min, tzinfo=UTC)
            if date_as_end:
                parsed += timedelta(days=1)
            return utc_iso(parsed)
    normalized = text.replace("Z", "+00:00")
    try:
        return utc_iso(datetime.fromisoformat(normalized))
    except ValueError:
        pass
    try:
        return utc_iso(parsedate_to_datetime(text))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class TimeRange:
    since: str | None = None
    until: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.since or self.until)

    def contains(self, published_at: str | None) -> bool:
        if not published_at:
            return True
        parsed = parse_datetime(published_at)
        if not parsed:
            return True
        if self.since and parsed < self.since:
            return False
        return not (self.until and parsed >= self.until)


def build_time_range(
    *,
    since: str | None,
    until: str | None,
    since_days: int | None,
    now: datetime | None = None,
) -> TimeRange:
    parsed_since = parse_datetime(since)
    parsed_until = parse_datetime(until, date_as_end=True)
    if not parsed_since and since_days is not None:
        current = now or datetime.now(UTC)
        parsed_since = utc_iso(current - timedelta(days=since_days))
    return TimeRange(since=parsed_since, until=parsed_until)
