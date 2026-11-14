#!/usr/bin/env python3
"""Rig link bench check: are the cable and the board alive before anything else is debugged?

The board answers `CMD PING` with `EVT PONG`, and that single exchange proves the cable, the power and
the baud rate. The rig requires a keepalive at least every two seconds, so the tool sends one on that
schedule and prints every line the board sends - a board that talks is a different fault from one that
is silent, and finding out which is the first question every other check depends on.

    python scripts/test_rig_link.py
    python scripts/test_rig_link.py --port COM5 --seconds 10
    python scripts/test_rig_link.py --port COM5 --scan --seconds 6
    python scripts/test_rig_link.py --port COM5 --answer --seconds 60

Exit codes: 0 the question was answered, 1 it was not, or the port could not be opened.

With `--scan` the tool instead asks the board to walk its I2C bus (`CMD SCAN`) and reports every address
that answered, against the one this rig is built to have, the OLED. That is the check `P3-17` names, and it
is the only way to see the bus without a serial terminal. The firmware has no completion marker for a scan,
so the tool waits a fixed window and says how long it waited rather than pretending the list is complete.

With `--answer` the tool stands in for the server and answers a button press, which is the only way to test
the two verdict lamps on their own: the firmware pulses a lamp when `CMD RESULT` arrives, and it **refuses**
a result in any state but `Capturing`, so a bare button press lights nothing and looks like a broken LED.
Press the button while this runs; it answers each trigger in turn so both lamps can be seen.

**Pick the right port.** On the machine this was written on, `COM3` and `COM4` were Bluetooth serial ports
with nothing on the other end, and **opening one blocks** rather than failing fast; the rig was
`USB-Enhanced-SERIAL CH343`. Choose the CH343 port by name.

Opening the port resets the board: the bridge chip's DTR and RTS lines feed the auto-reset circuit, so
the sketch restarts and reports a fresh `EVT SCREEN READY` before this tool's first ping arrives. That is
normal - do not read it as the rig having been online already.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

# The two protocol tokens this tool needs, from the table in `firmware/README.md`. Copied rather than
# imported: `app.rig.protocol` pulls in `app.vision.quality`, which pulls in OpenCV and numpy - not
# dependencies a laptop sitting on a bench with one cable should need to check the cable.
PING = b"CMD PING\n"
SCAN = b"CMD SCAN\n"
PONG = "EVT PONG"
SCAN_PREFIX = "EVT I2C "
TRIGGER = "EVT TRIGGER"
#: What `--answer` sends, in turn, so that both lamps can be seen in one run. The scores and the reason
#: token are the ones `app.rig.protocol` writes; they are copied here for the reason above.
VERDICTS = (b"CMD RESULT 95 PASS NONE\n", b"CMD RESULT 40 RETAKE LOW_LIGHT\n")
#: The one device this rig is built to have on the bus, from `firmware/main/src/config.h`.
EXPECTED = {"3C": "OLED"}
BAUD = 115200
KEEPALIVE_SECONDS = 2.0
DEFAULT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 0.2


def scan_addresses(lines: list[str]) -> dict[str, str]:
    """The addresses a scan reported, in the order they arrived.

    The firmware prints `EVT I2C %02X`, so the value keeps the upper-case hex spelling it arrived in -
    `3C` and not `0x3c` - because that is what the person reading the terminal will match against the
    module's silkscreen.
    """
    found: dict[str, str] = {}
    for line in lines:
        if line.startswith(SCAN_PREFIX):
            address = line[len(SCAN_PREFIX) :].strip().upper()
            if address:
                found[address] = EXPECTED.get(address, "something the rig does not expect")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        default=os.environ.get("AV_RIG_PORT", ""),
        help="serial port; defaults to $AV_RIG_PORT",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=DEFAULT_SECONDS,
        help=f"how long to wait for EVT PONG, or to collect a scan (default {DEFAULT_SECONDS:g})",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="ask the board to walk its I2C bus and report the addresses that answered",
    )
    parser.add_argument(
        "--answer",
        action="store_true",
        help="stand in for the server and answer each button press with a verdict",
    )
    args = parser.parse_args(argv)

    if not args.port:
        print("No port given: pass --port or set AV_RIG_PORT.", file=sys.stderr)
        return 1

    # Imported here so `--help` still works on a machine that has not installed pyserial yet.
    try:
        import serial
    except ImportError:
        print("pyserial is not installed: pip install -r requirements-server.txt", file=sys.stderr)
        return 1

    # Said before the port is touched: a tool that then waits two seconds should look like a board
    # that is not answering, not like a tool that hung.
    print(f"Opening {args.port} at {BAUD} baud")
    try:
        port = serial.Serial(args.port, BAUD, timeout=READ_TIMEOUT_SECONDS)
    except serial.SerialException as err:
        print(f"Cannot open {args.port}: {err}", file=sys.stderr)
        return 1

    if args.scan and args.answer:
        print("--scan and --answer are different jobs: pass one of them.", file=sys.stderr)
        port.close()
        return 2
    if args.answer:
        print(
            f"Answering each button press with a verdict for {args.seconds:g} s "
            f"(keepalive every {KEEPALIVE_SECONDS:g} s). Press the button now."
        )
    elif args.scan:
        print(
            f"Sending CMD SCAN, collecting EVT I2C lines for {args.seconds:g} s "
            f"(keepalive every {KEEPALIVE_SECONDS:g} s)"
        )
    else:
        print(
            f"Sending CMD PING every {KEEPALIVE_SECONDS:g} s, "
            f"waiting up to {args.seconds:g} s for EVT PONG"
        )
    pong = False
    seen: list[str] = []
    deadline = time.monotonic() + args.seconds
    # The first ping goes out at once: the rig wants a command every two seconds, not two seconds of
    # silence before the first one. The scan rides along, because a scan is also a `CMD` line and it
    # keeps the link alive just as well - but the keepalive still has to continue while it collects.
    next_ping = 0.0
    scan_sent = False
    answered = 0
    try:
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_ping:
                port.write(PING)
                next_ping = now + KEEPALIVE_SECONDS
                if args.scan and not scan_sent:
                    port.write(SCAN)
                    scan_sent = True
            raw = port.readline()
            if not raw:
                continue
            line = raw.decode("ascii", errors="replace").strip()
            if not line:
                continue
            print(f"  {line}")
            seen.append(line)
            if args.answer and line.startswith(TRIGGER):
                verdict = VERDICTS[answered % len(VERDICTS)]
                answered += 1
                port.write(verdict)
                print(f"    -> {verdict.decode('ascii').strip()}")
            if line == PONG and not args.scan and not args.answer:
                pong = True
                break
    except serial.SerialException as err:
        print(f"Fail: the port failed during the check: {err}", file=sys.stderr)
        return 1
    finally:
        port.close()

    if args.answer:
        print()
        if answered:
            print(f"Pass: answered {answered} button press(es) - both lamps should have been seen.")
            return 0
        print(
            f"Fail: no EVT TRIGGER in {args.seconds:g} s, so no verdict was sent and no lamp pulsed. "
            "Press the button while this runs.",
            file=sys.stderr,
        )
        return 1

    if args.scan:
        found = scan_addresses(seen)
        print()
        if not found:
            print(
                f"Fail: no EVT I2C line in {args.seconds:g} s. Either nothing is on the bus, or the scan "
                "did not reach the board - run this tool without --scan first, because a board that "
                "cannot answer CMD PING cannot answer CMD SCAN either.",
                file=sys.stderr,
            )
            return 1
        for address, what in found.items():
            print(f"  found {address}  {what}")
        missing = [
            f"{address} ({what})" for address, what in EXPECTED.items() if address not in found
        ]
        if missing:
            print(f"  not found: {', '.join(missing)}")
        print(f"Pass: {len(found)} address(es) answered in the {args.seconds:g} s window.")
        return 0

    if pong:
        print(f"Pass: {args.port} answered EVT PONG.")
        return 0
    print(
        f"Fail: no EVT PONG within {args.seconds:g} s on {args.port}. "
        f"Check the cable, the board power and the baud rate ({BAUD}).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
