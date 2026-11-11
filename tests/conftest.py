"""Test fixtures shared by the suite.

pytest's own temporary-directory machinery cannot be used here: it creates numbered directories
under the system temp root, and in this environment both the root and the per-test directories are
partly unreadable to the process. The fixture below replaces ``tmp_path`` with a plain directory
under ``tests/tmp``, which is inside the repository and therefore reliably writable.

It is a drop-in replacement: tests keep asking for ``tmp_path`` and get a fresh empty directory, and
a run leaves that directory gone. Removing it is not a one-line ``rmtree``: a test that opened a
SQLite database here still holds the file open when the fixture ends, and on Windows an open handle
makes the delete fail. The removal below closes what it can reach and retries the delete, and its last
attempt is unguarded - a directory that really cannot be removed fails the test instead of quietly
staying behind (which is how ``tests/tmp`` grew to thousands of directories).
"""

from __future__ import annotations

import gc
import shutil
import time
import uuid
from pathlib import Path

import pytest

TMP_ROOT = Path(__file__).resolve().parent / "tmp"

#: Delays between removal attempts. The first attempt is immediate; the rest give a pooled SQLite
#: connection that is still being garbage-collected a moment to close its file handle.
REMOVAL_BACKOFF = (0.0, 0.05, 0.2, 0.5)


@pytest.fixture
def tmp_path() -> Path:
    """A fresh empty directory, removed when the test ends."""
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    directory = TMP_ROOT / uuid.uuid4().hex[:12]
    directory.mkdir()
    try:
        yield directory
    finally:
        remove_tree(directory)


def dispose_engines_under(directory: Path) -> None:
    """Dispose every SQLAlchemy engine whose database file lives in ``directory``.

    The engine owns the SQLite handle, and the fixture cannot reach the engine a test built. A pool
    closes its connections when it is disposed or collected, not when the test's ``tmp_path`` goes
    away, so on Windows the file stays locked. Walking the live engines and disposing the ones
    pointed at this directory is what actually releases the handle.
    """
    from sqlalchemy.engine import Engine

    root = directory.resolve()
    for obj in gc.get_objects():
        if not isinstance(obj, Engine):
            continue
        database = obj.url.database
        if not database:
            continue
        try:
            path = Path(database).resolve()
        except OSError:  # an engine over a non-file URL cannot hold a file in this directory
            continue
        if path == root or root in path.parents:
            obj.dispose()


def remove_tree(directory: Path) -> None:
    """Remove a test directory, waiting for the test's SQLite handle to be closed first."""
    for pause in REMOVAL_BACKOFF:
        if pause:
            time.sleep(pause)
        try:
            shutil.rmtree(directory)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            # An open handle - almost always the test's SQLite pool. Dispose that engine directly;
            # a full garbage collection here would cost more than the retry saves, so it waits for
            # the last attempt below.
            dispose_engines_under(directory)
    # Nothing closed the handle in time. Collect once (the handle may belong to a pool whose engine
    # is already unreachable) and make the last attempt without ignore_errors, so a directory that
    # really cannot be removed fails the test instead of silently growing tests/tmp.
    gc.collect()
    shutil.rmtree(directory)
