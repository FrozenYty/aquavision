#!/usr/bin/env python3
"""Arrival check for the USB camera: open it and find out whether exposure can be locked.

This is a thin entry point so the command written in the procurement document works from the
repository root. The check itself lives beside the capture code it validates:

    python scripts/test_exposure.py
    python scripts/test_exposure.py --index 1 --frames 30

Exit codes: 0 pass, 1 a check failed, 2 no camera attached.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The server package is not on the path when a script runs from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from app.vision.probe import main  # noqa: E402  (import follows the path setup on purpose)

if __name__ == "__main__":
    raise SystemExit(main())
