"""The presentation machine, run on the host, not read from its source.

`tests/test_rig_presentation.py` compares the matrix in `presentation.cpp` with the document and with an
independent transcription. That catches a wrong cell, but not a wrong **lookup**: a table that is right
and is read with the indices swapped still passes a text comparison. So this file compiles the real
translation unit for the host with a minimal harness - `presentation.cpp` includes only `presentation.h`
and `config.h`, no Arduino - and drives every cell and every face through the code that runs on the rig.

The compiler is the host's; the test skips, with the reason, on a machine that has none. CI's Ubuntu
runner has `g++`, so the check runs where it matters.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "firmware" / "main" / "src"

STATES = ["Pairing", "NoLink", "Live", "RadioFault"]
EVENTS = ["Attached", "Subscribed", "Detached", "RadioFaulted", "Command", "Silence"]

#: The same independent transcription the source-level test carries.
EXPECTED = {
    "Pairing": ["NoLink", "IGNORED", "IGNORED", "RadioFault", "IGNORED", "IGNORED"],
    "NoLink": ["IGNORED", "Live", "Pairing", "RadioFault", "Live", "HANDLED"],
    "Live": ["REJECTED", "IGNORED", "Pairing", "RadioFault", "HANDLED", "NoLink"],
    "RadioFault": ["IGNORED", "IGNORED", "IGNORED", "HANDLED", "IGNORED", "IGNORED"],
}

EXPECTED_FACES = {
    "Pairing": ("WaitingForPc", "Pairing"),
    "NoLink": ("Offline", "Err0"),
    "Live": ("RigScreen", "RigScreen"),
    "RadioFault": ("RadioFault", "Err4"),
}

OLED = ["WaitingForPc", "Offline", "RigScreen", "RadioFault"]
PANEL = ["Pairing", "Err0", "RigScreen", "Err4"]

HARNESS = r"""
#include <cstdint>
#include <cstdio>

#include "config.h"
#include "presentation.h"

using presentation::Cell;
using presentation::Event;
using presentation::Outcome;
using presentation::State;

static const Event kEvents[] = {Event::Attached, Event::Subscribed, Event::Detached,
                                Event::RadioFaulted, Event::Command, Event::Silence};
static const char* kEventNames[] = {"Attached", "Subscribed", "Detached", "RadioFaulted",
                                    "Command", "Silence"};
static const State kStates[] = {State::Pairing, State::NoLink, State::Live, State::RadioFault};
static const char* kStateNames[] = {"Pairing", "NoLink", "Live", "RadioFault"};

// Enter a state through the machine's own entry points, so a state the harness cannot reach is a
// failure rather than a silently skipped row.
static void setState(State state) {
  switch (state) {
    case State::Pairing:
      presentation::begin(false, false);
      break;
    case State::NoLink:
      presentation::begin(true, false);
      break;
    case State::Live:
      presentation::begin(true, true);
      break;
    case State::RadioFault:
      presentation::begin(false, false);
      presentation::apply(Event::RadioFaulted);
      break;
  }
}

static const char* outcomeName(Outcome outcome) {
  switch (outcome) {
    case Outcome::Move:
      return "MOVE";
    case Outcome::Handled:
      return "HANDLED";
    case Outcome::Ignored:
      return "IGNORED";
    case Outcome::Rejected:
      return "REJECTED";
  }
  return "?";
}

int main() {
  for (unsigned s = 0; s < 4; ++s) {
    for (unsigned e = 0; e < 6; ++e) {
      setState(kStates[s]);
      const Cell cell = presentation::apply(kEvents[e]);
      const char* target = "-";
      if (cell.outcome == Outcome::Move || cell.outcome == Outcome::Rejected) {
        for (unsigned t = 0; t < 4; ++t) {
          if (kStates[t] == cell.target) {
            target = kStateNames[t];
          }
        }
      }
      printf("cell %s %s %s %s\n", kStateNames[s], kEventNames[e], outcomeName(cell.outcome),
             target);
    }
  }
  for (unsigned s = 0; s < 4; ++s) {
    const presentation::Face& face = presentation::faceFor(static_cast<State>(s));
    printf("face %s %u %u\n", kStateNames[s], static_cast<unsigned>(face.oled),
           static_cast<unsigned>(face.panel));
  }
  printf("rotate %u\n", static_cast<unsigned>(cfg::DISPLAY_ROTATE_MS));
  printf("steps %u\n", static_cast<unsigned>(cfg::DISPLAY_ROTATE_STEPS));
  for (unsigned k = 0; k < 8; ++k) {
    const unsigned age = k * cfg::DISPLAY_ROTATE_MS;
    printf("rotation %u %u\n", age, static_cast<unsigned>(presentation::rotationStep(age)));
  }
  return 0;
}
"""


def compiler() -> str | None:
    """The host C++ compiler, or None. Resolved through the shell's PATH, as a person would."""
    return shutil.which("g++") or shutil.which("clang++")


def run_harness(tmp_path: Path) -> list[str]:
    """Compile the real translation unit plus the harness, run it, return its lines."""
    cc = compiler()
    if cc is None:
        pytest.skip("no host C++ compiler (g++ or clang++) on this machine")

    harness = tmp_path / "harness.cpp"
    harness.write_text(HARNESS, encoding="utf-8")
    binary = tmp_path / ("harness.exe" if sys.platform == "win32" else "harness")
    build = tmp_path / "build.log"
    with build.open("w", encoding="utf-8") as log:
        built = subprocess.run(
            [
                cc,
                "-std=c++17",
                "-O0",
                "-Wall",
                "-Wextra",
                "-I",
                str(SRC),
                str(SRC / "presentation.cpp"),
                str(harness),
                "-o",
                str(binary),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=False,
        )
    assert built.returncode == 0, f"the harness did not compile:\n{build.read_text()}"

    output = tmp_path / "run.txt"
    with output.open("w", encoding="utf-8") as log:
        ran = subprocess.run(
            [str(binary)], stdout=log, stderr=subprocess.STDOUT, timeout=30, check=False
        )
    assert ran.returncode == 0, f"the harness did not run:\n{output.read_text()}"
    return output.read_text(encoding="utf-8").splitlines()


def cells(lines: list[str]) -> dict[tuple[str, str], tuple[str, str]]:
    found = {}
    for line in lines:
        if not line.startswith("cell "):
            continue
        _, state, event, outcome, target = line.split()
        found[(state, event)] = (outcome, target)
    return found


def expected_cell(state: str, event_index: int) -> tuple[str, str]:
    cell = EXPECTED[state][event_index]
    if cell in STATES:
        return ("MOVE", cell)
    if cell == "REJECTED":
        return ("REJECTED", state)
    return (cell, "-")


def test_the_real_machine_moves_every_cell_as_the_matrix_says(tmp_path: Path) -> None:
    """4 x 6, driven through `apply()` itself - a table read with the wrong indices fails here."""
    found = cells(run_harness(tmp_path))
    assert len(found) == 24, f"the harness reported {len(found)} cells, not 24"
    for state in STATES:
        for index, event in enumerate(EVENTS):
            assert found[(state, event)] == expected_cell(state, index), (
                f"{state} x {event}: the machine did {found[(state, event)]}"
            )


def test_the_real_machine_reports_the_four_faces(tmp_path: Path) -> None:
    """The face table through `faceFor()`, so a swapped row cannot hide behind a correct document."""
    faces = {}
    for line in run_harness(tmp_path):
        if not line.startswith("face "):
            continue
        _, state, oled, panel = line.split()
        faces[state] = (OLED[int(oled)], PANEL[int(panel)])
    assert faces == EXPECTED_FACES


def test_the_rotation_is_six_distinct_steps_on_the_clock(tmp_path: Path) -> None:
    """Six positions, six distinct segments, and the step read from the age - the property the ring table
    failed: a copied table can agree with itself, so this asserts the definition instead."""
    lines = run_harness(tmp_path)
    rotate = next(int(line.split()[1]) for line in lines if line.startswith("rotate "))
    steps = next(int(line.split()[1]) for line in lines if line.startswith("steps "))
    rotations = {
        int(parts[1]): int(parts[2])
        for parts in (line.split() for line in lines)
        if parts[0] == "rotation"
    }
    assert steps == 6, f"the fourth digit has {steps} rim segments, not six"
    sequence = [rotations[k * rotate] for k in range(8)]
    assert sequence[:steps] == list(range(steps)), (
        f"one lap is {sequence[:steps]}, not six distinct steps"
    )
    assert len(set(sequence[:steps])) == steps, (
        "a repeated step is a segment twice and one never lit"
    )
    assert sequence[steps] == 0, "the lap must wrap to the first segment"
    assert sequence[steps + 1] == 1, "an age one step late must read the current step, not drift"
