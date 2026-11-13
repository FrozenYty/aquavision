"""Find which command byte makes the turbidity sensor answer.

The vendor manual gives the *shape* of a register read and states the I2C address (0x49), but publishes no
table of command bytes. So the byte `config.h` uses was found by sweeping the address space rather than by
reading a document - and this is the script that found it, kept so the finding can be repeated when a
different batch of the same sensor disagrees.

    python scripts/test_turbidity.py --port COM5

It asks the firmware to read each command in turn (`CMD TREAD <hex>`) and prints what came back. A value
inside the sensor's documented output range (1 to 16000; 14000 for a 20 mm white board) is a candidate. A
constant 0, or 65535, is not: the sensor acknowledged and had nothing to say.
"""

from __future__ import annotations

import argparse
import sys
import time

import serial

BAUD = 115200
#: Copied rather than imported for the same reason the other bench tools copy theirs: `app.rig.protocol`
#: pulls in the application, and this script should run with nothing but pyserial installed. The test
#: `tests/test_rig_scan.py` holds the copy to the original.
REGISTER_READ_PREFIX = "EVT TREG "
#: The sensor's documented output range. Anything outside it is a non-answer rather than a measurement.
PLAUSIBLE = range(1, 16001)


def parse_read(line: str) -> tuple[int, int] | None:
    """`EVT TREG 00 14000` -> (0x00, 14000). Anything else -> None."""
    if not line.startswith(REGISTER_READ_PREFIX):
        return None
    parts = line[len(REGISTER_READ_PREFIX) :].split()
    if len(parts) != 2:
        return None
    try:
        return int(parts[0], 16), int(parts[1])
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="the rig's serial port, such as COM5")
    parser.add_argument(
        "--first", type=lambda v: int(v, 0), default=0x00, help="first command byte"
    )
    parser.add_argument("--last", type=lambda v: int(v, 0), default=0x1F, help="last command byte")
    parser.add_argument(
        "--settle", type=float, default=0.12, help="seconds to wait for each answer"
    )
    args = parser.parse_args()

    print(f"Opening {args.port} at {BAUD} baud")
    port = serial.Serial(args.port, BAUD, timeout=0.05)
    time.sleep(0.3)
    port.reset_input_buffer()

    candidates = []
    for command in range(args.first, args.last + 1):
        # Drain first: an answer that arrives late belongs to the previous request, and printing it against
        # this command is how the first sweep produced a table that was off by one.
        port.reset_input_buffer()
        port.write(f"CMD TREAD {command:02X}\n".encode("ascii"))
        deadline = time.monotonic() + args.settle
        value: int | None = None
        while time.monotonic() < deadline:
            line = port.readline().decode("ascii", errors="replace").strip()
            if not line:
                continue
            answer = parse_read(line)
            if answer is None or answer[0] != command:
                continue
            value = answer[1]
            break
        if value is None:
            print(f"  {command:02X}  no answer")
            continue
        mark = ""
        if value in PLAUSIBLE:
            mark = "   <- candidate"
            candidates.append((command, value))
        print(f"  {command:02X}  {value:>6}{mark}")

    port.close()
    print()
    if candidates:
        print(f"{len(candidates)} candidate(s) inside the documented range 1-16000:")
        for command, value in candidates:
            print(f"  CMD {command:02X} -> {value}")
        return 0
    print(
        "No command byte returned a value in 1-16000. The sensor acknowledged every read and had nothing to"
        " say: suspect the probe is not against a surface, or that this batch needs a measurement command"
        " written before the read.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
