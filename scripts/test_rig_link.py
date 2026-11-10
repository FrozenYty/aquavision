#!/usr/bin/env python3
"""Rig link bench check: are the cable and the board alive before anything else is debugged?

The board answers `CMD PING` with `EVT PONG`, and that single exchange proves the cable, the power and
the baud rate. The rig requires a keepalive at least every two seconds, so the tool sends one on that
schedule and prints every line the board sends - a board that talks is a different fault from one that
is silent, and finding out which is the first question every other check depends on.

    python scripts/test_rig_link.py
    python scripts/test_rig_link.py --port COM5 --seconds 10

Exit codes: 0 a PONG arrived, 1 no PONG in time or the port could not be opened.

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
PONG = "EVT PONG"
BAUD = 115200
KEEPALIVE_SECONDS = 2.0
DEFAULT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 0.2


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
        help=f"how long to wait for EVT PONG (default {DEFAULT_SECONDS:g})",
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

    print(
        f"Sending CMD PING every {KEEPALIVE_SECONDS:g} s, "
        f"waiting up to {args.seconds:g} s for EVT PONG"
    )
    pong = False
    deadline = time.monotonic() + args.seconds
    # The first ping goes out at once: the rig wants a command every two seconds, not two seconds of
    # silence before the first one.
    next_ping = 0.0
    try:
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_ping:
                port.write(PING)
                next_ping = now + KEEPALIVE_SECONDS
            raw = port.readline()
            if not raw:
                continue
            line = raw.decode("ascii", errors="replace").strip()
            if not line:
                continue
            print(f"  {line}")
            if line == PONG:
                pong = True
                break
    except serial.SerialException as err:
        print(f"Fail: the port failed during the check: {err}", file=sys.stderr)
        return 1
    finally:
        port.close()

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
