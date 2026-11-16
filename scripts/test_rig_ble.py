#!/usr/bin/env python3
"""Rig over BLE bench check: connect time, a forty-byte line, an outage, and twenty cycles.

**The connect time is the one number the design could not reason out.** Every other timing in
`docs/rig-transport-en.md` §9 is a firmware constant, arithmetic or a decision; the twenty-second scan and
connect budgets come from a platform observation and not from a stopwatch, and the document says so in the
table. This tool is the measurement that replaces it - five connects from a cold start, each printed rather
than averaged, so a worst case can be seen instead of an average that hides it.

    python scripts/test_rig_ble.py
    python scripts/test_rig_ble.py --seconds 10

There is no `--port`: the rig is found by its advertised name or its service UUID, and typing a port is the
one thing this transport exists to stop doing.

Four questions, in the order they are asked:

1. **How long does a connect take, five times?** A fresh client and a fresh scan each time - a cached
   address or a warm connection would answer a different question. Each attempt prints its total and the
   three phases it is made of, and the worst is compared with the twenty-second budget the design assumed.
2. **Does a forty-byte line arrive intact and in one piece?** The line sent is a padded `CMD PING` - the
   firmware reads the verb and the command and ignores the rest - and `EVT PONG` back proves the forty
   bytes arrived and were parsed. Whether it fitted **one notification** depends on the negotiated ATT MTU,
   which is printed as the payload it gives; §12 of the document lists that as unmeasured.
3. **Does it recover from a three-second outage, and does that need a person?** The radio is held
   unreachable for three seconds and then released: the client keeps attempting on its own, and the time
   until `EVT PONG` comes back is the answer. A person is needed only if the five-attempt budget was spent
   first, which is the `Failed` state and is reported as exactly that.
4. **Does the rig survive twenty consecutive connect/disconnect cycles?** This is the number that decides
   whether there is a demonstration at all: a slow connect is a wait, and a rig that cannot be found is the
   end of it. The bench report of 2026-11-15 is why the section exists - five deliberate cycles took the
   rig off the air, because the firmware counted each clean departure as a dropped link and reached its
   `Fault` state on the fifth.

**The verdict is derived from the four sections and from nothing else.** A summary with a counter of its
own can disagree with the lines above it, and one that says "0 of 5 connects did not reach Streaming"
underneath "5 of 5 reached Streaming" is worse than no summary at all.

Exit codes: 0 all four answered, 1 one of them was not, or the rig was never seen.

The rig must be flashed `rig-ble` and powered, and this machine needs a BLE adapter: without one the five
attempts fail as scans that see nothing, which is the honest answer for a machine that cannot measure this.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
import time
from dataclasses import dataclass
from functools import partial
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "server"))

from app.rig.ble import (  # noqa: E402
    SCAN_TIMEOUT_SECONDS,
    BleClient,
    BleState,
    BleTransport,
    LinkNotStreaming,
)

#: How many connects the design asks for: one per backoff value, and the budget `Failed` marks.
ATTEMPTS = 5
#: The cycles of the fourth section - the acceptance the bench report set, and four times the firmware's
#: five-drop storm limit, so passing it proves the rig is not faulting on clean departures.
CYCLES = 20
#: How long to keep waiting for `EVT PONG` once the rig has been asked, and how long to wait for traffic
#: to come back after the outage. Default only; `--seconds` moves it.
DEFAULT_SECONDS = 5.0
#: The outage the design asks about. Three seconds is long enough to cross the rig's own two-second
#: keepalive boundary and short enough to stay inside one reconnect attempt.
OUTAGE_SECONDS = 3.0
#: A connect attempt can cost a scan, a connection and a subscription; the design's own bound is 45 s, and
#: a few seconds of margin keep a slow success from being reported as a failure.
STREAMING_DEADLINE_SECONDS = 50.0
#: `CMD PING`, one filler token and a newline - exactly forty bytes on the wire. The firmware's parser
#: takes the verb and the command and ignores the remaining token, so this is a legal command padded to the
#: size the design calls its longest line, not a new message.
PAYLOAD = b"CMD PING " + b"-" * 30 + b"\n"
PONG = "EVT PONG"


class Timeline:
    """When each state was entered, so a phase can be named instead of guessed.

    The client reports its own state changes; timing them here rather than inside the client keeps the
    measurement out of the thing being measured.
    """

    def __init__(self) -> None:
        self.marks: list[tuple[float, BleState]] = []

    def record(self, state: BleState) -> None:
        self.marks.append((time.monotonic(), state))

    def at(self, state: BleState) -> float | None:
        for at, seen in self.marks:
            if seen is state:
                return at
        return None


@dataclass
class Attempt:
    """One cold start: the phases when it reached `Streaming`, and nothing when it did not."""

    number: int
    total: float | None
    scan: float = 0.0
    connect: float = 0.0
    subscribe: float = 0.0
    mtu: int = 0


def phases(timeline: Timeline, start: float) -> tuple[float, float, float, float] | None:
    """The four phases of one attempt: scan, connect, subscribe, and the total.

    `None` when the attempt never reached `Streaming` - an attempt that failed has no subscribe phase, and
    inventing a zero for it would read as an instant one.
    """
    connecting = timeline.at(BleState.CONNECTING)
    subscribing = timeline.at(BleState.SUBSCRIBING)
    streaming = timeline.at(BleState.STREAMING)
    if connecting is None or subscribing is None or streaming is None:
        return None
    return (
        connecting - start,
        subscribing - connecting,
        streaming - subscribing,
        streaming - start,
    )


def wait_for(predicate, timeout: float) -> bool:
    """Poll until the predicate holds. The client works on its own threads, so this waits for effects."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def shut_down(client: BleClient) -> None:
    """Stop a client and wait for its worker to finish.

    The wait is longer than the design's scan timeout on purpose: a scan already in flight cannot be
    interrupted, and the next measurement needs the adapter to itself. Stopping is also how a cycle says
    goodbye - the client disables the subscription before it disconnects, and the rig counts only the links
    that vanished without that goodbye.
    """
    client.stop(timeout=SCAN_TIMEOUT_SECONDS + 5.0)


def read_until(transport: BleTransport, line: str, timeout: float) -> float | None:
    """Read lines until `line` arrives, and return when it did, or None when the window closed."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = transport.readline(timeout=0.2)
        if not raw:
            continue
        if raw.decode("ascii", errors="replace").strip() == line:
            return time.monotonic()
    return None


def settled(client: BleClient) -> bool:
    """True when an attempt has finished either way: `Streaming`, or `Failed` with its budget spent."""
    return client.state in (BleState.STREAMING, BleState.FAILED)


def keep_alive(client: BleClient) -> None:
    """One `CMD PING` on an open link, unanswered.

    A rig that hears nothing for ten seconds declares the PC gone and shows `OFFLINE` - that is the
    protocol's rule and this tool must not make the panel look broken while it measures (§2). It is sent
    after a measurement has been taken, so it cannot colour the numbers.
    """
    with contextlib.suppress(OSError, LinkNotStreaming):
        client.open_transport().write(b"CMD PING\n")


def measure_connect(attempt: int) -> Attempt:
    """One cold start. A fresh client per attempt is the whole point: a second connect on a warm stack
    answers a different question from the one the design asks, which is how long a demonstration waits
    after boot."""
    timeline = Timeline()
    client = BleClient(on_state=timeline.record)
    started = time.monotonic()
    client.request_link()
    try:
        # Either answer ends the wait: `Streaming` is the measurement, and `Failed` is the client saying it
        # has spent its whole budget, which is worth reporting now rather than after the window closes.
        wait_for(
            lambda: client.state in (BleState.STREAMING, BleState.FAILED),
            STREAMING_DEADLINE_SECONDS,
        )
        found = phases(timeline, started) if client.state is BleState.STREAMING else None
        if found is None:
            spent = client.attempts
            print(
                f"  attempt {attempt}: no Streaming after {time.monotonic() - started:.2f} s "
                f"({client.state.name.lower()}, {spent} of {ATTEMPTS} attempts spent)"
            )
            return Attempt(attempt, None)
        scan, connect, subscribe, total = found
        mtu = client.payload_size + 3 if client.payload_size else 0
        print(
            f"  attempt {attempt}: {total:.2f} s to Streaming "
            f"(scan {scan:.2f}, connect {connect:.2f}, subscribe {subscribe:.2f}), "
            f"MTU {mtu}, payload {client.payload_size}"
        )
        keep_alive(client)
        return Attempt(attempt, total, scan, connect, subscribe, mtu)
    finally:
        shut_down(client)


def measure_payload(seconds: float) -> tuple[bool, str]:
    """The forty-byte line, on a link that is already streaming.

    Two facts are reported separately: whether the line arrived and was parsed (an `EVT PONG` back), and
    whether it fitted **one notification** - which is the negotiated payload's size, not the code's
    intention. The firmware splits a line that does not fit, so both answers can be true at once.
    """
    timeline = Timeline()
    client = BleClient(on_state=timeline.record)
    client.request_link()
    try:
        if not wait_for(lambda: client.state is BleState.STREAMING, STREAMING_DEADLINE_SECONDS):
            return False, "the rig was not reachable for this check"
        transport = client.open_transport()
        payload = client.payload_size
        sent_at = time.monotonic()
        try:
            transport.write(PAYLOAD)
            answered = read_until(transport, PONG, seconds)
        except OSError as err:
            return False, f"the write failed: {err}"
        if answered is None:
            return False, f"no {PONG} within {seconds:g} s of a forty-byte CMD PING"
        took = answered - sent_at
        if not payload:
            fit = "the stack reported no ATT MTU, so the notification size is unknown"
        elif len(PAYLOAD) <= payload:
            fit = f"in one notification (payload {payload} bytes)"
        else:
            pieces = -(-len(PAYLOAD) // payload)
            fit = f"in {pieces} notifications (payload {payload} bytes), reassembled"
        return True, f"{len(PAYLOAD)} bytes answered by {PONG} in {took:.2f} s, {fit}"
    finally:
        shut_down(client)


def measure_outage(seconds: float) -> tuple[bool, str]:
    """A three-second outage, held on the radio and released without asking again.

    The outage is produced by `hold_down`, which is this repository's seam for it: a powered rig on a bench
    cannot be unplugged from a script. The client's behaviour during it is not simulated - it keeps
    scanning, backing off and reconnecting, and the budget it spends is the real one.
    """
    timeline = Timeline()
    client = BleClient(on_state=timeline.record)
    client.request_link()
    try:
        if not wait_for(lambda: client.state is BleState.STREAMING, STREAMING_DEADLINE_SECONDS):
            return False, "the rig was not reachable for this check"
        drop_at = time.monotonic()
        client.hold_down(OUTAGE_SECONDS)
        ended_at = drop_at + OUTAGE_SECONDS
        wait_for(lambda: client.state is not BleState.STREAMING, OUTAGE_SECONDS + 5.0)
        print(f"  the link was held unreachable for {OUTAGE_SECONDS:g} s")

        back = wait_for(lambda: client.state is BleState.STREAMING, STREAMING_DEADLINE_SECONDS)
        if not back:
            state = client.state.name.lower()
            if client.state is BleState.FAILED:
                return False, (
                    f"the reconnect budget was spent: the client is {state} after five attempts, so only a "
                    "person asking again would bring the link back"
                )
            return False, (
                f"the link did not come back within {STREAMING_DEADLINE_SECONDS:g} s ({state})"
            )
        streaming_at = time.monotonic()
        transport = client.open_transport()
        try:
            transport.write(b"CMD PING\n")
            answered = read_until(transport, PONG, seconds)
        except OSError as err:
            return False, f"the link came back but the write failed: {err}"
        if answered is None:
            return False, f"the link came back but no {PONG} within {seconds:g} s"
        return True, (
            f"Streaming again {streaming_at - ended_at:.2f} s after the outage ended, "
            f"{PONG} {answered - ended_at:.2f} s after it, with no operator action "
            f"({client.attempts} of {ATTEMPTS} attempts spent)"
        )
    finally:
        shut_down(client)


def measure_cycles(seconds: float) -> tuple[bool, str]:
    """`CYCLES` consecutive connect/disconnect cycles, each from a cold start and each answered.

    Every cycle asks the rig to answer, so what is proven is a conversation and not a GATT connection: a
    rig that accepts a link and never speaks again would pass a bare connect test and fail this one. The
    section stops at the first cycle that fails, because the property under test is "twenty of twenty" and
    a second timeout would only say the same thing twice.
    """
    worst = 0.0
    for cycle in range(1, CYCLES + 1):
        timeline = Timeline()
        client = BleClient(on_state=timeline.record)
        started = time.monotonic()
        client.request_link()
        try:
            reached = wait_for(partial(settled, client), STREAMING_DEADLINE_SECONDS)
            found = (
                phases(timeline, started)
                if (reached and client.state is BleState.STREAMING)
                else None
            )
            if found is None:
                took = time.monotonic() - started
                print(
                    f"  cycle {cycle}: no Streaming after {took:.2f} s "
                    f"({client.state.name.lower()}, {client.attempts} of {ATTEMPTS} attempts spent)"
                )
                return False, (
                    f"cycle {cycle} of {CYCLES} never reached Streaming - the rig was reachable on "
                    f"{cycle - 1} consecutive cycle(s) before it"
                )
            total = found[3]
            worst = max(worst, total)
            try:
                transport = client.open_transport()
                transport.write(b"CMD PING\n")
                answered = read_until(transport, PONG, seconds)
            except OSError as err:
                print(f"  cycle {cycle}: Streaming in {total:.2f} s but the write failed: {err}")
                return (
                    False,
                    f"cycle {cycle} of {CYCLES} reached Streaming but could not be written to",
                )
            if answered is None:
                print(f"  cycle {cycle}: Streaming in {total:.2f} s but no {PONG} in {seconds:g} s")
                return False, f"cycle {cycle} of {CYCLES} reached Streaming but never answered"
            print(f"  cycle {cycle}: {total:.2f} s to Streaming, answered {PONG}")
        finally:
            shut_down(client)
    return (
        True,
        f"{CYCLES} of {CYCLES} cycles reached the rig and were answered (worst {worst:.2f} s)",
    )


def verdict(
    unreachable: list[int],
    payload: tuple[bool, str],
    outage: tuple[bool, str],
    cycles: tuple[bool, str],
) -> list[str]:
    """The failures the four sections add up to, in the order they were measured.

    **Derived from the sections and from nothing else.** An earlier version kept a counter of its own
    beside the loop that filled it, and printed `Fail: 0 of 5 connects did not reach Streaming` directly
    under `5 of 5 reached Streaming` - a summary that can disagree with the lines above it is worse than
    no summary. `tests/test_rig_ble.py` pins exactly that case.
    """
    problems: list[str] = []
    if unreachable:
        numbers = ", ".join(str(number) for number in unreachable)
        problems.append(
            f"connects: {len(unreachable)} of {ATTEMPTS} never reached Streaming (attempts {numbers})"
        )
    for name, (ok, note) in (
        ("the forty-byte line", payload),
        ("the outage", outage),
        ("the cycles", cycles),
    ):
        if not ok:
            problems.append(f"{name}: {note}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seconds",
        type=float,
        default=DEFAULT_SECONDS,
        help=f"how long to wait for EVT PONG once the rig is asked (default {DEFAULT_SECONDS:g})",
    )
    args = parser.parse_args(argv)

    # Imported here so `--help` still works on a machine that has not installed bleak. Said out loud
    # rather than left to the scan path, where a missing module would look like a rig that is switched off.
    try:
        import bleak  # noqa: F401
    except ImportError:
        print("bleak is not installed: pip install -r requirements-server.txt", file=sys.stderr)
        return 1

    print(
        f"{PAYLOAD!r} is {len(PAYLOAD)} bytes; the rig is found by name, so there is no port to give."
    )
    print()

    print(f"Connect, {ATTEMPTS} cold starts (new client, new scan each time):")
    attempts = [measure_connect(number) for number in range(1, ATTEMPTS + 1)]
    reached = [attempt for attempt in attempts if attempt.total is not None]
    unreachable = [attempt for attempt in attempts if attempt.total is None]
    if not reached:
        print()
        print(
            "Fail: the rig was never reached in five attempts. Check that it is flashed rig-ble and "
            "powered, that its panel does not read Err4 (a radio that did not start), and that this "
            "machine has a BLE adapter.",
            file=sys.stderr,
        )
        return 1
    worst = max(attempt.total for attempt in reached if attempt.total is not None)
    best = min(attempt.total for attempt in reached if attempt.total is not None)
    print(
        f"  {len(reached)} of {ATTEMPTS} reached Streaming; worst {worst:.2f} s, best {best:.2f} s"
    )
    print()

    print("A forty-byte line:")
    payload_ok, payload_note = measure_payload(args.seconds)
    print(f"  {'pass' if payload_ok else 'FAIL'}: {payload_note}")
    print()

    print(f"A {OUTAGE_SECONDS:g}-second outage:")
    outage_ok, outage_note = measure_outage(args.seconds)
    print(f"  {'pass' if outage_ok else 'FAIL'}: {outage_note}")
    print()

    print(f"{CYCLES} connect/disconnect cycles:")
    cycles_ok, cycles_note = measure_cycles(args.seconds)
    print(f"  {'pass' if cycles_ok else 'FAIL'}: {cycles_note}")
    print()

    # The verdict is built from the four sections above and from nothing else - see `verdict`, which is
    # tested on its own because a summary that can disagree with the lines it summarises is worse than no
    # summary, and that is what this block used to do.
    problems = verdict(
        [attempt.number for attempt in unreachable],
        (payload_ok, payload_note),
        (outage_ok, outage_note),
        (cycles_ok, cycles_note),
    )
    if problems:
        print("Fail:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    budget = 20.0
    print(
        f"Pass: {ATTEMPTS} of {ATTEMPTS} connects, a forty-byte line, recovery with no person, and "
        f"{CYCLES} of {CYCLES} cycles."
    )
    print(f"  connect: worst {worst:.2f} s against the design's {budget:g} s budget")
    if worst < budget / 4:
        print(
            f"  the budget is {budget / worst:.1f}x the worst case; §9 says a worst case under 5 s "
            "means the 20 s should be cut"
        )
    print(f"  40 bytes: {payload_note}")
    print(f"  outage: {outage_note}")
    print(f"  cycles: {cycles_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
