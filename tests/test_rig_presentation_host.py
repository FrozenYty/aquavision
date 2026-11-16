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

STATES = ["Pairing", "Live", "RadioFault"]
EVENTS = ["Attached", "Subscribed", "Detached", "RadioFaulted", "Command", "Silence"]

#: The same independent transcription the source-level test carries.
EXPECTED = {
    "Pairing": ["Live", "IGNORED", "IGNORED", "RadioFault", "IGNORED", "IGNORED"],
    "Live": ["REJECTED", "IGNORED", "Pairing", "RadioFault", "HANDLED", "HANDLED"],
    "RadioFault": ["IGNORED", "IGNORED", "IGNORED", "HANDLED", "IGNORED", "IGNORED"],
}

EXPECTED_FACES = {
    "Pairing": ("WaitingForPc", "Pairing"),
    "Live": ("RigScreen", "RigScreen"),
    "RadioFault": ("RadioFault", "Err4"),
}

OLED = ["WaitingForPc", "RigScreen", "RadioFault"]
PANEL = ["Pairing", "RigScreen", "Err4"]

HARNESS = r"""
#include <cstdint>
#include <cstdio>

#include "config.h"
#include "presentation.h"
#include "rig_state.h"

using presentation::Cell;
using presentation::Event;
using presentation::Outcome;
using presentation::State;

static const Event kEvents[] = {Event::Attached, Event::Subscribed, Event::Detached,
                                Event::RadioFaulted, Event::Command, Event::Silence};
static const char* kEventNames[] = {"Attached", "Subscribed", "Detached", "RadioFaulted",
                                    "Command", "Silence"};
static const State kStates[] = {State::Pairing, State::Live, State::RadioFault};
static const char* kStateNames[] = {"Pairing", "Live", "RadioFault"};

// Enter a state through the machine's own entry points, so a state the harness cannot reach is a
// failure rather than a silently skipped row.
static void setState(State state) {
  switch (state) {
    case State::Pairing:
      presentation::begin(false);
      break;
    case State::Live:
      presentation::begin(true);
      break;
    case State::RadioFault:
      presentation::begin(false);
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
  for (unsigned s = 0; s < 3; ++s) {
    for (unsigned e = 0; e < 6; ++e) {
      setState(kStates[s]);
      const Cell cell = presentation::apply(kEvents[e]);
      const char* target = "-";
      if (cell.outcome == Outcome::Move || cell.outcome == Outcome::Rejected) {
        for (unsigned t = 0; t < 3; ++t) {
          if (kStates[t] == cell.target) {
            target = kStateNames[t];
          }
        }
      }
      printf("cell %s %s %s %s\n", kStateNames[s], kEventNames[e], outcomeName(cell.outcome),
             target);
    }
  }
  for (unsigned s = 0; s < 3; ++s) {
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
  // The invariant, through the real predicate: a capture in flight must not carry a verdict timer.
  const rig::Screen screens[] = {rig::Screen::Ready, rig::Screen::Capturing, rig::Screen::Pass,
                                 rig::Screen::Retake};
  const char* screenNames[] = {"Ready", "Capturing", "Pass", "Retake"};
  for (unsigned s = 0; s < 4; ++s) {
    for (unsigned armed = 0; armed < 2; ++armed) {
      rig::State sample;
      sample.screen = screens[s];
      sample.verdictAt = armed ? 1000u : 0u;
      printf("invariant %s %u %u\n", screenNames[s], armed,
             static_cast<unsigned>(rig::invariantHolds(sample)));
    }
  }

  // The face's lifetime, measured on a virtual clock through the real predicate. The bench saw a face
  // that lived about 1.4 s instead of 12 s; these lines state what the code actually does.
  const uint32_t t0 = 100000u;
  rig::State face;
  face.screen = rig::Screen::Pass;
  rig::armVerdictFace(face, t0);
  unsigned lifetime = 0;
  while (lifetime <= 20000u &&
         !rig::verdictFaceExpired(t0 + lifetime, face.verdictAt, cfg::VERDICT_FACE_MS)) {
    ++lifetime;
  }
  printf("lifetime same-clock %u\n", lifetime);

  // The old shape: a second clock reading, one millisecond after the loop took `now`.
  face.verdictAt = t0 + 1u;
  lifetime = 0;
  while (lifetime <= 20000u &&
         !rig::verdictFaceExpired(t0 + lifetime, face.verdictAt, cfg::VERDICT_FACE_MS)) {
    ++lifetime;
  }
  printf("lifetime one-ms-ahead %u\n", lifetime);

  // An unarmed face never expires, however far the clock runs.
  face.verdictAt = 0u;
  lifetime = 0;
  while (lifetime <= 20000u &&
         !rig::verdictFaceExpired(t0 + lifetime, face.verdictAt, cfg::VERDICT_FACE_MS)) {
    ++lifetime;
  }
  printf("lifetime unarmed %d\n", lifetime > 20000u ? -1 : static_cast<int>(lifetime));

  // The two readings the operator's complaint names: still up at eleven seconds, gone by thirteen.
  printf("edge 11000 %u\n",
         static_cast<unsigned>(rig::verdictFaceExpired(t0 + 11000u, t0, cfg::VERDICT_FACE_MS)));
  printf("edge 13000 %u\n",
         static_cast<unsigned>(rig::verdictFaceExpired(t0 + 13000u, t0, cfg::VERDICT_FACE_MS)));
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
    """3 x 6, driven through `apply()` itself - a table read with the wrong indices fails here."""
    found = cells(run_harness(tmp_path))
    assert len(found) == 18, f"the harness reported {len(found)} cells, not 18"
    for state in STATES:
        for index, event in enumerate(EVENTS):
            assert found[(state, event)] == expected_cell(state, index), (
                f"{state} x {event}: the machine did {found[(state, event)]}"
            )


def test_the_real_machine_reports_the_three_faces(tmp_path: Path) -> None:
    """The face table through `faceFor()`, so a swapped row cannot hide behind a correct document."""
    faces = {}
    for line in run_harness(tmp_path):
        if not line.startswith("face "):
            continue
        _, state, oled, panel = line.split()
        faces[state] = (OLED[int(oled)], PANEL[int(panel)])
    assert faces == EXPECTED_FACES


def test_the_real_invariant_catches_an_armed_capture_timer(tmp_path: Path) -> None:
    """The flash's signature: a capture in flight with the previous verdict's timer still armed."""
    lines = run_harness(tmp_path)
    held = {
        (parts[1], parts[2] == "1"): parts[3] == "1"
        for parts in (line.split() for line in lines)
        if parts[0] == "invariant"
    }
    assert held[("Capturing", False)] is True, (
        "a capture with no verdict timer is the healthy state"
    )
    assert held[("Capturing", True)] is False, (
        "an armed verdict timer during a capture is the bug the bench saw"
    )
    assert held[("Pass", True)] is True, "a verdict face must carry its timer"
    assert held[("Pass", False)] is False, "a verdict face with no timer would never expire"
    assert held[("Retake", True)] is True and held[("Retake", False)] is False


def test_the_verdict_face_lives_twelve_seconds_on_the_loop_clock(tmp_path: Path) -> None:
    """Measured on a virtual clock through the real predicate, not asserted at the boundary.

    The bench measured about 1 434 ms between one trigger and the next and read the face as dying in
    that time; the face the operator is promised is `cfg::VERDICT_FACE_MS`, twelve seconds. The second
    case is the defect's own shape: a verdict stamped with a second clock reading, one millisecond past
    the loop's. An unsigned age then wraps to 4 294 967 295 and the face expires on the pass it appears.
    """
    lines = run_harness(tmp_path)
    measured = {
        parts[1]: int(parts[2])
        for parts in (line.split() for line in lines)
        if parts[0] == "lifetime"
    }
    assert measured["same-clock"] == 12000, (
        f"the verdict face measured {measured['same-clock']} ms, not 12 000"
    )
    # A stamp one millisecond ahead is the old shape. It costs one millisecond, not the whole face: the
    # unsigned version measured 0 ms, which is the flashback.
    assert 12000 <= measured["one-ms-ahead"] <= 12001, (
        "a stamp one millisecond past the loop's reading wrapped the age and the face measured "
        f"{measured['one-ms-ahead']} ms instead of about 12 000"
    )
    assert measured["unarmed"] == -1, "an unarmed face must never expire on its own"

    edges = {
        int(parts[1]): parts[2] == "1"
        for parts in (line.split() for line in lines)
        if parts[0] == "edge"
    }
    assert edges[11000] is False, "the face must still be up at eleven seconds"
    assert edges[13000] is True, "the face must be gone by thirteen seconds"


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
