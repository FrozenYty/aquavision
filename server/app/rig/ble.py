"""The PC end of the rig link over BLE (docs/rig-transport-en.md, P3-38).

The rig has two state machines and this module is the second one on this side of the wire. `rig/link.py`
owns the conversation - the keepalive, the parser, `Alive`/`Gone` - and never learns which carrier it is
on; this module owns the connection and the notification subscription and nothing else. They meet at
exactly one point, which §8 states as the whole interface contract: **a transport exists while this client
is `Streaming`, and not otherwise**. `link.py` is not edited for this, because that is already its own
invariant one layer down - a transport exists if and only if its state is `OPEN`.

The seven states, the ten events and every cell between them are §7 of the document, transcribed below
and checked cell by cell in `tests/test_rig_ble.py`:

| State \\ Event | C1 request | C2 seen | C3 scan timeout | C4 connected | C5 failed | C6 subscribed | C7 sub timeout | C8 line in | C9 link lost | C10 backoff |
|---|---|---|---|---|---|---|---|---|---|---|
| `Disconnected` | `Scanning` | ignored | ignored | ignored | ignored | ignored | ignored | ignored | ignored | ignored |
| `Scanning` | handled | `Connecting` | `Reconnecting`/`Failed` | ignored | ignored | ignored | ignored | ignored | ignored | ignored |
| `Connecting` | handled | ignored | ignored | `Subscribing` | `Reconnecting`/`Failed` | ignored | ignored | ignored | ignored | ignored |
| `Subscribing` | handled | ignored | ignored | rejected | ignored | `Streaming` | `Reconnecting`/`Failed` | ignored | ignored | ignored |
| `Streaming` | rejected | ignored | ignored | rejected | ignored | handled | ignored | handled | `Reconnecting` | ignored |
| `Reconnecting` | handled | ignored | ignored | ignored | ignored | ignored | ignored | ignored | ignored | `Scanning` |
| `Failed` | `Scanning` | ignored | ignored | ignored | ignored | ignored | ignored | ignored | ignored | ignored |

**`Failed` is the reason that table has seven rows.** An unbounded reconnect loop makes a broken link look
like a working one: the log fills with attempts, a page says "reconnecting", and no state anywhere ever
admits that this is not going to work. Five attempts, and then a state that stays put until a person asks
again (C1).

Two things about the shape of this module belong in the open rather than in a comment nobody reads:

- **bleak is asynchronous and `Transport` is not.** The client runs one asyncio loop on a worker thread
  and hands `readline`, `write` and `close` to whoever asks for them. `write` and `close` marshal a
  coroutine onto that loop with `asyncio.run_coroutine_threadsafe(...).result()` and therefore **block the
  calling thread** for the duration of one GATT operation. That caller is `RigLink`'s keepalive thread or
  its reader thread - both already dedicated to this link - and the block is not hidden inside a callback:
  it is the line under this docstring, and the reason `write` has a timeout of its own.
- **`readline` blocks on a queue** fed by the notification callback. It returns `b""` when its wait times
  out, exactly as the serial adapter does, and it raises when the subscription ended - a `readline` that
  returned `b""` for "the link is gone" would park the reader thread forever.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Protocol

log = logging.getLogger(__name__)

#: The advertised name and the Nordic UART Service UUIDs. The same four strings are in the firmware's
#: `config.h`: §12 of the document says they have to be written down somewhere both ends read, and this is
#: the other end.
RIG_NAME = "AQUAVISION"
NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # the PC writes here
NUS_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # the rig notifies here

#: §9's timings. The scan and connect budgets are the platform's worst case rather than a measured mean -
#: a Windows BLE scan and a Windows BLE connection can each genuinely take this long, and the measurement
#: that would replace these numbers is `scripts/test_rig_ble.py`.
SCAN_TIMEOUT_SECONDS = 20.0
CONNECT_TIMEOUT_SECONDS = 20.0
#: Chosen, not measured: long enough for a subscription round trip on a loaded link, short enough that a
#: client which will not subscribe does not hold the attempt open. The rig's own eviction of a silent
#: client is ten seconds, deliberately longer, so the ordinary failure reads as a PC-side timeout.
SUBSCRIBE_TIMEOUT_SECONDS = 5.0
#: The wait before each new attempt, doubling from one second. **The fifth value is never waited out under
#: this budget**: the fifth failure is the one that reaches `Failed` (§7, "or `Failed` on the fifth"), so
#: the waits actually taken between five attempts are 1, 2, 4 and 8 seconds. The tuple keeps the design's
#: five values in one place, and it is also why §9's rehearsal bound `5 x 40 + 31 = 231 s` counts a wait
#: that does not happen - the worst case this code can produce is 215 seconds.
BACKOFF_SECONDS = (1.0, 2.0, 4.0, 8.0, 16.0)
ATTEMPTS_BEFORE_FAILED = 5
#: How long `readline` waits for a complete line before answering `b""`, matching the serial adapter's read
#: timeout. An empty read is "nothing yet" to the protocol layer, which loops. A subscription that ends is
#: not an empty read: it raises.
READLINE_TIMEOUT_SECONDS = 0.5
#: How long a GATT write may block its caller before this client calls the link lost. A write that has not
#: answered in this long is a link that is not carrying anything.
WRITE_TIMEOUT_SECONDS = 5.0


class BleState(Enum):
    """The seven states of §6. `FAILED` exists on purpose - see the module docstring."""

    DISCONNECTED = auto()  # no link and none being attempted
    SCANNING = auto()  # looking for the rig's advertisement
    CONNECTING = auto()  # a GATT connection is in progress
    SUBSCRIBING = auto()  # connected, waiting for the rig to acknowledge the subscription
    STREAMING = auto()  # notifications enabled and arriving
    RECONNECTING = auto()  # an attempt failed; waiting out the backoff
    FAILED = auto()  # the attempt budget is spent


class BleEvent(Enum):
    """The ten events of §6. `LINE_IN` is here for the same reason `F5` is on the firmware side: its cell
    says that a line is **not** this layer's event, and a rule that appears in no cell is a rule nobody can
    check. Nothing raises it - every cell of its column is `handled in place` or `ignored`."""

    REQUEST_LINK = auto()  # C1
    RIG_SEEN = auto()  # C2
    SCAN_TIMEOUT = auto()  # C3
    CONNECTED = auto()  # C4
    ATTEMPT_FAILED = auto()  # C5
    SUBSCRIBED = auto()  # C6
    SUBSCRIBE_TIMEOUT = auto()  # C7
    LINE_IN = auto()  # C8
    LINK_LOST = auto()  # C9
    BACKOFF_EXPIRED = auto()  # C10


class Outcome(Enum):
    """The four kinds of cell, the ones §4 defines and §7 shares: a target state; handled in place;
    ignored; or rejected, meaning the state does not change **and** the event is reported."""

    MOVE = auto()
    HANDLED = auto()
    IGNORED = auto()
    REJECTED = auto()


@dataclass(frozen=True)
class Cell:
    """One cell of the matrix. `target` is set for `MOVE` and for `REJECTED`, which names the state the
    layer stays in because the sender has to learn it was refused."""

    outcome: Outcome
    target: BleState | None = None


_IGNORED = Cell(Outcome.IGNORED)
_HANDLED = Cell(Outcome.HANDLED)


def _move(state: BleState) -> Cell:
    return Cell(Outcome.MOVE, state)


def _reject(state: BleState) -> Cell:
    return Cell(Outcome.REJECTED, state)


def _row(**cells: Cell) -> dict[BleEvent, Cell]:
    """One state's row of §7. Every event starts `ignored` - which is what the document says for most of
    the table - and the cells that are not are named. A missing event in the matrix is therefore impossible
    rather than merely untested."""
    row: dict[BleEvent, Cell] = {event: _IGNORED for event in BleEvent}
    for name, cell in cells.items():
        row[BleEvent[name.upper()]] = cell
    return row


#: §7, row by row.
MATRIX: dict[BleState, dict[BleEvent, Cell]] = {
    BleState.DISCONNECTED: _row(request_link=_move(BleState.SCANNING)),
    BleState.SCANNING: _row(
        request_link=_HANDLED,
        rig_seen=_move(BleState.CONNECTING),
        scan_timeout=_move(BleState.RECONNECTING),
    ),
    BleState.CONNECTING: _row(
        request_link=_HANDLED,
        connected=_move(BleState.SUBSCRIBING),
        attempt_failed=_move(BleState.RECONNECTING),
    ),
    BleState.SUBSCRIBING: _row(
        request_link=_HANDLED,
        connected=_reject(BleState.SUBSCRIBING),
        subscribed=_move(BleState.STREAMING),
        subscribe_timeout=_move(BleState.RECONNECTING),
    ),
    BleState.STREAMING: _row(
        request_link=_reject(BleState.STREAMING),
        connected=_reject(BleState.STREAMING),
        subscribed=_HANDLED,
        line_in=_HANDLED,
        link_lost=_move(BleState.RECONNECTING),
    ),
    BleState.RECONNECTING: _row(request_link=_HANDLED, backoff_expired=_move(BleState.SCANNING)),
    BleState.FAILED: _row(request_link=_move(BleState.SCANNING)),
}

#: The events that spend the attempt budget: a scan that saw nothing, a connection that failed, and a
#: subscription that was never acknowledged. **Reaching `Streaming` resets the counter, and nothing else
#: does** (§7) - a disconnect from `Streaming` starts a new budget, because that link proved the rig
#: reachable.
_FAILURE_EVENTS = frozenset(
    {BleEvent.SCAN_TIMEOUT, BleEvent.ATTEMPT_FAILED, BleEvent.SUBSCRIBE_TIMEOUT}
)


class LinkNotStreaming(RuntimeError):
    """`open_transport()` was called while the client was not `Streaming`.

    `RigLink` catches this like any other failure of its factory and stays in its own `OPENING`, retrying
    on its own schedule; that is the whole composition, and it is why this exception says which state the
    client was in rather than only that there is no transport.
    """


class BleLinkCore:
    """The §7 machine with no radio under it: a state, an attempt budget, and nothing that can block.

    Split from the client so the transitions can be driven - and checked against the document - on a
    machine with no BLE adapter and no rig, which is the only way the failure paths are testable at all.
    Every method here is called from one thread (the client's worker); the client is what makes that true.
    """

    def __init__(
        self,
        on_state: Callable[[BleState], None] | None = None,
        *,
        backoff: tuple[float, ...] = BACKOFF_SECONDS,
        attempts_before_failed: int = ATTEMPTS_BEFORE_FAILED,
    ) -> None:
        self._state = BleState.DISCONNECTED
        self._attempts = 0
        self._backoff = backoff
        self._attempts_before_failed = attempts_before_failed
        self._on_state = on_state

    @property
    def state(self) -> BleState:
        return self._state

    @property
    def attempts(self) -> int:
        """Failures spent since the last link that reached `Streaming`."""
        return self._attempts

    def request_link(self) -> Cell:
        """C1: a link is requested - by the service at start-up, or by an operator after `Failed`."""
        return self.apply(BleEvent.REQUEST_LINK)

    def backoff(self) -> float:
        """How long to wait before the next attempt. The budget of attempts is what bounds this."""
        index = min(max(self._attempts - 1, 0), len(self._backoff) - 1)
        return self._backoff[index]

    def apply(self, event: BleEvent) -> Cell:
        """One event, one cell. Returns the cell so a caller can see what happened without reading state."""
        cell = MATRIX[self._state][event]

        if cell.outcome is Outcome.MOVE:
            target = cell.target
            if target is BleState.RECONNECTING and event in _FAILURE_EVENTS:
                self._attempts += 1
                # The fifth failure is the one that stops (§7). `Failed` is reached and stays: a further
                # failure event cannot arrive, because nothing is attempting anything.
                if self._attempts >= self._attempts_before_failed:
                    target = BleState.FAILED
            if target is BleState.STREAMING:
                self._attempts = 0  # a link that carries lines is a rig that can be reached
            if event is BleEvent.LINK_LOST:
                self._attempts = 0  # a disconnect from `Streaming` starts a new budget
            self._set_state(target if target is not None else self._state, event)

        if cell.outcome is Outcome.REJECTED:
            # Reported, not silent: a caller that asked for a link while one is up has to learn that its
            # request was refused, or it will wait for something that is never going to happen.
            log.info("rig ble: %s refused in %s", event.name.lower(), self._state.name.lower())

        return cell

    def _set_state(self, state: BleState, event: BleEvent) -> None:
        if state is self._state:
            return
        self._state = state
        log.info("rig ble: %s -> %s", event.name.lower(), state.name.lower())
        if self._on_state is not None:
            self._on_state(state)


class Radio(Protocol):
    """The radio operations this client needs, so a test can stand in for bleak.

    Each is asynchronous because bleak is; nothing here may block the loop for longer than its own timeout,
    and every operation takes the timeout it is allowed. `on_disconnect` is how the radio reports the one
    event that has no caller to return it to: **the link dropped by itself** (§6, C9).
    """

    async def find(self, name: str, service_uuid: str, timeout: float) -> str | None: ...

    async def connect(self, address: str, timeout: float) -> None: ...

    async def subscribe(
        self, tx_uuid: str, on_bytes: Callable[[bytes], None], timeout: float
    ) -> None: ...

    async def write(self, rx_uuid: str, data: bytes) -> None: ...

    async def unsubscribe(self, tx_uuid: str) -> None: ...

    async def disconnect(self) -> None: ...

    def mtu(self) -> int: ...

    def on_disconnect(self, handler: Callable[[], None]) -> None: ...


class BleakRadio:
    """The real radio, through `bleak`, with the timeout each operation is given.

    One `BleakClient` at a time: this client connects to one rig, and a second link is the firmware's to
    refuse (its own rule 1), not something this end can talk it out of.
    """

    def __init__(self) -> None:
        self._client: object | None = None
        self._handler: Callable[[], None] | None = None
        #: True while this client is tearing a link down on purpose. bleak reports *every* disconnect
        #: through the same callback, ours included, and a teardown we asked for is not a lost link.
        self._expected_disconnect = False

    def on_disconnect(self, handler: Callable[[], None]) -> None:
        self._handler = handler

    async def find(self, name: str, service_uuid: str, timeout: float) -> str | None:
        from bleak import BleakScanner

        def matches(device: object, advertisement: object) -> bool:
            local_name = getattr(advertisement, "local_name", None)
            services = {str(uuid).lower() for uuid in getattr(advertisement, "service_uuids", [])}
            return local_name == name or service_uuid.lower() in services

        device = await BleakScanner.find_device_by_filter(matches, timeout=timeout)
        if device is None:
            return None
        return str(device.address)

    async def connect(self, address: str, timeout: float) -> None:
        from bleak import BleakClient

        client = BleakClient(
            address, disconnected_callback=self._bleak_disconnected, timeout=timeout
        )
        # The address is a fresh scan result on every attempt (§7: `Reconnecting` scans rather than
        # connects), so a cached address that is no longer connectable never reaches this call.
        await client.connect(timeout=timeout)
        self._client = client
        self._expected_disconnect = False

    async def subscribe(
        self, tx_uuid: str, on_bytes: Callable[[bytes], None], timeout: float
    ) -> None:
        client = self._client
        if client is None:
            raise RuntimeError("no connection to subscribe on")

        def handler(_characteristic: object, data: bytearray) -> None:
            on_bytes(bytes(data))

        await asyncio.wait_for(client.start_notify(tx_uuid, handler), timeout=timeout)

    async def write(self, rx_uuid: str, data: bytes) -> None:
        client = self._client
        if client is None:
            raise RuntimeError("no connection to write on")
        await client.write_gatt_char(rx_uuid, data, response=False)

    async def unsubscribe(self, tx_uuid: str) -> None:
        client = self._client
        if client is None:
            raise RuntimeError("no connection to unsubscribe on")
        await client.stop_notify(tx_uuid)

    async def disconnect(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        # The teardown is ours, so the callback it produces must not be read as a lost link - bleak cannot
        # tell the two apart on its own, and a callback read as C9 here used to tear down the *next* link
        # the moment it started streaming.
        self._expected_disconnect = True
        try:
            with contextlib.suppress(Exception):
                await client.disconnect()
        finally:
            self._expected_disconnect = False

    def mtu(self) -> int:
        client = self._client
        return int(getattr(client, "mtu_size", 0) or 0)

    def _bleak_disconnected(self, _client: object) -> None:
        """bleak's own disconnect callback: the radio dropped the link, and this layer is told."""
        if self._expected_disconnect:
            return  # we asked for this one
        if self._handler is not None:
            self._handler()


class BleTransport:
    """One streaming link, presented as the three calls `rig/link.py` already relies on.

    The bytes are a stream in both directions, exactly as they are over the cable: notifications are not
    message boundaries, so a line is reassembled here and a line that does not fit one notification is
    still one line to the reader above.
    """

    def __init__(
        self,
        client: BleClient,
        lines: queue.Queue[bytes | None],
        readline_timeout: float = READLINE_TIMEOUT_SECONDS,
    ) -> None:
        self._client = client
        #: The client's queue, not this object's: a notification that arrives between the subscription
        #: being acknowledged and this transport being handed out would otherwise be dropped, and the
        #: first line of a link is the one a reader is least able to do without.
        self._lines = lines
        self._readline_timeout = readline_timeout
        self._pending = bytearray()
        self._closed = False

    def readline(self, timeout: float | None = None) -> bytes:
        deadline = time.monotonic() + (self._readline_timeout if timeout is None else timeout)
        while b"\n" not in self._pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return b""
            try:
                chunk = self._lines.get(timeout=remaining)
            except queue.Empty:
                return b""
            if chunk is None:
                # Raised rather than answered with `b""`: an empty read means "nothing yet" to the protocol
                # layer, and answering the end of a subscription with it parked the reader thread forever.
                raise OSError("the BLE subscription ended")
            self._pending += chunk
        line, _, rest = self._pending.partition(b"\n")
        self._pending = bytearray(rest)
        return bytes(line) + b"\n"

    def write(self, data: bytes) -> int:
        if self._closed:
            raise OSError("the transport is closed")
        self._client.write_blocking(data)
        return len(data)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._client.transport_closed(self)


class BleClient:
    """The §6/§7 client: scan, connect, subscribe, stream, reconnect with backoff, and `Failed`.

    `open_transport` is the factory `RigLink` is constructed with, and calling it is a **look** rather than
    a request (§8): it answers when the state is `Streaming` and raises otherwise, so `RigLink`'s own retry
    loop cannot start an attempt, extend one, or restart the budget. A request comes from `request_link`,
    which the service calls once at start-up and an operator calls again after `Failed`.
    """

    def __init__(
        self,
        *,
        radio: Radio | None = None,
        name: str = RIG_NAME,
        service_uuid: str = NUS_SERVICE_UUID,
        rx_uuid: str = NUS_RX_UUID,
        tx_uuid: str = NUS_TX_UUID,
        on_state: Callable[[BleState], None] | None = None,
        scan_timeout: float = SCAN_TIMEOUT_SECONDS,
        connect_timeout: float = CONNECT_TIMEOUT_SECONDS,
        subscribe_timeout: float = SUBSCRIBE_TIMEOUT_SECONDS,
        backoff: Iterable[float] = BACKOFF_SECONDS,
        attempts_before_failed: int = ATTEMPTS_BEFORE_FAILED,
        readline_timeout: float = READLINE_TIMEOUT_SECONDS,
    ) -> None:
        self._name = name
        self._service_uuid = service_uuid
        self._rx_uuid = rx_uuid
        self._tx_uuid = tx_uuid
        self._scan_timeout = scan_timeout
        self._connect_timeout = connect_timeout
        self._subscribe_timeout = subscribe_timeout
        self._readline_timeout = readline_timeout
        self._radio: Radio = radio if radio is not None else BleakRadio()
        self._radio.on_disconnect(self._on_radio_disconnect)
        self._core = BleLinkCore(
            self._state_changed,
            backoff=tuple(backoff),
            attempts_before_failed=attempts_before_failed,
        )
        self._on_state = on_state
        self._lock = threading.Lock()
        self._requested = False
        self._stopping = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wake: asyncio.Event | None = None
        self._link_lost: asyncio.Event | None = None
        self._transport: BleTransport | None = None
        #: Bytes from the rig, in arrival order, waiting for a `readline`. One queue for the client's
        #: lifetime: the transport reads it, so a notification cannot slip between the subscription and
        #: the transport being handed out, and `None` in it means the subscription ended.
        self._lines: queue.Queue[bytes | None] = queue.Queue()
        self._address: str | None = None
        self._hold_until = 0.0

    @property
    def state(self) -> BleState:
        return self._core.state

    @property
    def attempts(self) -> int:
        return self._core.attempts

    @property
    def payload_size(self) -> int:
        """What one notification can carry: the negotiated ATT MTU less its three-byte header, or zero
        while nothing is negotiated. This is the number §12 says has to be read rather than assumed, and
        the measurement script reports it beside the forty-byte line."""
        mtu = self._radio.mtu()
        return mtu - 3 if mtu > 3 else 0

    def start(self) -> None:
        """Start the worker. Idempotent: the attempt budget belongs to the machine, not to this call."""
        with self._lock:
            if self._thread is not None:
                return
            self._stopping = False
            self._thread = threading.Thread(target=self._run, name="rig-ble", daemon=True)
            self._thread.start()

    def request_link(self) -> None:
        """C1. From the service at start-up, or from an operator after `Failed`."""
        self.start()
        with self._lock:
            self._requested = True
        self._notify_loop(self._wake)

    def open_transport(self) -> BleTransport:
        """The transport, if and only if the state is `Streaming` (§8). Raises in every other state."""
        with self._lock:
            transport = self._transport
        if self._core.state is not BleState.STREAMING or transport is None:
            raise LinkNotStreaming(
                f"the BLE client is {self._core.state.name.lower()}, so there is no transport yet"
            )
        return transport

    def hold_down(self, seconds: float) -> None:
        """Pretend the radio is unreachable for `seconds`: the current link is dropped, and a scan finds
        nothing until the hold ends.

        This is the measurement seam of `scripts/test_rig_ble.py`, not part of §7's machine: a three-second
        outage of a rig that is on a bench and powered is otherwise produced by unplugging it, which the
        script cannot do. The reconnect attempts themselves are the real ones - the client keeps scanning,
        backing off and trying, because from its side nothing about the outage is special.
        """
        self._hold_until = time.monotonic() + seconds
        self._on_radio_disconnect()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop attempting, drop the link and let the worker out.

        The timeout is the caller's because a worker that is inside a scan cannot be interrupted: a radio
        operation already in flight runs to its own timeout. A caller that is about to start another client
        - the measurement script is - passes one longer than a scan, so that two clients never hold the
        adapter at once.
        """
        with self._lock:
            self._stopping = True
            thread = self._thread
        self._notify_loop(self._wake)
        self._notify_loop(self._link_lost)
        if thread is not None:
            thread.join(timeout=timeout)
            if not thread.is_alive():
                with self._lock:
                    self._thread = None

    def write_blocking(self, data: bytes) -> None:
        """One GATT write, from the calling thread. **This blocks that thread** up to
        `WRITE_TIMEOUT_SECONDS`; see the module docstring for why that is not hidden in a callback."""
        loop = self._loop
        if loop is None or self._core.state is not BleState.STREAMING:
            raise OSError("the BLE link is not streaming")
        future = asyncio.run_coroutine_threadsafe(self._radio.write(self._rx_uuid, data), loop)
        try:
            future.result(timeout=WRITE_TIMEOUT_SECONDS)
        except Exception as err:  # noqa: BLE001 - every way a write fails means the same thing
            self._on_radio_disconnect()
            raise OSError(f"the BLE write failed: {err}") from err

    def transport_closed(self, transport: BleTransport) -> None:
        """`RigLink` closed the transport - which it does when a port stops working. That is a link that is
        gone (§6, C9), not a client that has stopped wanting one: it goes back to scanning."""
        with self._lock:
            if self._transport is not transport:
                return
        self._on_radio_disconnect()

    # Internal ---------------------------------------------------------------------------------------

    def _state_changed(self, state: BleState) -> None:
        if state is BleState.STREAMING:
            # Anything still queued belongs to the link that just ended - a line from the old link turning
            # up on the new one would be a message the rig never sent on it.
            while True:
                try:
                    self._lines.get_nowait()
                except queue.Empty:
                    break
            transport = BleTransport(self, self._lines, readline_timeout=self._readline_timeout)
            with self._lock:
                self._transport = transport
        else:
            with self._lock:
                transport, self._transport = self._transport, None
            if transport is not None:
                # A reader waiting inside `readline` learns immediately that the subscription is over; the
                # marker is drained above if it arrives while nothing is reading.
                self._lines.put(None)
        if self._on_state is not None:
            self._on_state(state)

    def _on_radio_disconnect(self) -> None:
        self._notify_loop(self._link_lost)

    def _notify_loop(self, event: asyncio.Event | None) -> None:
        """Wake the worker from another thread. The loop is created by the worker, so a call that arrives
        before it exists is a call the worker's own first check covers."""
        loop = self._loop
        if loop is None or event is None:
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(event.set)

    def _run(self) -> None:
        asyncio.run(self._drive())

    async def _drive(self) -> None:
        """§7 driven by real I/O: one pass per state. Every event applied here comes from something that
        happened - a scan result, a connection, a timeout - and never from a guess about what should."""
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self._link_lost = asyncio.Event()
        try:
            while not self._stopping:
                state = self._core.state
                if state in (BleState.DISCONNECTED, BleState.FAILED):
                    await self._await_request()
                elif state is BleState.SCANNING:
                    await self._scan()
                elif state is BleState.CONNECTING:
                    await self._connect()
                elif state is BleState.SUBSCRIBING:
                    await self._subscribe()
                elif state is BleState.STREAMING:
                    await self._stream()
                elif state is BleState.RECONNECTING:
                    await self._backoff()
        finally:
            # A polite goodbye: disable notifications before disconnecting, so the firmware sees a client
            # that is leaving (its F4) rather than a radio that died. Firmware 1.24 deleted the drop-storm
            # rule this order used to serve, so nothing depends on the distinction now; the teardown is
            # still the honest one. A link that is already gone answers nothing here, which is correct -
            # the disconnect that mattered was the radio's, and the rig has seen it.
            with contextlib.suppress(Exception):
                await self._radio.unsubscribe(self._tx_uuid)
            await self._radio.disconnect()
            self._loop = None

    async def _await_request(self) -> None:
        with self._lock:
            requested, self._requested = self._requested, False
        if requested:
            self._core.request_link()
            return
        assert self._wake is not None
        await self._wake.wait()
        self._wake.clear()
        with self._lock:
            requested, self._requested = self._requested, False
        if requested and not self._stopping:
            self._core.request_link()

    async def _scan(self) -> None:
        if time.monotonic() < self._hold_until:
            # Inside a hold the radio is unreachable, so this is a scan that sees nothing - the same event,
            # and the same cost to the budget, as a rig that is switched off.
            await asyncio.sleep(min(1.0, self._hold_until - time.monotonic()))
            self._core.apply(BleEvent.SCAN_TIMEOUT)
            return
        try:
            address = await self._radio.find(self._name, self._service_uuid, self._scan_timeout)
        except Exception:  # noqa: BLE001 - an adapter that is not there scans as nothing
            log.info("rig ble: the scan failed", exc_info=True)
            address = None
        if self._stopping:
            return
        if address is None:
            self._core.apply(BleEvent.SCAN_TIMEOUT)
        else:
            self._address = address
            self._core.apply(BleEvent.RIG_SEEN)

    async def _connect(self) -> None:
        address = self._address
        if (
            address is None
        ):  # cannot happen: `Connecting` is only entered from a scan that saw the rig
            self._core.apply(BleEvent.ATTEMPT_FAILED)
            return
        try:
            await self._radio.connect(address, self._connect_timeout)
            ok = True
        except Exception:  # noqa: BLE001 - a connection that failed is C5 whatever it failed with
            log.info("rig ble: the connection attempt failed", exc_info=True)
            ok = False
        if self._stopping:
            return
        if ok and self._link_lost is not None:
            # Anything still set here belongs to the link that just ended. A disconnect callback from that
            # teardown can arrive after a new link is up, and a stale signal would tear the new one down the
            # moment it started streaming - which is what the bench saw on 2026-11-15: the outage check
            # reconnected and then failed its first write with "no connection to write on".
            self._link_lost.clear()
        self._core.apply(BleEvent.CONNECTED if ok else BleEvent.ATTEMPT_FAILED)

    async def _subscribe(self) -> None:
        try:
            await self._radio.subscribe(self._tx_uuid, self._on_bytes, self._subscribe_timeout)
            ok = True
        except Exception:  # noqa: BLE001 - no acknowledgement inside the timeout is C7
            log.info("rig ble: the subscription was not acknowledged", exc_info=True)
            ok = False
        if self._stopping:
            return
        self._core.apply(BleEvent.SUBSCRIBED if ok else BleEvent.SUBSCRIBE_TIMEOUT)

    async def _stream(self) -> None:
        assert self._link_lost is not None
        await self._link_lost.wait()
        self._link_lost.clear()
        if self._stopping:
            return
        # The link is gone: drop it here rather than leaving a half-open connection behind, so the next
        # attempt scans for a rig that is advertising again (§7: `Reconnecting` scans rather than connects).
        await self._radio.disconnect()
        self._core.apply(BleEvent.LINK_LOST)

    async def _backoff(self) -> None:
        await asyncio.sleep(self._core.backoff())
        if self._stopping:
            return
        self._core.apply(BleEvent.BACKOFF_EXPIRED)

    def _on_bytes(self, data: bytes) -> None:
        """A notification, on the loop thread. It is queued for the transport and nothing else: this layer
        does not parse, and does not keep time."""
        self._lines.put(data)
        self._core.apply(BleEvent.LINE_IN)
