"""The review canvas's geometry, run for real: web/static/js/canvas.js under Node.

Coordinate conversion is where a zoomable canvas usually goes wrong - a click lands beside the pointer,
a dragged box drifts - so it is one pure function, and these tests call it instead of reading it.
The page side is held too: review.html must take its coordinates from that function and must not zoom
with a CSS transform (PLAN P3-05).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = ROOT / "web" / "static" / "js" / "canvas.js"
REVIEW = ROOT / "web" / "templates" / "review.html"

NODE = shutil.which("node")
# Locally a missing Node skips; in CI it fails, so the checks can never pass by being skipped there.
if NODE is None and os.environ.get("CI"):
    pytest.fail("Node is required in CI to run tests/test_review_canvas.py", pytrace=False)
needs_node = pytest.mark.skipif(NODE is None, reason="Node is not installed")


def call(fn: str, *args):
    script = (
        f"import * as m from {json.dumps(CANVAS_JS.as_uri())};"
        f"console.log(JSON.stringify(m.{fn}(...{json.dumps(list(args))})));"
    )
    out = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(out.stdout)


def close(a: dict, b: dict) -> bool:
    return a.keys() == b.keys() and all(abs(a[k] - b[k]) < 1e-9 for k in a)


# A 800x450 picture whose top-left corner is at client (100, 50).
RECT = {"left": 100, "top": 50, "width": 800, "height": 450}


@needs_node
def test_corners_and_centre_map_to_normalised_coordinates():
    assert close(call("toImageCoords", 100, 50, RECT), {"x": 0, "y": 0})
    assert close(call("toImageCoords", 900, 500, RECT), {"x": 1, "y": 1})
    assert close(call("toImageCoords", 500, 275, RECT), {"x": 0.5, "y": 0.5})


@needs_node
def test_the_same_image_point_survives_zoom_and_scroll():
    # At 400% the stage is four times as large, and scrolling moves its left/top off-screen.
    # The point a quarter in and a third down is still the same image point.
    zoomed = {"left": 100 - 1234, "top": 50 - 567, "width": 3200, "height": 1800}
    x = zoomed["left"] + 0.25 * zoomed["width"]
    y = zoomed["top"] + (1 / 3) * zoomed["height"]
    assert close(call("toImageCoords", x, y, zoomed), {"x": 0.25, "y": 1 / 3})


@needs_node
def test_a_pointer_outside_the_picture_is_clamped_to_its_edge():
    assert close(call("toImageCoords", 0, 0, RECT), {"x": 0, "y": 0})
    assert close(call("toImageCoords", 5000, 5000, RECT), {"x": 1, "y": 1})


@needs_node
def test_a_stage_with_no_size_yet_gives_no_coordinates():
    # The picture has not loaded: a click must be ignored, not turned into NaN.
    assert call("toImageCoords", 10, 10, {"left": 0, "top": 0, "width": 0, "height": 0}) is None
    assert call("toImageCoords", 10, 10, None) is None


@needs_node
def test_zoom_steps_up_and_down_and_stops_at_both_ends():
    assert call("nextZoom", 1, 1) == 1.5
    assert call("nextZoom", 1, -1) == 0.75
    assert call("nextZoom", 4, 1) == 4
    assert call("nextZoom", 0.5, -1) == 0.5
    assert call("nextZoom", 1.2, 1) == 1.5  # between steps: up goes to the next one
    assert call("nextZoom", 1.2, -1) == 1


@needs_node
def test_a_moved_box_stops_at_the_edge_instead_of_leaving_the_picture():
    box = {"x": 0.7, "y": 0.1, "w": 0.2, "h": 0.3}
    assert close(call("moveBox", box, 0.5, -0.5), {"x": 0.8, "y": 0, "w": 0.2, "h": 0.3})
    assert close(call("moveBox", box, -2, 2), {"x": 0, "y": 0.7, "w": 0.2, "h": 0.3})


@needs_node
def test_a_resized_box_is_clamped_and_flips_past_the_opposite_corner():
    box = {"x": 0.6, "y": 0.6, "w": 0.2, "h": 0.2}
    assert close(call("resizeBox", box, "se", 0.5, 0.5), {"x": 0.6, "y": 0.6, "w": 0.4, "h": 0.4})
    assert close(call("resizeBox", box, "nw", -1, -1), {"x": 0, "y": 0, "w": 0.8, "h": 0.8})
    # Dragging the right edge past the left one flips the box rather than giving it a negative width.
    assert close(call("resizeBox", box, "ne", -0.3, 0), {"x": 0.5, "y": 0.6, "w": 0.1, "h": 0.2})


@needs_node
def test_a_drawn_box_works_in_any_direction():
    assert close(
        call("drawBox", {"x": 0.5, "y": 0.5}, {"x": 0.2, "y": 0.9}),
        {"x": 0.2, "y": 0.5, "w": 0.3, "h": 0.4},
    )


@needs_node
def test_zooming_keeps_the_point_under_the_pointer():
    after = {"left": 100, "top": 50, "width": 1600, "height": 900}
    # The pointer is at the picture's centre; after a 2x zoom that point is 400px right and 225px down
    # of the pointer, so the viewport scrolls by exactly that much.
    assert close(call("anchorScroll", 500, 275, RECT, after), {"dx": 400, "dy": 225})


def test_the_review_page_takes_its_coordinates_from_the_pure_function():
    page = REVIEW.read_text(encoding="utf-8")
    assert "toImageCoords(" in page, "review.html must convert pointer positions with toImageCoords"
    assert "getBoundingClientRect" in page
    assert "transform" not in page, "zoom must resize the stage, never apply a CSS transform"
