"""Wiring: the settings, the wire and the verdict handler, assembled once (P2-17, P3-38).

Kept apart from `main.py` so the assembly can be read without the rest of the application around it, and
so the tests can build a service over a fake transport without touching the app factory.

Two wires reach the same conversation (`docs/rig-transport-en.md` §8): the serial port this module has
always opened, and the BLE client, which is selected by `AV_RIG_TRANSPORT=ble`. Nothing above this module
knows which one it got - `RigLink` takes the factory and calls `readline`, `write` and `close` either way.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.params import effective
from app.rig.link import RigLink, Transport
from app.rig.service import RigService
from app.vision.quality import Quality

if TYPE_CHECKING:
    from app.rig.ble import BleClient

log = logging.getLogger(__name__)

#: How long `stop` waits for the BLE client's worker after the link is closed. A client inside a scan
#: cannot be interrupted before the scan's own timeout, and the radio has to be released before the
#: process goes away.
BLE_STOP_SECONDS = 25.0


class BleRigLink(RigLink):
    """A `RigLink` over the BLE client, which owns the client's worker thread and its radio as well.

    `RigLink.stop` closes the transport and joins its own threads; the client has a worker of its own and a
    link to release, and only the assembly that built both can stop both. Written as a class rather than a
    callback because the shutdown path is the one place a forgotten call leaves a radio held open.
    """

    def __init__(self, client: BleClient, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._client = client

    def stop(self, timeout: float = 5.0) -> None:
        super().stop(timeout)
        self._client.stop(timeout=BLE_STOP_SECONDS)


def build_link(settings: Settings, session_factory: sessionmaker | None = None) -> RigLink | None:
    """The link when a wire is configured, otherwise None.

    None is the normal answer: a developer's machine, CI, and every machine that is not at the rig run
    without a board, and the application must not treat that as a degraded state. It is also the answer
    for `serial` with no port; `ble` needs none, because the rig is found by its advertised name.
    """
    client: BleClient | None = None
    open_transport: Callable[[], Transport]

    if settings.rig_transport == "ble":
        # Imported here, like `serial` below, so a machine without bleak still serves every page that does
        # not talk to the rig.
        from app.rig.ble import RIG_NAME, BleClient

        client = BleClient()
        # C1, once, at service start-up (§8). `RigLink`'s factory only *looks* at the client's state, so
        # its own retry loop cannot start an attempt, extend one or restart the budget.
        client.request_link()
        open_transport = client.open_transport
        log.info("rig: link configured over BLE (%s)", RIG_NAME)
    else:
        if not settings.rig_port:
            return None

        import serial  # imported here so a machine without pyserial still runs the web application

        def open_transport() -> serial.Serial:
            return serial.Serial(
                settings.rig_port,
                settings.rig_baud,
                timeout=0.5,
            )

        log.info("rig: link configured on %s", settings.rig_port)

    service: RigService | None = None
    if client is None:
        link: RigLink = RigLink(
            open_transport,
            on_event=lambda event: service.handle(event) if service is not None else None,
            keepalive_seconds=settings.rig_keepalive_seconds,
        )
    else:
        link = BleRigLink(
            client,
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
