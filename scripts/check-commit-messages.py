#!/usr/bin/env python3
"""Reject commits that credit a tool as a co-author.

A squash merge puts the single commit's message on `main` verbatim, so one
`Co-authored-by: Claude Code` line written locally ends up in the history of the shared branch, where
GitHub reads it as a second contributor. Removing it afterwards means rewriting `main` and making every
clone reset, which is a large cost for a stray line — so it is cheaper to refuse the line.

Checked in CI rather than only in a local hook: hooks are not installed by default, and the person who
needs the check most is the one who never installed it.

    python scripts/check-commit-messages.py                    # origin/main..HEAD
    python scripts/check-commit-messages.py --range a1b2c3..HEAD
    python scripts/check-commit-messages.py --all              # every commit reachable from HEAD
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

# Trailers that name a tool or model rather than a person. Matched case-insensitively on the whole
# line so both the standard spelling and variants such as "Generated with" are caught.
TOOL_PATTERNS = (
    re.compile(r"^\s*co-authored-by\s*:.*\b(claude|anthropic)\b", re.IGNORECASE),
    re.compile(r"^\s*co-authored-by\s*:.*\b(copilot|github copilot)\b", re.IGNORECASE),
    re.compile(r"^\s*co-authored-by\s*:.*\b(chatgpt|openai|gpt-\d)\b", re.IGNORECASE),
    re.compile(r"^\s*co-authored-by\s*:.*\b(cursor|codeium|windsurf)\b", re.IGNORECASE),
    re.compile(r"^\s*generated with\s*\[?", re.IGNORECASE),
)
# A human co-author is ordinary teamwork and is allowed: the subject of the rule is attribution to a
# tool, not collaboration. Only the patterns above are refused.


def git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # commit messages in this repository contain Chinese; never crash on them
            check=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        print(f"could not read git history: {error.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2) from error


def commits_in_range(rev_range: str) -> list[tuple[str, str]]:
    """(short hash, full message) for every commit in the range.

    One commit at a time rather than joining them with a separator: Windows refuses an argument
    containing a null character, and any printable separator can appear inside a commit message.
    """
    hashes = git("rev-list", rev_range).split()
    return [(h[:7], git("log", "-1", "--format=%B", h).rstrip("\n")) for h in hashes]


def offending_lines(message: str) -> list[str]:
    return [
        line
        for line in message.splitlines()
        if any(pattern.match(line) for pattern in TOOL_PATTERNS)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range", default="origin/main..HEAD", help="revision range to check")
    parser.add_argument("--all", action="store_true", help="check every commit reachable from HEAD")
    args = parser.parse_args(argv)

    rev_range = "HEAD" if args.all else args.range
    problems: list[str] = []
    checked = 0
    for short, message in commits_in_range(rev_range):
        checked += 1
        for line in offending_lines(message):
            problems.append(f"{short}: {line.strip()}")

    if problems:
        print("commits credit a tool as a co-author:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nRemove the trailer from the commit before merging. A squash merge copies it onto main,\n"
            "where GitHub counts it as a contributor, and clearing it afterwards means rewriting main.\n"
            "See CONTRIBUTING.md §2.",
            file=sys.stderr,
        )
        return 1

    print(f"{checked} commit(s) checked, no tool attribution found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
