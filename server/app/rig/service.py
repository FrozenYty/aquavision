"""What the server does when the rig speaks (P2-17).

The rig owns the verdicts in one sense and not in another: it asks for a frame with `EVT TRIGGER`, and
this module decides the answer. The decision is the quality gate that already exists - `vision.quality`
scores a frame, `settings.quality_threshold` turns the score into a verdict - so the two halves of the
product agree about what "good enough" means instead of inventing a second opinion here.

Deliberately absent: any retry, any queueing, any second attempt. A capture that fails sends **nothing**,
and the rig's own five-second timeout turns the silence into `RETAKE / NO REPLY` with no score. That is
the honest answer - the shot did fail - and it reuses the firmware's mechanism rather than adding a new
message the rig would have to learn.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.rig import protocol
from app.rig.link import RigLink
from app.vision.quality import Quality

log = logging.getLogger(__name__)

#: Score that accompanies a retake the server produced without a measurement. The rig renders no number
#: when it has none, and `0` would claim a measurement nobody made - so this value never leaves here;
#: `_verdict` is only called with a real `Quality`, and a failure sends nothing at all.
VERDICT_PASS = "PASS"
VERDICT_RETAKE = "RETAKE"


class RigService:
    """Turns a trigger into a verdict, and logs everything else the rig says."""

    def __init__(
        self,
        link: RigLink,
        capture: Callable[[], Quality],
        *,
        threshold: int | Callable[[], int] = 60,
    ) -> None:
        self._link = link
        self._capture = capture
        # An int for a test or a fixed deployment; a callable when the operator can change it, so
        # the verdict uses the value in force rather than the one the process started with (ADR 15).
        self._threshold = threshold if callable(threshold) else (lambda value=threshold: value)

    def handle(self, event: protocol.RigEvent) -> None:
        if event.name == "TRIGGER":
            self._on_trigger(event)
        elif event.name == "TIMEOUT":
            # The rig gave up waiting for us. Saying so in the log is the only honest response: the panel
            # has already told the operator, and a late verdict is rejected by the rig as a stray anyway.
            log.warning("rig: no verdict in time for trigger %s", event.arg(0))
        elif event.name == "STRAY":
            log.warning("rig: rig rejected a verdict we sent out of state: %s", event.raw)
        elif event.name == "SCREEN":
            log.info("rig: screen %s", " ".join(a for a in (event.arg(0), event.arg(1)) if a))
        elif event.name == "HELLO":
            log.info("rig: firmware %s connected", event.arg(0))
        elif event.name == "TURBIDITY":
            log.debug("rig: turbidity %s", event.arg(0))
        elif event.name == "INVARIANT":
            log.error("rig: firmware reports a broken state invariant: %s", event.raw)

    def _on_trigger(self, event: protocol.RigEvent) -> None:
        try:
            quality = self._capture()
        except Exception:  # noqa: BLE001 - camera busy, no camera, disk full: all the same answer
            # Silence, on purpose. The rig's five-second timeout reports NO REPLY, which is true.
            log.exception("rig: capture failed for trigger %s; staying silent", event.arg(0))
            return

        verdict, reason = self._verdict(quality)
        line = protocol.result(quality.score, verdict, reason)
        if self._link.send(line):
            log.info("rig: trigger %s -> %s %d (%s)", event.arg(0), verdict, quality.score, reason)
        else:
            log.warning("rig: verdict dropped, the port closed before it was sent")

    def _verdict(self, quality: Quality) -> tuple[str, str]:
        if quality.score >= self._threshold():
            return VERDICT_PASS, protocol.REASON_NONE
        return VERDICT_RETAKE, protocol.reason_for(quality)
