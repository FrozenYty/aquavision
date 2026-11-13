"""`CMD SCAN` and the bench tool that sends it (P3-17).

The bench tool copies its protocol tokens on purpose: importing `app.rig.protocol` pulls in
`app.vision.quality`, which pulls in OpenCV and numpy, and a laptop whose only job is to check one cable
should not need those. A copy is a drift risk, so the copy is held to the grammar here instead of trusted —
the same way `tests/test_api_js.py` holds the front end to the contract.

The scan itself is tested as a pure function, because the half that can be wrong is the reading, not the
serial port.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.rig import protocol

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "scripts" / "test_rig_link.py"

#: The two devices this rig is built to have on the bus, from `firmware/main/src/config.h`.
EXPECTED = {"3C": "OLED", "49": "turbidity sensor"}


def _load_tool() -> object:
    """Import `scripts/test_rig_link.py`, which is not a module on the path.

    Safe without hardware: `serial` is imported inside `main`, so loading the file opens no port.
    """
    spec = importlib.util.spec_from_file_location("test_rig_link_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_grammar_has_a_scan_command() -> None:
    assert protocol.scan() == "CMD SCAN\n"


def test_the_bench_tool_sends_exactly_what_the_firmware_parses() -> None:
    """The two tokens the tool copies, compared against the grammar they were copied from."""
    tool = _load_tool()
    assert tool.PING.decode("ascii") == protocol.ping()
    assert tool.SCAN.decode("ascii") == protocol.scan()


def test_the_verdicts_the_tool_sends_are_the_ones_the_server_would_write() -> None:
    """`--answer` stands in for the server, so its lines are held to the server's grammar."""
    tool = _load_tool()
    sent = [line.decode("ascii") for line in tool.VERDICTS]
    assert protocol.result(95, "PASS") in sent
    assert protocol.result(40, "RETAKE", protocol.REASON_LOW_LIGHT) in sent
    # Two different verdicts, so that one run can show both lamps.
    assert len(sent) == 2


def test_the_tool_expects_the_two_addresses_the_rig_actually_has() -> None:
    assert _load_tool().EXPECTED == EXPECTED


def test_a_scan_reports_what_answered_and_names_the_ones_the_rig_expects() -> None:
    tool = _load_tool()
    found = tool.scan_addresses(
        ["EVT PONG", "EVT I2C 3C", "EVT I2C 49", "EVT I2C 68", "something else"]
    )
    assert found == {
        "3C": "OLED",
        "49": "turbidity sensor",
        "68": "something the rig does not expect",
    }


def test_hex_case_does_not_change_which_device_is_which() -> None:
    """Hex arrives in either case; a lower-case address must not read as a different device."""
    assert _load_tool().scan_addresses(["EVT I2C 3c"]) == {"3C": "OLED"}


def test_a_scan_that_found_nothing_reports_nothing_rather_than_guessing() -> None:
    """A board that cannot answer `CMD PING` cannot answer `CMD SCAN` either, so an empty result is real."""
    assert _load_tool().scan_addresses(["EVT PONG", "EVT SCREEN READY 0"]) == {}
