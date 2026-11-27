"""Run the live statistics view's rendering and data checks under Node."""

import shutil
import subprocess
from pathlib import Path


def test_statistics_views():
    node = shutil.which("node")
    assert node, "Node is required to verify the statistics views"
    subprocess.run([node, str(Path(__file__).with_name("stats_view.mjs"))], check=True, timeout=30)
