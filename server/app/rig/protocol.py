"""The serial grammar of the rig link, as pure functions.

The firmware's protocol is documented in `firmware/README.md` and the rules behind it in
`docs/rig-state-machine-en.md`. This module only translates lines: parsing turns one received line into
an event, the writers turn a decision into one outgoing line. No threads, no ports, no state — which is
what lets the interesting parts be tested without a board.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.vision.quality import Quality

EVENT_PREFIX: Final = "EVT "
COMMAND_PREFIX: Final = "CMD "

#: The reason tokens the firmware accepts, exactly as `rig_state.cpp` spells them. A token the rig does
#: not know becomes `UNKNOWN` on the panel, which is a silent wrong answer - so they are listed once,
#: here, and nowhere else in Python.
REASON_NONE: Final = "NONE"
REASON_LOW_LIGHT: Final = "LOW_LIGHT"
REASON_BLUR: Final = "BLUR"
REASON_COLOR_CAST: Final = "COLOR_CAST"
REASON_UNKNOWN: Final = "UNKNOWN"


@dataclass(frozen=True)
class RigEvent:
    """One line received from the rig."""

    name: str
    args: tuple[str, ...]
    raw: str

    def arg(self, index: int, default: str = "") -> str:
        return self.args[index] if index < len(self.args) else default


def parse(line: str) -> RigEvent | None:
    """Turn one line into an event, or None when it is not an event at all.

    The firmware ignores what it does not understand, and so does this: an unrecognised line costs a log
    line, never an exception in the reader thread.
    """
    text = line.strip()
    if not text.startswith(EVENT_PREFIX):
        return None
    parts = text[len(EVENT_PREFIX) :].split()
    if not parts:
        return None
    return RigEvent(name=parts[0], args=tuple(parts[1:]), raw=text)


def ping() -> str:
    return f"{COMMAND_PREFIX}PING\n"


def ready() -> str:
    return f"{COMMAND_PREFIX}READY\n"


def result(score: int, verdict: str, reason: str = REASON_NONE) -> str:
    """`CMD RESULT <score> <PASS|RETAKE> <REASON>`."""
    return f"{COMMAND_PREFIX}RESULT {score} {verdict} {reason}\n"


def reason_for(quality: Quality) -> str:
    """The cause the panel should name, taken from the weakest sub-score.

    A score without a cause tells the operator nothing to fix, so the reason is never `NONE` on a retake
    unless all three sub-scores are level - in which case `UNKNOWN` is the honest answer.
    """
    candidates = (
        (quality.sharpness, REASON_BLUR),
        (quality.brightness, REASON_LOW_LIGHT),
        (quality.colorcast, REASON_COLOR_CAST),
    )
    lowest, reason = min(candidates, key=lambda pair: pair[0])
    if lowest >= 100:
        return REASON_UNKNOWN
    return reason
