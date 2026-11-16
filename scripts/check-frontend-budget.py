"""Bound raw JS/CSS per page, including inline code and every literal import (mock included)."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

JS_LIMIT = 128 * 1024
CSS_LIMIT = 320 * 1024
IMPORT = re.compile(
    r"\b(?:import|export)\s+(?:[^;'\"]*?\s+from\s*)?['\"]([^'\"]+)['\"]"
    r"|\bimport\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
)
CSS_IMPORT = re.compile(r"@import\s+(?:url\(\s*)?['\"]([^'\"]+)['\"]")


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.inline = {"js": [], "css": []}
        self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("style"):
            self.inline["css"].append(attrs["style"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.links.append(("css", attrs["href"]))
        if tag == "script":
            if attrs.get("src"):
                self.links.append(("js", attrs["src"]))
            else:
                self.capture = "js"
        elif tag == "style":
            self.capture = "css"

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.capture = None

    def handle_data(self, data):
        if self.capture:
            self.inline[self.capture].append(data)


def measure(page: Path, web: Path) -> dict:
    web = web.resolve()
    parser = Assets()
    parser.feed(page.read_text(encoding="utf-8"))
    totals = {"page": page.name, "js": 0, "css": 0}
    visited = set()

    def scan(source, parent, kind):
        pattern = IMPORT if kind == "js" else CSS_IMPORT
        for match in pattern.finditer(source):
            visit(next(value for value in match.groups() if value), parent, kind)

    def visit(url, parent, kind):
        parts = urlsplit(url)
        if parts.scheme or parts.netloc:
            raise ValueError(f"{page.name}: external asset {url}")
        path = (
            web / unquote(parts.path).lstrip("/")
            if parts.path.startswith("/")
            else parent / unquote(parts.path)
        ).resolve()
        if not path.is_relative_to(web):
            raise ValueError(f"{page.name}: asset leaves web root: {url}")
        if path in visited:
            return
        visited.add(path)
        totals[kind] += path.stat().st_size
        scan(path.read_text(encoding="utf-8"), path.parent, kind)

    for kind, url in parser.links:
        visit(url, page.parent, kind)
    for kind, blocks in parser.inline.items():
        for source in blocks:
            totals[kind] += len(source.encode("utf-8"))
            scan(source, page.parent, kind)
    return totals


def check(rows, *, js_limit=JS_LIMIT, css_limit=CSS_LIMIT) -> int:
    print(f"{'Page':28} {'JS bytes':>10} {'CSS bytes':>10} {'Result':>8}")
    failed = False
    for row in rows:
        over = row["js"] > js_limit or row["css"] > css_limit
        failed |= over
        print(f"{row['page']:28} {row['js']:10} {row['css']:10} {'OVER' if over else 'OK':>8}")
    print(f"Ceilings per page: JS {js_limit} bytes; CSS {css_limit} bytes (uncompressed)")
    return int(failed)


def main() -> int:
    web = Path(__file__).resolve().parents[1] / "web"
    try:
        rows = [measure(page, web) for page in sorted((web / "templates").glob("*.html"))]
    except (OSError, ValueError) as error:
        print(f"Frontend budget failed: {error}", file=sys.stderr)
        return 1
    if not rows:
        print("Frontend budget failed: no pages found", file=sys.stderr)
        return 1
    return check(rows)


if __name__ == "__main__":
    sys.exit(main())
