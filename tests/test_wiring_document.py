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

#: The terminal names in the wiring table that are ESP32 GPIO numbers rather than rails.
ESP_PIN = re.compile(r"ESP32\s*`(\d{1,2})`")
CONFIG_PIN = re.compile(r"constexpr\s+int\s+(PIN_[A-Z0-9_]+)\s*=\s*(\d+)\s*;")


def firmware_pins() -> dict[str, int]:
    return {
        name: int(number) for name, number in CONFIG_PIN.findall(CONFIG.read_text(encoding="utf-8"))
    }


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
    pins = firmware_pins()
    assert pins == {
        "PIN_BUTTON": 4,
        "PIN_LED_PASS": 5,
        "PIN_LED_RETAKE": 6,
        "PIN_I2C_SDA": 8,
        "PIN_I2C_SCL": 9,
    }


def test_the_wiring_table_names_exactly_the_firmware_pins() -> None:
    """Both directions: a wire for a pin the firmware does not know, and a pin with no wire."""
    documented = documented_pins(PAIR[0])
    declared = {str(number) for number in firmware_pins().values()}
    assert documented == declared
    assert documented, (
        "the table parsed empty - the check would pass on a document that says nothing"
    )


def test_both_languages_of_the_wiring_table_agree_on_the_pins() -> None:
    assert documented_pins(PAIR[0]) == documented_pins(PAIR[1])
