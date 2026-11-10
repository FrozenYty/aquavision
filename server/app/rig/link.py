"""The PC end of the rig link: a small state machine around one serial port (P2-17).

The rig has its own state machine - five screens, two link states, documented in
`docs/rig-state-machine-en.md` - and this is the other half of the same conversation. Its job is narrow:
hold the port open, send `CMD PING` every two seconds because the rig's liveness rule requires it, hand
every received event to a callback, and get out of the way.

The states are written out as a matrix in the same document, because the pairs nobody writes down are
exactly where a serial link misbehaves: a write attempted on a closed port, a keepalive thread outliving
its transport, two reconnect attempts racing each other.

| State \\ Event | start | port opened | open failed | read failed | write failed | stop | tick | line in |
|---|---|---|---|---|---|---|---|---|
| DOWN | OPENING | - | - | - | - | STOPPING | - | - |
| OPENING | ignored | OPEN | DOWN (retry) | - | - | STOPPING | - | - |
| OPEN | ignored | - | - | DOWN (retry) | DOWN (retry) | STOPPING | OPEN | OPEN |
| STOPPING | ignored | ignored | ignored | - | - | - | ignored | ignored |

Two invariants follow, and the code checks both:

1. **A transport exists if and only if the state is OPEN.** A write on a closed port is an exception in
   another thread, which is how a keepalive thread kills a process.
2. **Only OPEN emits keepalives.** A retry loop that also pings is two writers on one port.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol, runtime_checkable

from app.rig import protocol

log = logging.getLogger(__name__)

#: Seconds between `CMD PING` writes. The rig declares itself OFFLINE after ten seconds of silence, so
#: the contract is "at least every two", which leaves four missed beats before the panel changes.
KEEPALIVE_SECONDS = 2.0

#: Seconds to wait before trying the port again after a failure. Long enough not to spin on a cable that
#: is out, short enough that plugging it back in feels immediate.
RETRY_SECONDS = 2.0


@runtime_checkable
class Transport(Protocol):
    """The part of `serial.Serial` this module uses, so a test can stand in for it."""

    def readline(self) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def close(self) -> None: ...


class LinkState(Enum):
    DOWN = auto()  # no port; either not opened yet or closed after a failure
    OPENING = auto()  # trying to open, or waiting to retry
    OPEN = auto()  # port held, reader and keepalive running
    STOPPING = auto()  # shutdown was requested; threads are winding down


@dataclass
class LinkCounters:
    """What the link has done, for the log and the tests. No metrics endpoint yet."""

    opened: int = 0
    failures: int = 0
    lines_in: int = 0
    pings: int = 0


class RigLink:
    """One serial port, held open, kept alive, reported."""

    def __init__(
        self,
        open_transport: Callable[[], Transport],
        on_event: Callable[[protocol.RigEvent], None],
        *,
        keepalive_seconds: float = KEEPALIVE_SECONDS,
        retry_seconds: float = RETRY_SECONDS,
    ) -> None:
        self._open = open_transport
        self._on_event = on_event
        self._keepalive_seconds = keepalive_seconds
        self._retry_seconds = retry_seconds
        self._state = LinkState.DOWN
        self._transport: Transport | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._connection_stop: threading.Event | None = None
        self.counters = LinkCounters()

    @property
    def state(self) -> LinkState:
        return self._state

    def start(self) -> None:
        """Start the reader; opening, retrying and reconnecting all happen inside it."""
        with self._lock:
            if self._state is not LinkState.DOWN:
                return
            self._state = LinkState.OPENING
        self._stop.clear()
        reader = threading.Thread(target=self._run, name="rig-link", daemon=True)
        reader.start()
        self._threads.append(reader)

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            if self._state is LinkState.STOPPING:
                return
            self._state = LinkState.STOPPING
        self._stop.set()
        # Closing unblocks a readline that is waiting on a port that will never speak again.
        self._close_transport()
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()

    def send(self, line: str) -> bool:
        """Write one command. False when there is no open port - never an exception in a caller."""
        with self._lock:
            if self._state is not LinkState.OPEN or self._transport is None:
                return False
            transport = self._transport
        try:
            transport.write(line.encode("ascii"))
            return True
        except Exception:  # noqa: BLE001 - any transport failure means the same thing: the link is gone
            log.warning("rig: write failed, dropping the port", exc_info=True)
            self._fail()
            return False

    # Internal ---------------------------------------------------------------------------------------

    def _fail(self) -> None:
        """A port that stopped working. Back to OPENING so the retry loop takes over."""
        with self._lock:
            if self._state in (LinkState.STOPPING, LinkState.DOWN):
                return
            self._state = LinkState.OPENING
            self.counters.failures += 1
            connection_stop = self._connection_stop
        if connection_stop is not None:
            connection_stop.set()
        self._close_transport()

    def _close_transport(self) -> None:
        with self._lock:
            transport, self._transport = self._transport, None
        if transport is not None:
            with contextlib.suppress(Exception):
                transport.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                transport = self._open()
            except Exception:  # noqa: BLE001 - a missing cable is the normal case, not a crash
                with self._lock:
                    if self._state is not LinkState.STOPPING:
                        self._state = LinkState.OPENING
                log.info("rig: no port yet, retrying in %.1fs", self._retry_seconds)
                self._stop.wait(self._retry_seconds)
                continue

            with self._lock:
                if self._state is LinkState.STOPPING:
                    self._state = LinkState.DOWN
                self._transport = transport
                if self._state is not LinkState.STOPPING:
                    self._state = LinkState.OPEN
                    self.counters.opened += 1
                self._connection_stop = threading.Event()
                connection_stop = self._connection_stop
            log.info("rig: port open")

            keepalive = threading.Thread(
                target=self._keepalive, args=(connection_stop,), name="rig-keepalive", daemon=True
            )
            keepalive.start()
            self._threads.append(keepalive)

            try:
                self._read_loop(transport, connection_stop)
            finally:
                # The connection is over, whatever ended it: close the port, wait for the keepalive of
                # *this* connection, and go back to the retry loop. The global stop event is only for
                # shutdown - using it here ended the reader for good the first time a write failed.
                connection_stop.set()
                keepalive.join(timeout=self._keepalive_seconds + 1)
                self._close_transport()

            if self._stop.is_set():
                break
            self._stop.wait(self._retry_seconds)

        with self._lock:
            if self._state is not LinkState.STOPPING:
                self._state = LinkState.DOWN

    def _read_loop(self, transport: Transport, connection_stop: threading.Event) -> None:
        while not self._stop.is_set() and not connection_stop.is_set():
            if self._state is not LinkState.OPEN:
                # A write failure moved the state; this connection is finished and must not linger.
                return
            try:
                raw = transport.readline()
            except Exception:  # noqa: BLE001 - unplugged while reading is an event, not a fault
                log.warning("rig: read failed, dropping the port", exc_info=True)
                self._fail()
                return
            if not raw:
                continue
            text = raw.decode("ascii", errors="replace").strip()
            if not text:
                continue
            self.counters.lines_in += 1
            event = protocol.parse(text)
            if event is not None:
                self._dispatch(event)

    def _dispatch(self, event: protocol.RigEvent) -> None:
        try:
            self._on_event(event)
        except Exception:  # noqa: BLE001 - one bad handler must not kill the reader
            log.exception("rig: handler failed on %s", event.name)

    def _keepalive(self, connection_stop: threading.Event) -> None:
        while not connection_stop.wait(self._keepalive_seconds):
            if self._stop.is_set():
                return
            if not self.send(protocol.ping()):
                return
            self.counters.pings += 1


def iter_events(events: Iterable[protocol.RigEvent]) -> Iterable[protocol.RigEvent]:
    """Convenience for tests and log tooling: iterate events unchanged."""
    return events


def _now() -> float:
    return time.monotonic()
