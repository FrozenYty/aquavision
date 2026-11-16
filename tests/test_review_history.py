"""Run the review undo stack's behavioral assertions in Node."""

import shutil
import subprocess
from pathlib import Path


def test_review_history():
    node = shutil.which("node")
    assert node, "Node is required to verify the review undo stack"
    subprocess.run(
        [node, str(Path(__file__).with_name("review_history.mjs"))],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
