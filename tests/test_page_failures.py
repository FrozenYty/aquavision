"""Run the page failure matrix's behavioral assertions in Node."""

import shutil
import subprocess
from pathlib import Path


def test_page_failure_matrix():
    node = shutil.which("node")
    assert node, "Node is required to verify the page failure matrix"
    subprocess.run(
        [node, str(Path(__file__).with_name("page_failures.mjs"))],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
