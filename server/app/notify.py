"""In-app messages for the events FR-M8-02 names (P3-09, AC-29).

`sys_message` had a table, a list route and a mark-read route, and **nothing ever wrote a row**: the
unread count was permanently zero and the page was decorative. The requirement names three events - a
capture failure, a job failure and a finished report - and two rules that decide how they are written:

- **the same type and object collapse into one message within an hour**, so a disk that is full for a
  whole session produces one message, not one per frame;
- **a message never blocks the main flow.** `notify` opens its own session and swallows its own errors
  into the log: the capture that failed must still answer with the reason it failed, and the task that
  failed must still be recorded as failed. Nothing here can change an outcome; it can only add a row.

The row is targeted at a role when the event belongs to one, and left open (`target_role` NULL, which
the list route already reads as "everyone") when it concerns the system as a whole.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import SysMessage

log = logging.getLogger("aquavision.notify")

#: FR-M8-02's business rule: the same type and object collapse within an hour. One stated number.
COLLAPSE_WINDOW = timedelta(hours=1)

#: `sys_message.level` (data model §3.9).
LEVEL_INFO = 1
LEVEL_WARN = 2
LEVEL_CRIT = 3


def _write(
    session_factory: sessionmaker,
    *,
    msg_type: str,
    level: int,
    title: str,
    content: str | None = None,
    target_role: str | None = None,
    ref_type: str | None = None,
    ref_id: str | None = None,
) -> bool:
    """Write one message unless the same type and object already has one inside the window."""
    since = datetime.now(UTC).replace(tzinfo=None) - COLLAPSE_WINDOW
    with session_factory() as session:
        conditions = [
            SysMessage.msg_type == msg_type,
            SysMessage.created_at >= since,
        ]
        if ref_id is not None:
            # "Same type and object" needs the object; without one, only the type can collapse.
            conditions.extend([SysMessage.ref_type == ref_type, SysMessage.ref_id == ref_id])
        if session.scalar(select(SysMessage.msg_id).where(*conditions).limit(1)) is not None:
            return False
        session.add(
            SysMessage(
                msg_type=msg_type,
                level=level,
                title=title[:128],
                content=content[:512] if content else None,
                target_role=target_role,
                ref_type=ref_type,
                ref_id=ref_id,
                is_read=0,
            )
        )
        session.commit()
        return True


def notify(session_factory: sessionmaker, **fields) -> bool:
    """`_write`, with its errors kept out of the caller's way. Returns whether a row was written."""
    try:
        return _write(session_factory, **fields)
    except Exception:  # noqa: BLE001 - a message never blocks the main flow (FR-M8-02)
        log.exception("could not write the %s message", fields.get("msg_type"))
        return False
