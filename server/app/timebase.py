"""The one interpretation of a calendar day (ADR 14).

Storage keeps `captured_at` naive UTC: two deployments' rows must be comparable, and UTC is the only
representation where that is true. Everything an operator calls a date - a filter range, a bucket, a
report period, the offset on a timestamp - is that same instant read in **one configured zone**,
`AV_TIMEZONE`. This module is the only place the conversion happens; a second implementation elsewhere
is how the frame filter, the dashboard and the report came to disagree.

Deliberately absent: anything that writes the database. The column stays naive UTC; `day_bounds` and
the outbound `iso` are the two directions across the boundary.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings

#: The zone a deployment operates in unless it says otherwise (ADR 14).
DEFAULT_TIMEZONE = "Asia/Shanghai"


def zone() -> ZoneInfo:
    """The configured IANA zone.

    Not cached here: `get_settings` already is, and this module must see a setting changed after that
    cache is cleared (the tests do exactly that). `ZoneInfo` itself caches by key.
    """
    return ZoneInfo(get_settings().timezone)


def now() -> datetime:
    """The current instant, aware, in the configured zone."""
    return datetime.now(zone())


def now_utc() -> datetime:
    """The current instant as storage holds it: naive UTC."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_zone(value: datetime) -> datetime:
    """An aware timestamp in the configured zone; a naive one is UTC, which is what storage means."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(zone())


def as_utc(value: datetime) -> datetime:
    """The storage form of a timestamp arriving from outside: naive UTC.

    An offset-aware value is converted; a naive one is taken to be UTC already, the same assumption
    `to_zone` makes in the other direction. A reader must never have to guess what a bare wall clock
    meant, so inbound timestamps should carry an offset (api-contract §5).
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=None)
    return value.astimezone(UTC).replace(tzinfo=None)


def iso(value: datetime | None, *, timespec: str = "milliseconds") -> str | None:
    """The contract's outbound timestamp: ISO 8601 carrying the configured offset.

    Milliseconds, not seconds: the contract's own example is `2026-11-03T19:30:12.418+08:00`, and a
    capture pipeline running at five frames a second routinely produces frames inside the same second.
    Truncated to seconds they would render as the same moment, and the operator could not tell which
    came first. SQL still orders on the stored column, so this is about what a person reads.
    """
    if value is None:
        return None
    return to_zone(value).isoformat(timespec=timespec)


def local_date(value: datetime) -> date:
    """The calendar date an instant falls on in the configured zone."""
    return to_zone(value).date()


def recent_days(days: int) -> list[date]:
    """The last `days` local calendar dates, oldest first, ending today in the configured zone."""
    today = now().date()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def day_bounds(start: str | None, end: str | None) -> tuple[datetime | None, datetime | None]:
    """The stored-UTC range for an inclusive local day range given as `YYYY-MM-DD` strings.

    A day is 00:00:00 to 23:59:59.999999 in the configured zone. The returned upper bound is exclusive
    - the next local midnight - because the column is an instant, not a date; that is what makes both
    ends inclusive for the caller. Raises `ValueError` naming the value that is not a date.
    """
    lower = _local_midnight(_parse_day(start)) if start else None
    upper = _local_midnight(_parse_day(end)) + timedelta(days=1) if end else None
    return lower, upper


def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as err:
        raise ValueError(value) from err


def _local_midnight(day: date) -> datetime:
    """Midnight at the start of a local day, expressed as the naive UTC the column stores."""
    return (
        datetime.combine(day, datetime.min.time(), tzinfo=zone())
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
