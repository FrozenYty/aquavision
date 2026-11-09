"""Hold web/static/js/api.js to the API contract.

The frontend once marked twenty calls as "provisional" while the contract grew to cover every one of
them; the comments went on telling readers the routes did not exist. These checks keep both halves of
the claim true: no such marker comes back, and every function the module exports names a route that
docs/api-contract-en.md §6 actually lists. The reverse is not required — a few contract routes have no
caller in the browser yet, and inventing one to satisfy a test would be worse than the gap.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_JS = ROOT / "web" / "static" / "js" / "api.js"
CONTRACT = ROOT / "docs" / "api-contract-en.md"

EXPORTED_ARROW = re.compile(r"export const (\w+) = \([^)]*\) =>")
EXPORTED_CALL = re.compile(
    r'export const (\w+) = \([^)]*\) =>\s*request\("([A-Z]+)",\s*(`[^`]*`|"[^"]*")'
)
CONTRACT_ROW = re.compile(r"^\| (GET|POST|PATCH|PUT|DELETE) \| `(/api/[^`]+)` \|", re.MULTILINE)


def normalise(path: str) -> str:
    """'/frames/${frameId}' and '/frames/{frame_id}' both become '/frames/{}'."""
    path = re.sub(r"\$\{[^}]+\}", "{}", path)
    return re.sub(r"\{[^}]*\}", "{}", path)


def exported_routes() -> dict[str, tuple[str, str]]:
    source = API_JS.read_text(encoding="utf-8")
    return {
        name: (method, normalise(path.strip('`"')))
        for name, method, path in EXPORTED_CALL.findall(source)
    }


def contract_routes() -> set[tuple[str, str]]:
    table = CONTRACT.read_text(encoding="utf-8")
    return {
        (method, normalise(path.removeprefix("/api")))
        for method, path in CONTRACT_ROW.findall(table)
    }


def test_no_provisional_marker_remains():
    count = API_JS.read_text(encoding="utf-8").lower().count("provisional")
    assert count == 0, f"api.js says 'provisional' {count} time(s); the contract covers every route"


def test_every_exported_function_was_parsed():
    """Guard the parser: a function it cannot read would silently escape the route check."""
    source = API_JS.read_text(encoding="utf-8")
    arrows = set(EXPORTED_ARROW.findall(source))
    missed = sorted(arrows - set(exported_routes()))
    assert not missed, f"could not read the route of {missed}; keep calls as request(METHOD, path)"


def test_contract_table_was_parsed():
    assert len(contract_routes()) >= 40, "the route table in api-contract §6 was not found"


def test_every_exported_function_maps_to_a_contract_route():
    known = contract_routes()
    unknown = sorted(
        f"{name}: {method} {path}"
        for name, (method, path) in exported_routes().items()
        if (method, path) not in known
    )
    assert not unknown, f"api.js calls routes the contract does not list: {unknown}"
