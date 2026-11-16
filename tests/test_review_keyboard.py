"""Run the review keyboard controls's behavioral assertions in Node."""

import shutil
import subprocess
from pathlib import Path


def test_review_keyboard():
    node = shutil.which("node")
    assert node, "Node is required to verify the review keyboard controls"
    subprocess.run(
        [node, str(Path(__file__).with_name("review_keyboard.mjs"))],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
