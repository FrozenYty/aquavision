"""One page, one name: the menu, each template's title, SRS §5.2 and the traceability matrix must agree.

These are four hand-kept copies of the same thirteen names. Checked by eye they drift, which is what
happened before SRS V1.11 settled them (handover §3.7). SRS §5.2 is the authority; every other list is
compared with it, page by page.
"""

from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
TEMPLATES = ROOT / "web" / "templates"
LAYOUT_JS = ROOT / "web" / "static" / "js" / "layout.js"

PAGE_IDS = [f"P-{n:02d}" for n in range(1, 14)]
# The P-02 heading in the matrix also covers the shared shell; that note is not part of the name.
SHELL_NOTE = {"zh": "（含公共外壳）", "en": " (and the shared shell)"}


def srs_names(lang: str) -> dict[str, str]:
    text = (DOCS / f"srs-{lang}.md").read_text(encoding="utf-8")
    section = text[text.index("### 5.2") : text.index("### 5.3")]
    return dict(re.findall(r"^\| (P-\d\d) \| ([^|]+?) \|", section, flags=re.M))


def matrix_names(lang: str) -> dict[str, str]:
    text = (DOCS / f"traceability-{lang}.md").read_text(encoding="utf-8")
    heading = r"^### 4\.\d+ (P-\d\d) (.+?)(?:（图 \d+）| \(figure \d+\))$"
    return {
        pid: name.replace(SHELL_NOTE[lang], "")
        for pid, name in re.findall(heading, text, flags=re.M)
    }


def matrix_templates(lang: str) -> dict[str, str]:
    text = (DOCS / f"traceability-{lang}.md").read_text(encoding="utf-8")
    return dict(re.findall(r"^\| (P-\d\d) [^|]+\| `([\w-]+\.html)` \|", text, flags=re.M))


def menu() -> dict[str, tuple[str, str]]:
    source = LAYOUT_JS.read_text(encoding="utf-8")
    entries = re.findall(r'\{ id: "(P-\d\d)", label: "([^"]+)", href: "([^"]+)" \}', source)
    return {pid: (label, href) for pid, label, href in entries}


def title_of(page: Path) -> str:
    match = re.search(r"<title>(.+?) · AquaVision</title>", page.read_text(encoding="utf-8"))
    assert match, f"{page.name}: no <title> of the form 'NAME · AquaVision'"
    return match.group(1)


def h1_of(page: Path) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page.read_text(encoding="utf-8"), flags=re.S)
    assert match, f"{page.name}: no <h1>"
    return re.sub(r"<[^>]+>", "", match.group(1)).strip()


def test_every_list_names_all_thirteen_pages():
    for lang in ("zh", "en"):
        assert sorted(srs_names(lang)) == PAGE_IDS, f"SRS {lang} §5.2"
        assert sorted(matrix_names(lang)) == PAGE_IDS, f"traceability-{lang} headings"
        assert sorted(matrix_templates(lang)) == PAGE_IDS, f"traceability-{lang} summary table"
    # Sign-in is the one page outside the menu.
    assert sorted(menu()) == PAGE_IDS[1:], "layout.js menu"


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_matrix_names_equal_srs(lang: str):
    srs, matrix = srs_names(lang), matrix_names(lang)
    wrong = {pid: (matrix[pid], srs[pid]) for pid in PAGE_IDS if matrix[pid] != srs[pid]}
    assert not wrong, f"traceability-{lang} disagrees with SRS §5.2 (matrix, SRS): {wrong}"


@pytest.mark.parametrize("pid", PAGE_IDS)
def test_page_name_is_the_same_everywhere(pid: str):
    name = srs_names("zh")[pid]
    template = matrix_templates("zh")[pid]
    assert matrix_templates("en")[pid] == template, (
        f"{pid}: the two matrices name different templates"
    )
    page = TEMPLATES / template
    assert page.is_file(), f"{pid}: the matrix names {template}, which does not exist"

    assert title_of(page) == name, (
        f"{pid} {template}: <title> says {title_of(page)!r}, SRS §5.2 says {name!r}"
    )
    if pid == "P-01":
        return  # the sign-in page's <h1> is the product line, and it has no menu entry
    assert h1_of(page) == name, (
        f"{pid} {template}: <h1> says {h1_of(page)!r}, SRS §5.2 says {name!r}"
    )
    label, href = menu()[pid]
    assert label == name, f"{pid}: menu label {label!r}, SRS §5.2 says {name!r}"
    assert href == template, f"{pid}: menu links to {href}, the matrix says {template}"
    assert "renderShell()" in page.read_text(encoding="utf-8"), (
        f"{template} does not render the shell"
    )


def one_edit_apart(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1 :] == short for i in range(len(long_)))


def test_no_two_templates_differ_by_one_character():
    stems = sorted(page.stem for page in TEMPLATES.glob("*.html"))
    close = [(a, b) for a, b in combinations(stems, 2) if one_edit_apart(a, b)]
    assert not close, f"template names one character apart invite editing the wrong file: {close}"
