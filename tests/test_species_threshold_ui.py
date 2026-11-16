"""Run the species threshold UI's behavioral assertions in Node."""

import shutil
import subprocess
from pathlib import Path


def test_species_threshold_ui():
    node = shutil.which("node")
    assert node, "Node is required to verify the species threshold UI"
    subprocess.run(
        [node, str(Path(__file__).with_name("species_thresholds.mjs"))],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
