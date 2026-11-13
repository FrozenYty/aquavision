"""The turbidity register probe, and the tokens it copies (P3-17).

Same reason as `test_rig_scan.py`: `scripts/test_turbidity.py` copies its protocol tokens so that it runs with
nothing but pyserial installed, and a copy is held to the grammar here rather than trusted.

The third test exists because the first version of that script printed its own loop counter instead of the
command byte the sensor answered with, which produced a sweep that was off by one and looked plausible.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.rig import protocol

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "scripts" / "test_turbidity.py"


def _load_tool() -> object:
    """Import `scripts/test_turbidity.py`, which is not a module on the path.

    Safe without hardware: `serial` is imported at module scope but no port is opened until `main` runs.
    """
    spec = importlib.util.spec_from_file_location("test_turbidity_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_probe_sends_a_command_the_firmware_parses() -> None:
    """`CMD TREAD <hex>` is what `protocol.cpp` matches on and parses with `strtol(..., 16)`."""
    assert protocol.register_read(0x15) == "CMD TREAD 15\n"
    assert protocol.register_read(0x00) == "CMD TREAD 00\n"


def test_the_probe_reads_the_prefix_the_firmware_prints() -> None:
    tool = _load_tool()
    assert tool.REGISTER_READ_PREFIX == protocol.REGISTER_READ_PREFIX


def test_parse_read_takes_the_command_from_the_line_not_from_the_caller() -> None:
    """Guards the off-by-one sweep: the answer carries the command byte, and it is the one to trust."""
    tool = _load_tool()
    assert tool.parse_read("EVT TREG 15 5376") == (0x15, 5376)
    assert tool.parse_read("EVT TREG 00 -1") == (0x00, -1)
    assert tool.parse_read("EVT PONG") is None
    assert tool.parse_read("EVT TREG 15") is None
    assert tool.parse_read("EVT TREG zz 1") is None
