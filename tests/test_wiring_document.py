"""The wiring document and the firmware must name the same pins.

`docs/procurement-en.md` section 5 tells a person which ESP32 terminal each wire goes to; the same numbers
are in `firmware/main/src/config.h`, which is the only place the firmware reads them. If one moves and the
other does not, the symptom is a rig that **is** wired correctly and behaves as if it is not — the most
expensive kind of fault to find, because each document looks right on its own.

The same drift applies to the two languages of that table: a wire colour or a pin number that differs
between them is two instructions, and the person wiring cannot tell which one is current.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "firmware" / "main" / "src" / "config.h"
PAIR = [REPO / "docs" / "procurement-en.md", REPO / "docs" / "procurement-zh.md"]
DRAWING = REPO / "scripts" / "draw_wiring.py"

#: The terminal names in the wiring table that are ESP32 GPIO numbers rather than rails.
ESP_PIN = re.compile(r"ESP32\s*`(\d{1,2})`")
CONFIG_PIN = re.compile(r"constexpr\s+[A-Za-z0-9_:]+\s+(PIN_[A-Z0-9_]+)\s*=\s*(\d+)\s*;")
CONFIG_PIN_ARRAY = re.compile(
    r"constexpr\s+[A-Za-z0-9_:]+\s+(PIN_[A-Z0-9_]+)\s*\[[^\]]*\]\s*=\s*\{([^}]*)\}"
)
CONFIG_BAR_FIRST = re.compile(r"constexpr\s+[A-Za-z0-9_:]+\s+PIN_BAR_FIRST\s*=\s*(\d+)\s*;")
CONFIG_BAR_COUNT = re.compile(r"constexpr\s+[A-Za-z0-9_:]+\s+BAR_LEDS\s*=\s*(\d+)\s*;")


def firmware_pins() -> dict[str, int]:
    """Every single-pin constant in `config.h`, by name.

    `PIN_BAR_FIRST` is in here too: it is a pin the firmware declares, and it is also the bar's first
    element, which is why the bar's own list is read separately rather than derived from it.
    """
    return {
        name: int(number) for name, number in CONFIG_PIN.findall(CONFIG.read_text(encoding="utf-8"))
    }


def firmware_bar_pins() -> list[int]:
    """The bar's pins, in the order the firmware lights them.

    Two spellings are read, because `config.h` may enumerate the bar or state a first pin and a count. The
    enumerated list wins when both are present: a count cannot express a gap, and this bar skips the two USB
    pins. A name inside the list is resolved through the pin constants, and a name that cannot be resolved is
    a failure rather than a shorter list - a parse that quietly drops one entry is how a test passes on
    nothing.
    """
    text = CONFIG.read_text(encoding="utf-8")
    enumerated = CONFIG_PIN_ARRAY.search(text)
    if enumerated:
        body = enumerated.group(2)
        for name, number in firmware_pins().items():
            body = body.replace(name, str(number))
        unresolved = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", body)
        assert not unresolved, f"the bar's pin list names {unresolved}, which is not a number"
        return [int(number) for number in re.findall(r"\d+", body)]

    first = CONFIG_BAR_FIRST.search(text)
    count = CONFIG_BAR_COUNT.search(text)
    if first and count:
        return list(range(int(first.group(1)), int(first.group(1)) + int(count.group(1))))
    return []


def firmware_wired_pins() -> set[str]:
    """Every GPIO the firmware declares a wire for: the single pins and the bar."""
    declared = {str(number) for number in firmware_pins().values()}
    return declared | {str(number) for number in firmware_bar_pins()}


def wiring_section(path: Path) -> str:
    """Section 5 of the wiring document, from its heading to the next one."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(
        index
        for index, line in enumerate(lines)
        if line.startswith("## 5.") or line.startswith("## 五、供电与接线")
    )
    end = next(index for index in range(start + 1, len(lines)) if lines[index].startswith("## "))
    return "\n".join(lines[start:end])


def documented_pins(path: Path) -> set[str]:
    return set(ESP_PIN.findall(wiring_section(path)))


def test_the_firmware_still_declares_the_pins_this_project_wires() -> None:
    """A rename in `config.h` is a rename everywhere; this is the list the rest of the file depends on."""
    assert firmware_pins() == {
        "PIN_BUTTON": 4,
        "PIN_LED_PASS": 5,
        "PIN_LED_RETAKE": 6,
        "PIN_LED_STATE": 7,
        "PIN_I2C_SDA": 8,
        "PIN_I2C_SCL": 9,
        "PIN_BAR_FIRST": 10,
    }
    assert firmware_bar_pins() == [10, 11, 12, 13, 14, 15, 16, 17, 18, 21], (
        "the bar is ten lamps on GPIO 10-18 and 21 in this project's documents, with the last one on the "
        f"right header because 19 and 20 are the USB pair; config.h declares {firmware_bar_pins()}"
    )


def test_the_wiring_table_names_exactly_the_firmware_pins() -> None:
    """Both directions: a wire for a pin the firmware does not know, and a pin with no wire."""
    documented = documented_pins(PAIR[0])
    declared = firmware_wired_pins()
    assert documented == declared
    assert documented, (
        "the table parsed empty - the check would pass on a document that says nothing"
    )


def test_both_languages_of_the_wiring_table_agree_on_the_pins() -> None:
    assert documented_pins(PAIR[0]) == documented_pins(PAIR[1])


def test_the_drawing_script_draws_the_pins_the_firmware_declares() -> None:
    """The picture is a third copy of the pin numbers, so it gets held to the same source.

    `docs/rig-wiring.svg` is generated from `scripts/draw_wiring.py`, whose `USED` table names the pins it
    draws. Without this check a pin could move in `config.h`, be fixed in the table and still be drawn
    wrong - and the drawing is the copy a person actually wires from.
    """
    source = DRAWING.read_text(encoding="utf-8")
    used = re.search(r"USED = \{([^}]*)\}", source)
    assert used is not None, "the drawing script no longer has a USED table"
    drawn = {name for name in re.findall(r'"(\d{1,2})":', used.group(1))}
    assert drawn == firmware_wired_pins()
