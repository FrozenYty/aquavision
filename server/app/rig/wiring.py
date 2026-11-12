"""Wiring: the settings, the serial port and the verdict handler, assembled once (P2-17).

Kept apart from `main.py` so the assembly can be read without the rest of the application around it, and
so the tests can build a service over a fake transport without touching the app factory.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.params import effective
from app.rig.link import RigLink
from app.rig.service import RigService
from app.vision.quality import Quality

log = logging.getLogger(__name__)


def build_link(settings: Settings, session_factory: sessionmaker | None = None) -> RigLink | None:
    """The link when a port is configured, otherwise None.

    None is the normal answer: a developer's machine, CI, and every machine that is not at the rig run
    without a board, and the application must not treat that as a degraded state.
    """
    if not settings.rig_port:
        return None

    import serial  # imported here so a machine without pyserial still runs the web application

    def open_transport() -> serial.Serial:
        return serial.Serial(
            settings.rig_port,
            settings.rig_baud,
            timeout=0.5,
        )

    service: RigService | None = None
    link = RigLink(
        open_transport,
        on_event=lambda event: service.handle(event) if service is not None else None,
        keepalive_seconds=settings.rig_keepalive_seconds,
    )
    # The panel's verdict follows the same threshold as the capture route, read when the trigger
    # arrives; without a database the link still works, at the configured value (ADR 15).
    threshold: int | Callable[[], int] = settings.quality_threshold
    if session_factory is not None:

        def live_threshold() -> int:
            """The threshold in force when a trigger arrives, not the one from start-up (ADR 15)."""
            return effective(session_factory, "quality_threshold", settings)

        threshold = live_threshold
    service = RigService(link, capture=_camera_capture, threshold=threshold)
    log.info("rig: link configured on %s", settings.rig_port)
    return link


def _camera_capture() -> Quality:
    """Grab one frame and score it, through the same code the capture endpoint uses.

    Imported lazily for the same reason as `serial`: a machine with no camera still serves every page
    that does not need one, and the failure surfaces when a rig actually asks for a frame.
    """
    from app.vision.capture import CameraSource
    from app.vision.quality import score_frame

    source = CameraSource()
    source.open()
    try:
        return score_frame(source.read())
    finally:
        source.close()
