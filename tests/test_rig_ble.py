"""The PC end of the rig link over BLE (P3-38).

Three things are tested here, and the first two need no radio at all:

1. **The §7 matrix, cell by cell.** The table is transcribed again in this file, independently of the
   code, and compared with what the machine does - so a cell that moves fails here rather than on the
   bench. This is the transition proof the implementation owes before it is ever run against a rig.
2. **The rules the matrix does not carry**: the attempt budget and `Failed` after five of them, the
   counter reset that only `Streaming` performs, and the rejected cells that have to be reported.
3. **The composition with `rig/link.py`**, over a fake radio: a transport exists if and only if the
   client is `Streaming`, and once it does, `RigLink` talks through it without learning which wire it is
   on.

`FakeRadio` is the stand-in for `bleak`, including the two things a radio does on its own: it can drop a
link, and it can hand back notifications. Nothing here opens a socket or an adapter.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pytest
from app.config import Settings
from app.rig.ble import (
    MATRIX,
    BleClient,
    BleEvent,
    BleLinkCore,
    BleState,
    LinkNotStreaming,
    Outcome,
)
from app.rig.link import LinkState, RigLink
from app.rig.wiring import BleRigLink, build_link
from pydantic import ValidationError

#: The events in §7's column order C1..C10. The test walks the table in this order, so a row is compared
#: column by column rather than by whichever cell happens to exist.
EVENTS = [
    BleEvent.REQUEST_LINK,
    BleEvent.RIG_SEEN,
    BleEvent.SCAN_TIMEOUT,
    BleEvent.CONNECTED,
    BleEvent.ATTEMPT_FAILED,
    BleEvent.SUBSCRIBED,
    BleEvent.SUBSCRIBE_TIMEOUT,
    BleEvent.LINE_IN,
    BleEvent.LINK_LOST,
    BleEvent.BACKOFF_EXPIRED,
]

#: §7 transcribed by hand: ten cells per row, in the order above. `N` is ignored, `H` is handled in
#: place, `R:<state>` is rejected, and any other word is the state the event moves to. `RECONNECTING`
#: in a failure cell is also where `Failed` appears on the fifth attempt - the counter is not a cell,
#: and `test_the_fifth_failure_is_the_one_that_stops` is what checks it.
EXPECTED: dict[BleState, list[str]] = {
    BleState.DISCONNECTED: ["SCANNING", "N", "N", "N", "N", "N", "N", "N", "N", "N"],
    BleState.SCANNING: ["H", "CONNECTING", "RECONNECTING", "N", "N", "N", "N", "N", "N", "N"],
    BleState.CONNECTING: ["H", "N", "N", "SUBSCRIBING", "RECONNECTING", "N", "N", "N", "N", "N"],
    BleState.SUBSCRIBING: [
        "H",
        "N",
        "N",
        "R:SUBSCRIBING",
        "N",
        "STREAMING",
        "RECONNECTING",
        "N",
        "N",
        "N",
    ],
    BleState.STREAMING: [
        "R:STREAMING",
        "N",
        "N",
        "R:STREAMING",
        "N",
        "H",
        "N",
        "H",
        "RECONNECTING",
        "N",
    ],
    BleState.RECONNECTING: ["H", "N", "N", "N", "N", "N", "N", "N", "N", "SCANNING"],
    BleState.FAILED: ["SCANNING", "N", "N", "N", "N", "N", "N", "N", "N", "N"],
}


class FakeRadio:
    """Enough of `bleak` for the client, with each step failing on demand.

    `find` answers from `seen`, so a test can make a rig appear, disappear and come back. `deliver` and
    `drop` are the two things a radio does without being asked, and both are safe to call from the test's
    thread: the client's notification path and its disconnect handler are built for exactly that.
    """

    def __init__(self) -> None:
        self.address = "AA:BB:CC:DD:EE:FF"
        self.seen = True
        self.connect_fails = False
        self.subscribe_fails = False
        self.mtu_value = 247
        self.scans = 0
        self.connects = 0
        self.subscribes = 0
        self.disconnects = 0
        self.goodbyes = 0
        self.events: list[str] = []
        #: When true, `disconnect` reports the teardown back through the handler, the way bleak does.
        self.report_own_disconnects = False
        self.written: list[bytes] = []
        self._on_bytes: object | None = None
        self._handler: object | None = None

    def on_disconnect(self, handler) -> None:  # noqa: ANN001 - the protocol's signature
        self._handler = handler

    async def find(self, name: str, service_uuid: str, timeout: float) -> str | None:
        self.scans += 1
        return self.address if self.seen else None

    async def connect(self, address: str, timeout: float) -> None:
        self.connects += 1
        if self.connect_fails:
            raise OSError("the connection attempt failed")

    async def subscribe(self, tx_uuid: str, on_bytes, timeout: float) -> None:  # noqa: ANN001
        self.subscribes += 1
        if self.subscribe_fails:
            raise TimeoutError("no acknowledgement")
        self._on_bytes = on_bytes

    async def write(self, rx_uuid: str, data: bytes) -> None:
        self.written.append(data)

    async def unsubscribe(self, tx_uuid: str) -> None:
        self.goodbyes += 1
        self.events.append("unsubscribe")
        self._on_bytes = None  # the rig stops notifying

    async def disconnect(self) -> None:
        self.disconnects += 1
        self.events.append("disconnect")
        if self.report_own_disconnects and self._handler is not None:
            # bleak reports every disconnect through one callback, including the one this client asked
            # for; the real adapter filters those out, and this flag is how a test reproduces the case
            # where a late report of the *old* link arrives while the new one is being built.
            self._handler()

    def mtu(self) -> int:
        return self.mtu_value

    # Test helpers -----------------------------------------------------------------------------------

    def deliver(self, data: bytes) -> None:
        """A notification from the rig, as the radio would hand it over."""
        assert self._on_bytes is not None, "nothing is subscribed"
        self._on_bytes(data)  # type: ignore[operator]

    def drop(self) -> None:
        """The link goes away without anybody asking it to: §7's C9 from the radio's side."""
        assert self._handler is not None, "no disconnect handler was registered"
        self._handler()  # type: ignore[operator]


def wait_until(predicate, timeout: float = 5.0) -> bool:
    """Poll a predicate; the client works on threads, so tests wait for effects, not for calls."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return False


class FakeSerial:
    """A serial port that is never read: the settings test only asks which wire `build_link` chose."""

    def readline(self) -> bytes:
        return b""

    def write(self, data: bytes) -> int:
        return len(data)

    def close(self) -> None:
        pass


def build_client(radio: FakeRadio | None = None, **overrides) -> BleClient:
    """A client whose attempt budget is fast enough for a test: the timings are the design's, the waits
    between attempts are not waited out."""
    radio = radio if radio is not None else FakeRadio()
    options = {
        "backoff": (0.01, 0.02, 0.04, 0.08, 0.16),
        "scan_timeout": 0.05,
        "connect_timeout": 0.05,
        "subscribe_timeout": 0.05,
    }
    options.update(overrides)
    return BleClient(radio=radio, **options)


# The matrix ----------------------------------------------------------------------------------------


def test_every_cell_of_the_matrix_is_the_one_the_document_writes() -> None:
    for state, cells in EXPECTED.items():
        assert len(cells) == len(EVENTS)
        for event, expected in zip(EVENTS, cells, strict=True):
            cell = MATRIX[state][event]
            if expected == "N":
                assert cell.outcome is Outcome.IGNORED, f"{state.name}/{event.name}"
            elif expected == "H":
                assert cell.outcome is Outcome.HANDLED, f"{state.name}/{event.name}"
            elif expected.startswith("R:"):
                assert cell.outcome is Outcome.REJECTED, f"{state.name}/{event.name}"
                assert cell.target is BleState[expected[2:]], f"{state.name}/{event.name}"
            else:
                assert cell.outcome is Outcome.MOVE, f"{state.name}/{event.name}"
                assert cell.target is BleState[expected], f"{state.name}/{event.name}"


def test_every_state_has_a_row_and_every_row_every_event() -> None:
    assert set(MATRIX) == set(BleState)
    for state, row in MATRIX.items():
        assert set(row) == set(BleEvent), state.name


def test_a_rejected_event_leaves_the_state_and_is_reported(caplog) -> None:
    core = BleLinkCore()
    core.apply(BleEvent.REQUEST_LINK)
    core.apply(BleEvent.RIG_SEEN)
    core.apply(BleEvent.CONNECTED)
    core.apply(BleEvent.SUBSCRIBED)
    assert core.state is BleState.STREAMING

    with caplog.at_level("INFO", logger="app.rig.ble"):
        cell = core.apply(BleEvent.REQUEST_LINK)

    assert cell.outcome is Outcome.REJECTED
    assert core.state is BleState.STREAMING
    assert "refused" in caplog.text


# The attempt budget --------------------------------------------------------------------------------


def _walk_to(core: BleLinkCore, state: BleState) -> None:
    """Drive the machine to a state along the only path that reaches it."""
    path = {
        BleState.SCANNING: [BleEvent.REQUEST_LINK],
        BleState.CONNECTING: [BleEvent.REQUEST_LINK, BleEvent.RIG_SEEN],
        BleState.SUBSCRIBING: [BleEvent.REQUEST_LINK, BleEvent.RIG_SEEN, BleEvent.CONNECTED],
        BleState.STREAMING: [
            BleEvent.REQUEST_LINK,
            BleEvent.RIG_SEEN,
            BleEvent.CONNECTED,
            BleEvent.SUBSCRIBED,
        ],
        BleState.RECONNECTING: [BleEvent.REQUEST_LINK, BleEvent.SCAN_TIMEOUT],
    }[state]
    for event in path:
        core.apply(event)


@pytest.mark.parametrize(
    ("failure", "path"),
    [
        (BleEvent.SCAN_TIMEOUT, [BleEvent.REQUEST_LINK]),
        (BleEvent.ATTEMPT_FAILED, [BleEvent.REQUEST_LINK, BleEvent.RIG_SEEN]),
        (
            BleEvent.SUBSCRIBE_TIMEOUT,
            [BleEvent.REQUEST_LINK, BleEvent.RIG_SEEN, BleEvent.CONNECTED],
        ),
    ],
)
def test_the_fifth_failure_is_the_one_that_stops(failure: BleEvent, path: list[BleEvent]) -> None:
    """Every failure event spends the budget the same way, and the fifth reaches `Failed`."""
    core = BleLinkCore()
    for attempt in range(1, 5):
        for event in path:
            core.apply(event)
        core.apply(failure)
        assert core.state is BleState.RECONNECTING
        assert core.attempts == attempt
        core.apply(BleEvent.BACKOFF_EXPIRED)

    for event in path:
        core.apply(event)
    core.apply(failure)
    assert core.state is BleState.FAILED
    assert core.attempts == 5


def test_reaching_streaming_resets_the_budget_and_nothing_else_does() -> None:
    core = BleLinkCore()
    core.apply(BleEvent.REQUEST_LINK)
    core.apply(BleEvent.SCAN_TIMEOUT)
    core.apply(BleEvent.BACKOFF_EXPIRED)
    core.apply(BleEvent.SCAN_TIMEOUT)
    assert core.attempts == 2

    core.apply(BleEvent.BACKOFF_EXPIRED)
    core.apply(BleEvent.RIG_SEEN)
    core.apply(BleEvent.CONNECTED)
    core.apply(BleEvent.SUBSCRIBED)
    assert core.state is BleState.STREAMING
    assert core.attempts == 0


def test_a_disconnect_from_streaming_starts_a_new_budget() -> None:
    """A link that reached `Streaming` proved the rig reachable, so its drop is not held against it."""
    core = BleLinkCore()
    _walk_to(core, BleState.STREAMING)
    for _ in range(3):
        core.apply(BleEvent.LINK_LOST)
        assert core.state is BleState.RECONNECTING
        core.apply(BleEvent.BACKOFF_EXPIRED)
        core.apply(BleEvent.RIG_SEEN)
        core.apply(BleEvent.CONNECTED)
        core.apply(BleEvent.SUBSCRIBED)
    assert core.state is BleState.STREAMING
    assert core.attempts == 0


def test_failed_stays_put_until_a_request_arrives() -> None:
    core = BleLinkCore(attempts_before_failed=1)
    _walk_to(core, BleState.SCANNING)
    core.apply(BleEvent.SCAN_TIMEOUT)
    assert core.state is BleState.FAILED

    # Nothing in the matrix moves the layer out of `Failed` except a request: a backoff that expires late,
    # or a stale scan result, must not restart it behind the operator's back.
    assert core.apply(BleEvent.BACKOFF_EXPIRED).outcome is Outcome.IGNORED
    assert core.apply(BleEvent.RIG_SEEN).outcome is Outcome.IGNORED
    assert core.state is BleState.FAILED

    assert core.request_link().outcome is Outcome.MOVE
    assert core.state is BleState.SCANNING


def test_the_backoff_doubles_from_one_second() -> None:
    core = BleLinkCore()
    core.apply(BleEvent.REQUEST_LINK)
    waits = []
    for _ in range(4):
        core.apply(BleEvent.SCAN_TIMEOUT)
        waits.append(core.backoff())
        core.apply(BleEvent.BACKOFF_EXPIRED)
    assert waits == [1.0, 2.0, 4.0, 8.0]


# The client over a fake radio ----------------------------------------------------------------------


def test_no_attempt_happens_until_a_link_is_requested() -> None:
    """`open_transport` looks and does not request (§8): a caller that only asks whether there is a
    transport must not start an attempt, or `RigLink`'s retry loop would drive the radio."""
    radio = FakeRadio()
    client = build_client(radio)
    client.start()
    try:
        time.sleep(0.1)
        assert client.state is BleState.DISCONNECTED
        assert radio.scans == 0
        with pytest.raises(LinkNotStreaming):
            client.open_transport()

        client.request_link()
        assert wait_until(lambda: client.state is BleState.STREAMING)
    finally:
        client.stop()


def test_the_connect_path_reaches_streaming_and_gives_a_transport() -> None:
    radio = FakeRadio()
    client = build_client(radio)
    client.request_link()
    try:
        assert wait_until(lambda: client.state is BleState.STREAMING)
        assert [radio.scans, radio.connects, radio.subscribes] == [1, 1, 1]
        assert client.payload_size == 244
        transport = client.open_transport()
        assert transport.write(b"CMD PING\n") == 9
        assert radio.written == [b"CMD PING\n"]
    finally:
        client.stop()


def test_a_line_split_across_notifications_arrives_as_one_line() -> None:
    radio = FakeRadio()
    client = build_client(radio)
    client.request_link()
    try:
        assert wait_until(lambda: client.state is BleState.STREAMING)
        transport = client.open_transport()
        radio.deliver(b"EVT SCREE")
        radio.deliver(b"N RETAKE 40\r\n")
        assert transport.readline() == b"EVT SCREEN RETAKE 40\r\n"
    finally:
        client.stop()


def test_an_empty_read_times_out_and_a_dropped_link_raises() -> None:
    """The two answers `rig/link.py` depends on being different: nothing yet, and the link is gone."""
    radio = FakeRadio()
    client = build_client(radio, readline_timeout=0.05)
    client.request_link()
    try:
        assert wait_until(lambda: client.state is BleState.STREAMING)
        transport = client.open_transport()
        assert transport.readline() == b""

        radio.drop()
        assert wait_until(lambda: client.state is not BleState.STREAMING)
        with pytest.raises(OSError):
            transport.readline()
        with pytest.raises(LinkNotStreaming):
            client.open_transport()
    finally:
        client.stop()


def test_a_rig_that_never_appears_reaches_failed_and_stops_scanning() -> None:
    radio = FakeRadio()
    radio.seen = False
    client = build_client(radio)
    client.request_link()
    try:
        assert wait_until(lambda: client.state is BleState.FAILED)
        assert client.attempts == 5
        scans = radio.scans
        time.sleep(0.2)
        assert radio.scans == scans, "Failed is not an unbounded reconnect loop"
    finally:
        client.stop()


def test_a_request_after_failed_tries_again() -> None:
    radio = FakeRadio()
    radio.seen = False
    client = build_client(radio)
    client.request_link()
    try:
        assert wait_until(lambda: client.state is BleState.FAILED)
        radio.seen = True
        client.request_link()
        assert wait_until(lambda: client.state is BleState.STREAMING)
        assert client.attempts == 0
    finally:
        client.stop()


def test_a_write_failure_is_a_lost_link_and_the_client_goes_back_to_scanning() -> None:
    radio = FakeRadio()
    client = build_client(radio)
    client.request_link()
    try:
        assert wait_until(lambda: client.state is BleState.STREAMING)
        transport = client.open_transport()
        assert transport.write(b"CMD PING\n") == 9

        # A link that failed a write is gone, and the client says so rather than pretending: it drops the
        # transport, which is what raises in a reader that is waiting on it.
        async def broken_write(rx_uuid: str, data: bytes) -> None:
            raise OSError("the link is gone")

        client._radio.write = broken_write  # type: ignore[method-assign]
        with pytest.raises(OSError):
            transport.write(b"CMD PING\n")
        assert wait_until(lambda: client.state is not BleState.STREAMING)
        assert wait_until(lambda: client.state is BleState.STREAMING)
        assert radio.connects >= 2
    finally:
        client.stop()


def test_a_stop_says_goodbye_and_a_dropped_link_does_not() -> None:
    """The rig tells a client that is leaving from a radio that died, and so must this end.

    The firmware counts only the links that vanished **without** the subscription being disabled, which is
    how a bench session of deliberate connect/disconnect cycles stopped taking the rig off the air. The one
    thing this client has to get right is the order: unsubscribe, then disconnect - and never the reverse.
    """
    radio = FakeRadio()
    client = build_client(radio)
    client.request_link()
    try:
        assert wait_until(lambda: client.state is BleState.STREAMING)

        # A link that drops is not a goodbye: the radio went away, and there is nothing to unsubscribe from.
        radio.drop()
        assert wait_until(lambda: radio.disconnects >= 1)
        assert radio.goodbyes == 0, "a link that died must not be reported as a client that left"

        # A client that stops says so first, so the rig does not count it as a drop.
        assert wait_until(lambda: client.state is BleState.STREAMING)
        radio.events.clear()
        client.stop()
        assert radio.events[0] == "unsubscribe"
        assert "disconnect" in radio.events
    finally:
        client.stop()


def test_a_reconnect_is_not_torn_down_by_the_previous_links_teardown() -> None:
    """The failure the bench found in the outage check.

    The client disconnects on purpose when a link is lost, and bleak reports that teardown through the same
    callback as a real drop. Read as a fresh link-lost, it tore down the *next* link the moment it started
    streaming: the check reconnected and then failed its first write with "no connection to write on".
    """
    radio = FakeRadio()
    radio.report_own_disconnects = True
    client = build_client(radio)
    client.request_link()
    try:
        assert wait_until(lambda: client.state is BleState.STREAMING)

        radio.drop()
        assert wait_until(lambda: client.state is BleState.STREAMING)
        transport = client.open_transport()
        time.sleep(0.05)  # let any late teardown report land before the write is attempted
        assert transport.write(b"CMD PING\n") == 9
        assert radio.written == [b"CMD PING\n"]
    finally:
        client.stop()


def test_an_outage_recovers_without_a_person_and_the_client_keeps_trying() -> None:
    """The three-second outage of the measurement script, compressed: the radio is unreachable, the
    client keeps attempting on its own, and traffic resumes when the radio comes back - with no new
    request from anybody."""
    radio = FakeRadio()
    client = build_client(radio)
    client.request_link()
    try:
        assert wait_until(lambda: client.state is BleState.STREAMING)
        drop_at = time.monotonic()
        client.hold_down(0.2)
        assert wait_until(lambda: client.state is not BleState.STREAMING)
        assert wait_until(lambda: client.state is BleState.STREAMING, timeout=5.0)
        assert time.monotonic() - drop_at >= 0.2
        assert client.attempts == 0
    finally:
        client.stop()


# The composition with `rig/link.py` ----------------------------------------------------------------


def test_rig_link_stays_in_its_own_opening_until_the_radio_streams() -> None:
    """§8's composition, and the invariant it has to keep: `link.py` is not edited, so a transport has to
    exist exactly when the client is `Streaming` - and its retry loop must not be able to touch the
    radio."""
    radio = FakeRadio()
    radio.seen = False
    client = build_client(radio)
    seen: list[str] = []
    link = RigLink(client.open_transport, lambda event: seen.append(event.name), retry_seconds=0.02)
    link.start()
    try:
        assert wait_until(lambda: link.state is LinkState.OPENING)
        time.sleep(0.1)
        assert radio.scans == 0, "RigLink's retry asked; it did not start an attempt"
        assert link.counters.opened == 0

        radio.seen = True
        client.request_link()
        assert wait_until(lambda: link.state is LinkState.OPEN)
        assert link.counters.opened == 1

        radio.deliver(b"EVT TRIGGER 5000\r\n")
        assert wait_until(lambda: seen == ["TRIGGER"])
    finally:
        link.stop()
        client.stop()


def test_the_keepalive_of_the_protocol_layer_reaches_the_radio() -> None:
    """One line of protocol over the notification characteristic, written by the layer above without
    knowing which wire it is on: `CMD PING` is the rig's liveness rule, and it is not this layer's."""
    radio = FakeRadio()
    client = build_client(radio)
    seen: list[str] = []
    link = RigLink(
        client.open_transport,
        lambda event: seen.append(event.name),
        keepalive_seconds=0.05,
        retry_seconds=0.02,
    )
    client.request_link()
    link.start()
    try:
        assert wait_until(lambda: radio.written.count(b"CMD PING\n") >= 2)
        assert wait_until(lambda: link.state is LinkState.OPEN)
    finally:
        link.stop()
        client.stop()


# The setting that chooses the wire ------------------------------------------------------------------


def test_the_serial_wire_is_still_the_default(monkeypatch) -> None:
    """A machine at the rig with `AV_RIG_PORT` set and nothing else must keep getting the cable."""
    settings = Settings.model_validate({"AV_RIG_PORT": "COM5"})
    assert settings.rig_transport == "serial"

    import serial

    monkeypatch.setattr(serial, "Serial", lambda *args, **kwargs: FakeSerial())
    link = build_link(settings)
    assert link is not None
    assert not isinstance(link, BleRigLink)


def test_the_ble_wire_needs_no_port_and_starts_the_client(monkeypatch) -> None:
    """`AV_RIG_TRANSPORT=ble` is the whole configuration: the rig is found by its advertised name, so the
    empty-port rule that switches the serial link off must not apply to it."""
    from app.rig import ble as ble_module

    radio = FakeRadio()
    monkeypatch.setattr(ble_module, "BleakRadio", lambda: radio)
    settings = Settings.model_validate(
        {"AV_RIG_TRANSPORT": "ble", "AV_RIG_KEEPALIVE_SECONDS": 0.05}
    )

    link = build_link(settings)
    assert isinstance(link, BleRigLink)
    assert wait_until(lambda: radio.scans >= 1), "the client was asked for a link at start-up (C1)"
    link.start()
    try:
        assert wait_until(lambda: link.state is LinkState.OPEN)
    finally:
        link.stop()
    assert radio.disconnects >= 1, "stopping the link releases the radio"


def test_a_transport_nobody_implemented_is_refused_rather_than_ignored() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"AV_RIG_TRANSPORT": "wifi"})


# The measurement script's verdict -------------------------------------------------------------------


def measurement_script():
    """`scripts/test_rig_ble.py`, loaded under a name of its own.

    It is not a package module and it is not importable from `tests/`: a bare `import test_rig_ble` would
    resolve to this very file, because pytest imports both by basename.
    """
    path = Path(__file__).resolve().parent.parent / "scripts" / "test_rig_ble.py"
    spec = importlib.util.spec_from_file_location("av_rig_ble_measure", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs: a module executing `@dataclass` over string annotations looks itself up in
    # `sys.modules`, and with `from __future__ import annotations` every annotation in that file is a string.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_a_verdict_never_names_a_section_that_passed() -> None:
    """The defect the bench found: five good connects and a later failure, reported as a connect failure.

    The summary is derived from the four sections, so a section that passed cannot appear in it - and the
    one that failed is named with its own sentence.
    """
    script = measurement_script()

    problems = script.verdict([], (False, "no EVT PONG within 5 s"), (True, "fine"), (True, "fine"))
    assert problems == ["the forty-byte line: no EVT PONG within 5 s"]

    problems = script.verdict([2, 4], (True, "fine"), (True, "fine"), (True, "fine"))
    assert problems == ["connects: 2 of 5 never reached Streaming (attempts 2, 4)"]

    problems = script.verdict(
        [], (True, "fine"), (True, "fine"), (False, "cycle 7 of 20 never reached Streaming")
    )
    assert problems == ["the cycles: cycle 7 of 20 never reached Streaming"]

    assert script.verdict([], (True, "fine"), (True, "fine"), (True, "fine")) == []
