"""Test fixtures shared by the suite.

pytest's own temporary-directory machinery cannot be used here: it creates numbered directories
under the system temp root, and in this environment both the root and the per-test directories are
partly unreadable to the process. The fixture below replaces ``tmp_path`` with a plain directory
under ``tests/tmp``, which is inside the repository and therefore reliably writable.

It is a drop-in replacement: tests keep asking for ``tmp_path`` and get a fresh empty directory.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

TMP_ROOT = Path(__file__).resolve().parent / "tmp"


@pytest.fixture
def tmp_path() -> Path:
    """A fresh empty directory, removed when the test ends."""
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    directory = TMP_ROOT / uuid.uuid4().hex[:12]
    directory.mkdir()
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)
