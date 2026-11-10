"""Static checks over the page templates.

These catch the two mistakes that cost the most time when ten pages are written in parallel: a link to
a page that does not exist, and a script looking up an element id that the markup never defines. Both
fail silently in a browser — a dead link clicks to a 404, a missing id throws only when the code path
runs — so they are checked here instead of being found during a demonstration.

Nothing here loads a browser: the checks read the files as text.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent / "web"
TEMPLATES = WEB / "templates"
LAYOUT_JS = WEB / "static" / "js" / "layout.js"

PAGES = sorted(TEMPLATES.glob("*.html"))
LOGIN = "login.html"


def uses_shell(html: str) -> bool:
    return re.search(r"renderShell\(\)", html) is not None


def test_there_are_pages_to_check():
    assert PAGES, f"no templates found under {TEMPLATES}"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_links_point_to_existing_pages(page: Path):
    html = page.read_text(encoding="utf-8")
    for href in re.findall(r'href="([^"]+\.html)"', html):
        target = (page.parent / href).resolve()
        assert target.is_file(), f"{page.name} links to {href}, which does not exist"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_every_element_id_the_script_looks_up_exists(page: Path):
    html = page.read_text(encoding="utf-8")
    wanted = set(re.findall(r'\$\("([^"]+)"\)', html))
    defined = set(re.findall(r'id="([^"]+)"', html))
    missing = sorted(wanted - defined)
    assert not missing, f"{page.name} looks up {missing}, which the markup never defines"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_element_ids_are_unique(page: Path):
    html = page.read_text(encoding="utf-8")
    ids = re.findall(r'id="([^"]+)"', html)
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    assert not duplicates, f"{page.name} defines {duplicates} more than once"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_every_page_except_login_uses_the_shared_shell(page: Path):
    html = page.read_text(encoding="utf-8")
    if page.name == LOGIN:
        assert not uses_shell(html), "the login page stands alone and should not render the shell"
        return
    assert uses_shell(html), f"{page.name} never calls renderShell()"


def test_menu_entries_point_to_pages_that_exist():
    menu = LAYOUT_JS.read_text(encoding="utf-8")
    hrefs = set(re.findall(r'href:\s*"([^"]+\.html)"', menu))
    assert hrefs, "the menu defines no links"
    missing = sorted(href for href in hrefs if not (TEMPLATES / href).is_file())
    assert not missing, f"menu links to {missing}, which do not exist"


def test_menu_page_ids_match_the_templates():
    """Every page that renders the shell must have a menu entry; the shell finds the current page by it."""
    menu = LAYOUT_JS.read_text(encoding="utf-8")
    menu_hrefs = set(re.findall(r'href:\s*"([^"]+\.html)"', menu))
    rendered = {page.name for page in PAGES if uses_shell(page.read_text(encoding="utf-8"))}

    unlinked = sorted(rendered - menu_hrefs)
    assert not unlinked, f"{unlinked} render but are absent from the menu, so they are unreachable"
