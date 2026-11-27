"""The P4-18 kit card must list every item, in both languages, within one printed page.

A card that is missing a line, or has grown a second page, is a card the first rehearsal has to work
around - which is exactly what `P4-18` exists to stop. The eight items are the ones `PLAN.md` names,
in the order it names them; the mapping below is written out rather than derived, because a
translation that spells a different word is the defect this check exists to find.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAIR = {
    "en": REPO / "docs" / "demo-kit-card-en.md",
    "zh": REPO / "docs" / "demo-kit-card-zh.md",
}

#: The eight PLAN P4-18 items: the English name in the ticket, the Chinese name the card uses.
ITEMS = {
    "laptop": "笔记本",
    "offline database copy": "离线数据库副本",
    "camera at index 1": "索引 1 的摄像头",
    "lamp": "台灯",
    "polariser": "偏振片",
    "rig": "装置（ESP32-S3）",
    "spare usb cable": "备用 USB 线",
    "power": "电源",
}

#: One A4 page at 11 pt holds roughly 55 lines of this card; 60 is the bound, with room for a heading
#: or a wrapped line and none for a second page.
MAX_LINES = 60

#: A tick box line whose item name is bold: `- [ ] **Item** - what to check`.
TICK_BOX = re.compile(r"^\s*[-*]\s*\[ \]\s*\*\*(.+?)\*\*")

#: An absolute Windows path, the shape `scripts/check-paths.py` rejects in documents.
WINDOWS_PATH = re.compile(r"[A-Za-z]:[\\/]|\\\\[A-Za-z0-9_.-]+\\")


def card(language: str) -> str:
    """The card's text; a missing half of the pair fails by name rather than by IndexError."""
    path = PAIR[language]
    assert path.is_file(), f"{path} is missing; the card is a pair, not one file"
    return path.read_text(encoding="utf-8")


def ticked_item_names(language: str) -> list[str]:
    """The bold name of every ticked item line, in document order and with case kept."""
    return [
        match.group(1).strip()
        for line in card(language).splitlines()
        if (match := TICK_BOX.match(line))
    ]


def test_the_card_exists_in_both_languages() -> None:
    assert PAIR["en"].is_file(), "docs/demo-kit-card-en.md is missing"
    assert PAIR["zh"].is_file(), "docs/demo-kit-card-zh.md is missing"


def test_every_plan_item_has_its_own_tick_box() -> None:
    """The eight items, each its own bold tick box, in the order PLAN.md names them."""
    assert len(ITEMS) == 8, "the ticket names eight items"
    english = [name.lower() for name in ticked_item_names("en")]
    chinese = ticked_item_names("zh")
    assert english == list(ITEMS), f"the English card's items, in order, are {english}"
    assert chinese == list(ITEMS.values()), f"the Chinese card's items, in order, are {chinese}"


def test_the_card_stays_within_one_printed_page() -> None:
    for language, path in PAIR.items():
        lines = card(language).splitlines()
        assert len(lines) <= MAX_LINES, f"{path.name} is {len(lines)} lines, page bound {MAX_LINES}"


def test_the_card_carries_no_absolute_windows_path() -> None:
    for language, path in PAIR.items():
        found = WINDOWS_PATH.findall(card(language))
        assert not found, f"{path.name} carries machine-specific path(s): {found}"
