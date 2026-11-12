"""The bilingual check must compare structure, not only heading levels.

Every case here is a shape that actually reached a release, not a hypothetical:

- the data model listed nine entities in Chinese where the English listed thirteen, and the row count
  went unnoticed for five days;
- the English SRS version of Table 2-3 was missing two rows that its own revision record said were
  added;
- six Chinese NFR tables lost their header row in translation, so each rendered a data row as its
  header.

Heading comparison passed all three, because all three pairs had the same headings. That is the defect
this file guards: a check that proves the outline matches does not prove the documents agree.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-bilingual.py"


def _load_check() -> object:
    """Import `scripts/check-bilingual.py`, whose filename cannot be imported as a module."""
    spec = importlib.util.spec_from_file_location("check_bilingual", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load_check()


def _pair(tmp_path: Path, english: str, chinese: str) -> list[str]:
    """Write a documents pair and return what the check reports about it."""
    en_path = tmp_path / "doc-en.md"
    zh_path = tmp_path / "doc-zh.md"
    en_path.write_text(english, encoding="utf-8")
    zh_path.write_text(chinese, encoding="utf-8")
    return check.compare_pair(en_path, zh_path)


def test_a_table_that_lost_a_row_is_reported(tmp_path: Path) -> None:
    """The data model case: same headings, one table a row shorter in Chinese."""
    english = (
        "# Entities\n\n| Entity | Note |\n|---|---|\n| A | 1 |\n| B | 2 |\n| C | 3 |\n| D | 4 |\n"
    )
    chinese = "# 实体\n\n| 实体 | 说明 |\n|---|---|\n| A | 1 |\n| B | 2 |\n| C | 3 |\n"

    problems = _pair(tmp_path, english, chinese)

    assert len(problems) == 1
    assert "en 5 rows" in problems[0] and "zh 4 rows" in problems[0]


def test_a_table_that_lost_its_header_row_is_reported(tmp_path: Path) -> None:
    """The six NFR tables case: the separator replaced the header, so one row fewer remains."""
    english = "# R\n\n| ID | Req |\n|---|---|\n| A-1 | x |\n| A-2 | y |\n"
    chinese = "# R\n\n| A-1 | x |\n|---|---|\n| A-2 | y |\n"

    problems = _pair(tmp_path, english, chinese)

    assert len(problems) == 1
    assert "rows" in problems[0]


def test_a_section_that_lost_its_table_is_reported(tmp_path: Path) -> None:
    """A whole block present on one side only — the page-name table case."""
    english = "# Section\n\n| Name | Page |\n|---|---|\n| Dashboard | home |\n"
    chinese = "# 章节\n\n这个页面叫什么，中文里没有那张表。\n"

    problems = _pair(tmp_path, english, chinese)

    assert len(problems) == 1
    assert "table" in problems[0]


def test_a_section_that_lost_its_code_block_is_reported(tmp_path: Path) -> None:
    """A command block dropped in translation — the CMD SCAN row's neighbour defect."""
    english = "# Section\n\n```\npython scripts/init_db.py\n```\n"
    chinese = "# 章节\n\n跑一下初始化脚本。\n"

    problems = _pair(tmp_path, english, chinese)

    assert len(problems) == 1
    assert "code block" in problems[0]


def test_different_wording_with_the_same_structure_is_not_reported(tmp_path: Path) -> None:
    """The false-positive guard: a translation is expected to differ word for word."""
    english = "# Limits\n\n| ID | Requirement |\n|---|---|\n| N-1 | Two seconds. |\n| N-2 | Eight hours. |\n"
    chinese = "# 限制\n\n| 编号 | 需求 |\n|---|---|\n| N-1 | 两秒。 |\n| N-2 | 八小时。 |\n"

    assert _pair(tmp_path, english, chinese) == []


def test_the_repository_pairs_are_in_sync() -> None:
    """The real documents, so the check cannot rot into something that only passes on fixtures."""
    pairs = [(en, zh) for en, zh in check.iter_pairs() if zh.exists()]
    assert pairs, "no document pairs found"

    failures = {str(en): check.compare_pair(en, zh) for en, zh in pairs}
    assert not any(failures.values()), {name: found for name, found in failures.items() if found}
