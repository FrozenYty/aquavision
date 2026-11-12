"""The values an operator can change at runtime, read where they take effect (P3-19, ADR 15).

`PATCH /api/params` has always persisted `sys_param` rows and written an audit line, and no module ever
read them: every consumer used `Settings`, loaded once at process start. The parameters page therefore
edited a copy nobody consulted, and the promise that a change needs no restart was empty.

Three rules make a change real, and they are ADR 15's:

- **one accessor**, `effective()`: the stored value, or the configured default when no row exists;
- **consumers call it at the moment they need the number** - the capture route when it judges quality,
  the worker when it decides how many tasks to claim - never once at start-up;
- **each parameter declares its range once**, in `PARAMETERS`: the page refuses a value outside it and
  this module ignores one that got in some other way, because a concurrency of zero is not a setting,
  it is a stopped queue.

The cache is a short time-to-live rather than an invalidation push. With one process, invalidating on
write would be tidier; with more than one, the writer's invalidation reaches only itself, and being
correct only in the single-process deployment is the assumption that becomes a bug the day a second
process starts. A delay of seconds is invisible to a person who just clicked a form.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.models import SysParam

log = logging.getLogger("aquavision.params")

#: How long a read value is trusted. ADR 15 asks for a stated number in one place, not a hidden default.
CACHE_TTL_SECONDS = 2.0


class Bounds(NamedTuple):
    low: int
    high: int


#: Every parameter the operator may change (FR-M7-01), with its accepted range. The write path and
#: the accessor both read this declaration, so a range cannot be enforced in one place and not the
#: other. Keys are `Settings` attribute names: the configured default is the fallback.
PARAMETERS: dict[str, Bounds] = {
    "retention_days": Bounds(1, 3650),
    "max_concurrency": Bounds(1, 32),
    "detect_interval_ms": Bounds(50, 10000),
    "quality_threshold": Bounds(0, 100),
    "camera_index": Bounds(0, 9),
}

_lock = threading.Lock()
#: (database, parameter) -> (monotonic read time, value). The database is part of the key because one
#: process can talk to more than one: the test suite does, and so does a developer running it beside the
#: application. Keyed by the parameter alone, one database's limit would be handed to another for the
#: length of the TTL - a wrong answer with no error to notice.
_cache: dict[tuple[str, str], tuple[float, int]] = {}


def _scope(session_factory: sessionmaker) -> str:
    """Which database this factory talks to, as a cache key."""
    bind = getattr(session_factory, "kw", {}).get("bind")
    url = getattr(bind, "url", None)
    return str(url) if url is not None else repr(bind)


def effective(session_factory: sessionmaker, key: str, settings: Settings | None = None) -> int:
    """The value in force for `key` at this moment.

    A stored value that is not a number, or is outside the declared range, is a corrupt row rather
    than a setting: it is logged and the configured default is used. Obeying it would let a bad write
    stop the queue, which is the failure the range exists to prevent.
    """
    bounds = PARAMETERS[key]  # KeyError for a key that is not editable: a code mistake, not input
    scope = _scope(session_factory)
    now = time.monotonic()
    with _lock:
        cached = _cache.get((scope, key))
        if cached is not None and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

    value = int(getattr(settings or get_settings(), key))
    with session_factory() as session:
        row = session.scalar(select(SysParam).where(SysParam.param_key == key))
    if row is not None:
        try:
            stored = int(row.param_value)
        except (TypeError, ValueError):
            log.warning("sys_param %s=%r is not a number; using %s", key, row.param_value, value)
        else:
            if bounds.low <= stored <= bounds.high:
                value = stored
            else:
                log.warning(
                    "sys_param %s=%s is outside %s..%s; using %s",
                    key,
                    stored,
                    bounds.low,
                    bounds.high,
                    value,
                )

    with _lock:
        _cache[(scope, key)] = (time.monotonic(), value)
    return value


def forget() -> None:
    """Drop every cached value. Tests use it where the TTL delay is not what is under test."""
    with _lock:
        _cache.clear()
