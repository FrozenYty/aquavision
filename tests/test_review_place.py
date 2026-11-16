"""Run the review navigation state's behavioral assertions in Node."""

import shutil
import subprocess
from pathlib import Path


def test_review_place():
    node = shutil.which("node")
    assert node, "Node is required to verify the review navigation state"
    subprocess.run(
        [node, str(Path(__file__).with_name("review_place.mjs"))],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
