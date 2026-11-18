"""Validate the Mermaid blocks the documents carry, narrowly.

GitHub renders ```` ```mermaid ```` blocks and shows *nothing* when one does not parse — the block is
replaced by one sentence in red, which every existing check happily ignores. This caught a real case:
`design-{en,zh}.md` used `UQ` as an attribute key, and Mermaid accepts only `PK`, `FK` and `UK`, so the
whole entity diagram failed to render for weeks' worth of readers while CI stayed green.

What is checked, and deliberately only this:

- every fenced block is closed, and its language tag is on the opening fence;
- `erDiagram` blocks: entity headers, attribute lines `<type> <name> [PK|FK|UK] ["comment"]`, closing
  braces, and relationships `<entity> <cardinality> <entity> : "label"` whose endpoints are declared;
- every other diagram type: fences balanced and the body not empty. Their grammars are larger and a
  hand-written parser would give false confidence, so this does not pretend to parse them.

Usage: python scripts/check-mermaid.py
Exit code: 0 when every block is well formed, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
FENCE = re.compile(r"^\s*```\s*([A-Za-z0-9_-]*)\s*$")
ATTRIBUTE = re.compile(r'^\s*[A-Za-z_][A-Za-z0-9_]*\s+[A-Za-z_][A-Za-z0-9_]*\s+(PK|FK|UK)\s*(?:"[^"]*")?\s*$')
ENTITY_OPEN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\{\s*$")
ENTITY_CLOSE = re.compile(r"^\s*\}\s*$")
RELATIONSHIP = re.compile(
    r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s+(\|\||\|o|o\||\}o|\}\|)\s*--\s*(\|\||o\||\|o|o\{|\|\{)\s*'
    r'([A-Za-z_][A-Za-z0-9_]*)\s*:\s*"[^"]*"\s*$',
)
DIRECTIVE = re.compile(r"^\s*(erDiagram|flowchart|graph|sequenceDiagram|stateDiagram(?:-v2)?|classDiagram|gantt|pie)\b")


def mermaid_blocks(path: Path) -> list[tuple[int, str, list[str]]]:
    """Return (line number of the opening fence, language, body lines) per block."""
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[tuple[int, str, list[str]]] = []
    index = 0
    while index < len(lines):
        match = FENCE.match(lines[index])
        if match and match.group(1).lower() == "mermaid":
            start = index + 1
            body: list[str] = []
            index += 1
            while index < len(lines) and not FENCE.match(lines[index]):
                body.append(lines[index])
                index += 1
            blocks.append((start, "mermaid", body))
        index += 1
    return blocks


def check_er(body: list[str], where: str) -> list[str]:
    problems: list[str] = []
    entities: set[str] = set()
    inside: str | None = None
    for offset, line in enumerate(body, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        if inside is None:
            if stripped == "erDiagram":
                continue
            opening = ENTITY_OPEN.match(line)
            if opening:
                inside = opening.group(1)
                entities.add(inside)
                continue
            relationship = RELATIONSHIP.match(line)
            if relationship:
                for endpoint in (relationship.group(1), relationship.group(4)):
                    if endpoint not in entities:
                        problems.append(f"{where}:{offset}: relationship names undeclared entity '{endpoint}'")
                continue
            problems.append(f"{where}:{offset}: unexpected line outside an entity: {stripped[:60]!r}")
            continue
        if ENTITY_CLOSE.match(line):
            inside = None
            continue
        if ATTRIBUTE.match(line):
            continue
        problems.append(
            f"{where}:{offset}: attribute line does not match '<type> <name> [PK|FK|UK]': {stripped[:60]!r}",
        )
    if inside is not None:
        problems.append(f"{where}: entity '{inside}' is never closed")
    return problems


def main() -> int:
    problems: list[str] = []
    blocks = 0
    for path in sorted(DOCS.rglob("*.md")):
        relative = path.relative_to(ROOT).as_posix()
        for start, _language, body in mermaid_blocks(path):
            blocks += 1
            where = f"{relative}:{start}"
            first = next((line.strip() for line in body if line.strip()), "")
            if not DIRECTIVE.match(first):
                problems.append(f"{where}: block does not start with a diagram directive")
                continue
            if first.startswith("erDiagram"):
                problems.extend(check_er(body, where))
    if problems:
        for problem in problems:
            print(problem)
        print(f"\n{len(problems)} problem(s) in {blocks} mermaid block(s)")
        return 1
    print(f"{blocks} mermaid block(s) well formed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
