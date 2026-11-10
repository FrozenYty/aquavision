"""The PC end of the rig link (P2-17).

Two things are tested here that the firmware's own suite cannot test, because they are the server's half
of the conversation:

1. **The protocol grammar** - what a line becomes, and what a decision is written as. Pure functions, so
   this part is exhaustive rather than illustrative.
2. **The link state machine**, whose matrix is in `docs/rig-state-machine-en.md` §9: DOWN / OPENING /
   OPEN / STOPPING against start, port opened, open failed, read failed, write failed, stop. The pairs
   that matter are the failures - a port unplugged mid-read, a write on a closed port, a stop while the
   retry loop is asleep - because those are what a demo hits.

Nothing here needs hardware. The transport is a stand-in that can be told to fail.
"""

from __future__ import annotations

import threading
import time

import pytest
from app.rig import protocol
from app.rig.link import LinkState, RigLink
from app.rig.service import RigService
from app.vision.quality import Quality


class FakeTransport:
    """Enough of `serial.Serial` for the link, with failure on demand."""

    def __init__(self) -> None:
        self.written: list[str] = []
        self.incoming: list[bytes] = []
        self.closed = False
        self.fail_reads = False
        self.fail_writes = False

    def readline(self) -> bytes:
        if self.fail_reads:
            raise OSError("device disconnected")
        if self.incoming:
            return self.incoming.pop(0)
        time.sleep(0.01)
        return b""

    def write(self, data: bytes) -> int:
        if self.fail_writes:
            raise OSError("write failed")
        self.written.append(data.decode("ascii"))
        return len(data)

    def close(self) -> None:
        self.closed = True


def wait_until(predicate, timeout: float = 2.0) -> bool:
    """Poll a predicate; the link runs on threads, so tests wait for effects, not for calls."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class Recorder:
    def __init__(self) -> None:
        self.events: list[protocol.RigEvent] = []
        self.lock = threading.Lock()

    def __call__(self, event: protocol.RigEvent) -> None:
        with self.lock:
            self.events.append(event)

    def names(self) -> list[str]:
        with self.lock:
            return [event.name for event in self.events]


# Protocol ------------------------------------------------------------------------------------------


def test_a_line_becomes_an_event() -> None:
    event = protocol.parse("EVT TRIGGER 12345")
    assert event is not None
    assert event.name == "TRIGGER"
    assert event.arg(0) == "12345"


def test_a_command_is_not_an_event() -> None:
    assert protocol.parse("CMD PONG") is None
    assert protocol.parse("") is None
    assert protocol.parse("garbage") is None


def test_the_written_commands_are_the_ones_the_firmware_parses() -> None:
    assert protocol.ping() == "CMD PING\n"
    assert protocol.ready() == "CMD READY\n"
    assert protocol.result(94, "PASS") == "CMD RESULT 94 PASS NONE\n"
    assert (
        protocol.result(30, "RETAKE", protocol.REASON_LOW_LIGHT)
        == "CMD RESULT 30 RETAKE LOW_LIGHT\n"
    )


def test_the_reason_names_the_weakest_sub_score() -> None:
    dark = Quality(sharpness=90, brightness=20, colorcast=80, score=55, verdict="retake")
    assert protocol.reason_for(dark) == protocol.REASON_LOW_LIGHT
    soft = Quality(sharpness=10, brightness=90, colorcast=80, score=50, verdict="retake")
    assert protocol.reason_for(soft) == protocol.REASON_BLUR
    blue = Quality(sharpness=90, brightness=90, colorcast=10, score=55, verdict="retake")
    assert protocol.reason_for(blue) == protocol.REASON_COLOR_CAST


def test_a_retake_with_nothing_weak_says_unknown_rather_than_inventing_a_cause() -> None:
    even = Quality(sharpness=100, brightness=100, colorcast=100, score=100, verdict="ok")
    assert protocol.reason_for(even) == protocol.REASON_UNKNOWN


# Link ---------------------------------------------------------------------------------------------


def test_the_link_starts_opens_and_reports_events() -> None:
    transport = FakeTransport()
    recorder = Recorder()
    link = RigLink(lambda: transport, recorder)
    link.start()
    try:
        assert wait_until(lambda: link.state is LinkState.OPEN)
        transport.incoming.append(b"EVT TRIGGER 5000\n")
        assert wait_until(lambda: recorder.names() == ["TRIGGER"])
    finally:
        link.stop()


def test_stop_closes_the_port_and_leaves_no_thread_writing() -> None:
    transport = FakeTransport()
    link = RigLink(lambda: transport, lambda _event: None, keepalive_seconds=0.05)
    link.start()
    assert wait_until(lambda: link.state is LinkState.OPEN)
    link.stop()
    assert link.state is LinkState.STOPPING or link.state is LinkState.DOWN
    assert transport.closed
    written_at_stop = len(transport.written)
    time.sleep(0.2)
    assert len(transport.written) == written_at_stop


def test_a_write_on_a_closed_link_returns_false_instead_of_raising() -> None:
    link = RigLink(lambda: FakeTransport(), lambda _event: None)
    assert link.send(protocol.ping()) is False


def test_the_keepalive_pings_the_rig_without_being_asked() -> None:
    transport = FakeTransport()
    link = RigLink(lambda: transport, lambda _event: None, keepalive_seconds=0.05)
    link.start()
    try:
        assert wait_until(lambda: transport.written.count("CMD PING\n") >= 2)
    finally:
        link.stop()


def test_a_port_that_cannot_open_is_retried_rather_than_crashing() -> None:
    attempts = {"count": 0}

    def factory() -> FakeTransport:
        attempts["count"] += 1
        raise OSError("no such device")

    link = RigLink(factory, lambda _event: None, retry_seconds=0.01)
    link.start()
    try:
        assert wait_until(lambda: attempts["count"] >= 2)
        assert link.state is LinkState.OPENING
    finally:
        link.stop()


def test_a_failed_write_takes_the_link_down_and_it_recovers() -> None:
    transport = FakeTransport()
    link = RigLink(
        lambda: transport, lambda _event: None, keepalive_seconds=0.02, retry_seconds=0.02
    )
    link.start()
    try:
        assert wait_until(lambda: link.state is LinkState.OPEN)
        transport.fail_writes = True
        assert wait_until(lambda: link.counters.failures >= 1)
        assert wait_until(lambda: link.state is LinkState.OPEN)
        assert link.counters.opened >= 2
    finally:
        link.stop()


def test_a_handler_that_raises_does_not_kill_the_reader() -> None:
    transport = FakeTransport()
    seen: list[str] = []

    def handler(event: protocol.RigEvent) -> None:
        seen.append(event.name)
        raise RuntimeError("handler bug")

    link = RigLink(lambda: transport, handler, keepalive_seconds=1.0)
    link.start()
    try:
        assert wait_until(lambda: link.state is LinkState.OPEN)
        transport.incoming.extend([b"EVT PONG\n", b"EVT PONG\n"])
        assert wait_until(lambda: len(seen) >= 2)
    finally:
        link.stop()


# Service ------------------------------------------------------------------------------------------


class StubLink:
    """Accepts writes and records them; the service only needs `send`."""

    def __init__(self, ok: bool = True) -> None:
        self.sent: list[str] = []
        self.ok = ok

    def send(self, line: str) -> bool:
        if not self.ok:
            return False
        self.sent.append(line)
        return True


def test_a_trigger_becomes_a_verdict_over_the_wire() -> None:
    link = StubLink()
    service = RigService(link, lambda: Quality(90, 80, 70, 82, "ok"), threshold=60)  # type: ignore[arg-type]
    service.handle(protocol.RigEvent(name="TRIGGER", args=("100",), raw="EVT TRIGGER 100"))
    assert link.sent == ["CMD RESULT 82 PASS NONE\n"]


def test_a_low_score_becomes_a_retake_with_the_reason() -> None:
    link = StubLink()
    service = RigService(link, lambda: Quality(90, 20, 80, 45, "retake"), threshold=60)  # type: ignore[arg-type]
    service.handle(protocol.RigEvent(name="TRIGGER", args=("101",), raw="EVT TRIGGER 101"))
    assert link.sent == ["CMD RESULT 45 RETAKE LOW_LIGHT\n"]


def test_a_failed_capture_sends_nothing_and_lets_the_rig_time_out() -> None:
    link = StubLink()

    def broken() -> Quality:
        raise RuntimeError("camera busy")

    service = RigService(link, broken, threshold=60)
    service.handle(protocol.RigEvent(name="TRIGGER", args=("102",), raw="EVT TRIGGER 102"))
    assert link.sent == []


@pytest.mark.parametrize("name", ["TIMEOUT", "STRAY", "SCREEN", "HELLO", "TURBIDITY", "INVARIANT"])
def test_events_that_are_not_triggers_never_produce_a_verdict(name: str) -> None:
    link = StubLink()
    service = RigService(link, lambda: Quality(90, 90, 90, 90, "ok"), threshold=60)  # type: ignore[arg-type]
    service.handle(protocol.RigEvent(name=name, args=("1",), raw=f"EVT {name} 1"))
    assert link.sent == []
