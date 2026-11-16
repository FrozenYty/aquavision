"""The presentation layer, held to its document cell by cell (rig-state-machine §11).

The machine is firmware, so this file cannot drive it: it reads the C++ table and the Markdown table and
compares them, the way `tests/test_wiring_document.py` holds the wiring document to `config.h`. Three
copies exist and all three are compared, because any two of them can drift together:

1. the contract - §11 of `docs/rig-state-machine-en.md`, and its `-zh` twin;
2. the implementation - the `kMatrix` and `kFaces` tables in `firmware/main/src/presentation.cpp`;
3. an independent transcription in this file, written from the same section.

The last part of the file checks the two things the tables alone cannot: that the renderer actually reads
the face table, and that a `Pairing` face is never shadowed by the rig's own screen - the rule that stops a
verdict painting over `WAITING`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC_EN = REPO / "docs" / "rig-state-machine-en.md"
DOC_ZH = REPO / "docs" / "rig-state-machine-zh.md"
PRESENTATION = REPO / "firmware" / "main" / "src" / "presentation.cpp"
SCREEN = REPO / "firmware" / "main" / "src" / "screen.cpp"
MAIN = REPO / "firmware" / "main" / "src" / "main.cpp"
PROTOCOL = REPO / "firmware" / "main" / "src" / "protocol.cpp"

STATES = ["Pairing", "Live", "RadioFault"]

#: §11's matrix, transcribed here from the document rather than from the code. A cell is a state name, or
#: one of `IGNORED`, `HANDLED` and `REJECTED`.
EXPECTED = {
    "Pairing": ["Live", "IGNORED", "IGNORED", "RadioFault", "IGNORED", "IGNORED"],
    "Live": ["REJECTED", "IGNORED", "Pairing", "RadioFault", "HANDLED", "HANDLED"],
    "RadioFault": ["IGNORED", "IGNORED", "IGNORED", "HANDLED", "IGNORED", "IGNORED"],
}

#: §11's face table: what each state draws on the OLED and on the seven-segment panel.
EXPECTED_FACES = {
    "Pairing": ("WaitingForPc", "Pairing"),
    "Live": ("RigScreen", "RigScreen"),
    "RadioFault": ("RadioFault", "Err4"),
}

#: The distinguishing text each face must contain in the document. Keyed by language because the two
#: documents are translations, not copies: the Chinese table says "装置自己的" where the English says
#: "the rig's own", and a check that quarrelled with the words would be switched off within a week.
FACE_WORDS_EN = {
    "Pairing": ("WAITING", "APP"),
    "Live": ("rig's own", "rig's own"),
    "RadioFault": ("RADIO FAULT", "Err4"),
}
FACE_WORDS_ZH = {
    "Pairing": ("WAITING", "APP"),
    "Live": ("装置自己的", "装置自己的"),
    "RadioFault": ("RADIO FAULT", "Err4"),
}

TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
SEPARATOR = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


def section(path: Path, heading: str) -> list[str]:
    """The lines of one `##` section, heading excluded, up to the next `##` heading."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(heading))
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    return lines[start + 1 : end]


def tables(body: list[str]) -> list[list[list[str]]]:
    """Every Markdown table in a section: a header row and its data rows, as stripped cells."""
    found: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in body:
        if not TABLE_ROW.match(line):
            if current:
                found.append(current)
                current = []
            continue
        if SEPARATOR.match(line):
            continue
        current.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    if current:
        found.append(current)
    return found


def canonical(cell: str) -> str:
    """One document cell in the shared vocabulary.

    `—` is ignored; `handled in place` and `already here` are both consumed without a move; `rejected`
    keeps the state and reports; anything else is the state the event moves to.
    """
    text = cell.replace("**", "").replace("`", "").strip()
    lowered = text.lower()
    if text in ("", "—", "-", "–"):
        return "IGNORED"
    if lowered in ("handled in place", "already here"):
        return "HANDLED"
    if lowered == "rejected":
        return "REJECTED"
    for state in STATES:
        if lowered == state.lower():
            return state
    raise AssertionError(f"cell {cell!r} is not one of the four kinds or a state")


def document_matrix(path: Path, heading: str) -> dict[str, list[str]]:
    """§11's matrix, read from the document rather than from the code."""
    for table in tables(section(path, heading)):
        if len(table[0]) == 7 and table[0][0].lower() in ("state \\ event", "状态 \\ 事件"):
            rows = {}
            for row in table[1:]:
                assert len(row) == 7, f"{path.name}: a matrix row has {len(row)} cells: {row}"
                rows[canonical(row[0])] = [canonical(cell) for cell in row[1:]]
            return rows
    raise AssertionError(f"{path.name} has no 7-column matrix in its section")


def document_faces(
    path: Path, heading: str, words: dict[str, tuple[str, str]]
) -> dict[str, tuple[str, str]]:
    """§11's face table, checked against the words the two screens actually draw."""
    for table in tables(section(path, heading)):
        if len(table[0]) == 3 and "OLED" in table[0][1]:
            faces = {}
            for row in table[1:]:
                state = canonical(row[0])
                oled_word, panel_word = words[state]
                assert oled_word in row[1], f"{path.name}: {state}'s OLED cell is {row[1]!r}"
                assert panel_word in row[2], f"{path.name}: {state}'s panel cell is {row[2]!r}"
                faces[state] = EXPECTED_FACES[state]
            return faces
    raise AssertionError(f"{path.name} has no face table in its section")


def matching(text: str, start: int) -> int:
    """The index of the `}` that closes the `{` at `start`."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise AssertionError("unbalanced braces in the table initializer")


def initializer(text: str, declaration: str) -> list[str]:
    """The top-level rows of a `constexpr ... name[rows][cols] = { ... };` table, braces stripped."""
    start = text.index(declaration)
    open_brace = text.index("{", text.index("=", start))
    body = text[open_brace + 1 : matching(text, open_brace)]
    rows: list[str] = []
    depth = 0
    row_start = 0
    for index, character in enumerate(body):
        if character == "{":
            if depth == 0:
                row_start = index
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                rows.append(body[row_start + 1 : index])
    return rows


def split_cells(row: str) -> list[str]:
    """The top-level cells of one row, so a `{Outcome::Rejected, State::Live}` cell stays whole."""
    cells: list[str] = []
    depth = 0
    cell_start = 0
    for index, character in enumerate(row):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        elif character == "," and depth == 0:
            cells.append(row[cell_start:index].strip())
            cell_start = index + 1
    cells.append(row[cell_start:].strip())
    return cells


def code_matrix() -> dict[str, list[str]]:
    """The implementation's `kMatrix`, with comments removed first."""
    text = re.sub(r"//[^\n]*", "", PRESENTATION.read_text(encoding="utf-8"))
    rows = initializer(text, "kMatrix[3][6]")
    assert len(rows) == 3, f"kMatrix has {len(rows)} rows, the document has 3"

    def cell(text: str) -> str:
        text = text.strip()
        if text == "kIgnored":
            return "IGNORED"
        if text == "kHandled":
            return "HANDLED"
        if text.startswith("kTo"):
            return text[len("kTo") :]
        if "Outcome::Rejected" in text:
            return "REJECTED"
        raise AssertionError(f"matrix cell {text!r} is not a known kind or a state")

    matrix = {}
    for state, row in zip(STATES, rows, strict=True):
        cells = split_cells(row)
        assert len(cells) == 6, f"a kMatrix row has {len(cells)} cells: {cells}"
        matrix[state] = [cell(value) for value in cells]
    return matrix


def code_faces() -> dict[str, tuple[str, str]]:
    """The implementation's `kFaces` table, as (OLED face, panel face) per state."""
    text = re.sub(r"//[^\n]*", "", PRESENTATION.read_text(encoding="utf-8"))
    rows = initializer(text, "kFaces[3]")
    assert len(rows) == 3, f"kFaces has {len(rows)} rows, the document has 3"

    def member(text: str) -> str:
        return text.strip().rsplit("::", 1)[-1]

    faces = {}
    for state, row in zip(STATES, rows, strict=True):
        cells = split_cells(row)
        assert len(cells) == 2, f"a kFaces row has {len(cells)} cells: {cells}"
        faces[state] = (member(cells[0]), member(cells[1]))
    return faces


# The matrix -------------------------------------------------------------------------------------


def test_the_code_matrix_is_the_document_matrix() -> None:
    """Every cell, in both directions: a cell the document moves and the code does not fails here."""
    assert code_matrix() == document_matrix(DOC_EN, "## 11.")


def test_the_code_matrix_is_the_contract_independently_transcribed() -> None:
    """The third copy: this file's transcription, so document and code cannot drift together."""
    assert code_matrix() == EXPECTED


def test_the_chinese_matrix_says_the_same_cells() -> None:
    """A translation that loses a cell is a second contract, not a translation."""
    assert document_matrix(DOC_ZH, "## 十一、") == EXPECTED


def test_every_cell_is_one_of_the_four_kinds() -> None:
    """3 states x 6 events, all filled: an unhandled pair is a cell nobody decided."""
    matrix = code_matrix()
    assert list(matrix) == STATES
    assert all(len(row) == 6 for row in matrix.values())
    allowed = set(STATES) | {"IGNORED", "HANDLED", "REJECTED"}
    assert {cell for row in matrix.values() for cell in row} <= allowed


def test_only_the_bold_cells_are_transitions() -> None:
    """The transitions the document bolds are transitions in the code, and the rest are not."""
    transitions = {
        (state, index)
        for state, row in code_matrix().items()
        for index, cell in enumerate(row)
        if cell in STATES
    }
    assert transitions == {
        ("Pairing", 0),
        ("Pairing", 3),
        ("Live", 2),
        ("Live", 3),
    }


# The faces --------------------------------------------------------------------------------------


def test_the_code_faces_are_the_document_faces() -> None:
    assert code_faces() == document_faces(DOC_EN, "## 11.", FACE_WORDS_EN)


def test_the_faces_are_the_contract_independently_transcribed() -> None:
    assert code_faces() == EXPECTED_FACES


def test_the_chinese_face_table_names_the_same_two_screens() -> None:
    assert document_faces(DOC_ZH, "## 十一、", FACE_WORDS_ZH) == EXPECTED_FACES


def test_the_three_faces_exist_in_the_drawing_code() -> None:
    """A table that names a face the renderer cannot draw is a table that has stopped being true."""
    drawing = SCREEN.read_text(encoding="utf-8")
    assert '"WAITING"' in drawing
    assert '"RADIO FAULT"' in drawing
    assert '"REFLASH RIG-SERIAL"' in drawing
    loop = MAIN.read_text(encoding="utf-8")
    assert "case '4':" in loop
    assert '"Err4"' in loop
    # The retired code is gone from the drawing code and stays absent from the panel masks.
    assert "Screen::Offline" not in loop and "Screen::Offline" not in drawing
    assert "PanelFace::Err0" not in loop
    assert "OledFace::Offline" not in drawing


# The rule the table alone cannot express --------------------------------------------------------


def test_pairing_cannot_paint_the_rig_screen() -> None:
    """A verdict cannot paint over `WAITING`, because `Pairing` never asks for the rig's screen."""
    assert EXPECTED_FACES["Pairing"][0] == "WaitingForPc"
    assert code_faces()["Pairing"][0] == "WaitingForPc"
    assert all(face[0] != "RigScreen" for state, face in code_faces().items() if state != "Live")
    # No *protocol* event out of `Pairing` lands on `Live`: only attaching hands the glass back.
    assert {index for index, target in enumerate(code_matrix()["Pairing"]) if target in STATES} == {
        0,
        3,
    }


def test_the_renderer_reads_the_face_table() -> None:
    """The drawing code must ask the presentation layer, not `state.screen`, what to paint."""
    drawing = SCREEN.read_text(encoding="utf-8")
    render_start = drawing.index("void render(U8G2& display")
    render = drawing[render_start : render_start + drawing[render_start:].index("\n}\n")]
    assert "presentation::faceFor(presentation)" in render
    assert "OledFace::WaitingForPc" in render
    assert render.index("OledFace::WaitingForPc") < render.index("switch (state.screen)")

    panel = MAIN.read_text(encoding="utf-8")
    assert "face.panel" in panel
    assert "PanelFace::Pairing" in panel
    assert "PanelFace::Err4" in panel


def test_the_presentation_layer_does_not_join_the_other_two() -> None:
    """It is a reader: it includes neither the wire nor the protocol, and neither includes it."""
    layer = PRESENTATION.read_text(encoding="utf-8")
    assert '#include "transport.h"' not in layer
    assert '#include "protocol.h"' not in layer
    for path in (
        REPO / "firmware" / "main" / "src" / "transport_ble.cpp",
        REPO / "firmware" / "main" / "src" / "transport.cpp",
        REPO / "firmware" / "main" / "src" / "protocol.cpp",
    ):
        assert "presentation::" not in path.read_text(encoding="utf-8"), (
            f"{path.name} knows about the presentation layer"
        )


def test_the_pairing_panel_is_the_word_and_the_rotation() -> None:
    """`APP` plus the fourth digit's six segments: no position table, so no entry can be wrong."""
    loop = MAIN.read_text(encoding="utf-8")
    start = loop.index("if (face.panel == presentation::PanelFace::Pairing) {")
    body = loop[start : loop.index("\n  }", start)]
    assert "segmentsFor('A')" in body
    assert body.count("segmentsFor('P')") == 2
    assert "1u << presentation::rotationStep(" in body
    # The ring and everything built on it is gone, not merely unused.
    for text in (
        loop,
        PRESENTATION.read_text(encoding="utf-8"),
        SCREEN.read_text(encoding="utf-8"),
    ):
        for stale in ("RING_DIGIT", "RING_SEGMENT", "DISPLAY_RING", "ringStep", "drawPairingRow"):
            assert stale not in text, f"the ring is still in the code: {stale}"


def test_the_rotation_has_six_distinct_segments() -> None:
    """The property the ring table failed: six positions, six distinct segments, no repeats."""
    config = (REPO / "firmware" / "main" / "src" / "config.h").read_text(encoding="utf-8")
    steps = int(re.search(r"constexpr uint8_t DISPLAY_ROTATE_STEPS = (\d+);", config).group(1))
    assert steps == 6, f"the fourth digit has {steps} rim segments, not six"
    segments = [1 << step for step in range(steps)]
    assert len(set(segments)) == steps, "a repeated segment is one position twice and one never lit"
    assert all(segment.bit_count() == 1 for segment in segments), "a step must light one segment"
    assert segments == sorted(segments), "one segment per step, in order"
    loop = MAIN.read_text(encoding="utf-8")
    assert loop.count("1u << presentation::rotationStep(") == 2, (
        "CAPTURING and Pairing must both derive their segment from the one step"
    )


def test_the_pairing_rotation_is_read_from_the_clock() -> None:
    """The step is `(faceAge / step) % steps`, never an accumulator: a late pass catches up."""
    layer = PRESENTATION.read_text(encoding="utf-8")
    assert "(faceAgeMs / cfg::DISPLAY_ROTATE_MS) % cfg::DISPLAY_ROTATE_STEPS" in layer
    start = layer.index("uint8_t rotationStep(uint32_t faceAgeMs) {")
    body = layer[start : layer.index("\n}\n", start)]
    assert "++" not in body and "+=" not in body, (
        "an accumulator loses a step when an iteration runs long"
    )
    loop = MAIN.read_text(encoding="utf-8")
    assert "presentation::rotationStep(faceAgeAt(now, screenAge))" in loop
    assert "presentation::rotationStep(faceAge)" in loop


def test_the_heartbeat_does_not_redraw_a_link_face() -> None:
    """The header dot exists only on the rig's own screen; elsewhere a 1 Hz full frame is waste."""
    loop = MAIN.read_text(encoding="utf-8")
    start = loop.index("void serviceHeartbeat(")
    body = loop[start : loop.index("\n}\n", start)]
    assert "presentation::state() == presentation::State::Live" in body, (
        "`Pairing` draws no header dot, so its heartbeat must not repaint the frame"
    )
    assert "state.markDirty();" in body


def test_the_waiting_face_is_the_house_face_without_animation() -> None:
    """Same box, same header, same body, no moving element."""
    drawing = SCREEN.read_text(encoding="utf-8")
    start = drawing.index("void drawWaitingForPc(")
    body = drawing[start : start + drawing[start:].index("\n}\n")]
    assert "drawStatusFace(" in body and '"WAITING"' in body
    for animated in ("drawDisc", "drawCircle", "drawFrame", "drawBox"):
        assert animated not in body, f"the waiting face still animates with {animated}"

    # The house face is one function; `RADIO FAULT` and `WAITING` are its two calls.
    for face in ("drawRadioFault", "drawWaitingForPc"):
        call = drawing[drawing.index(f"void {face}(") :]
        call = call[: call.index("\n}\n")]
        assert "drawStatusFace(" in call, f"{face} invented its own layout"
    assert "updateDisplayArea" not in drawing, "no partial tile update may exist"
    assert "renderRingStep" not in drawing


def test_the_oled_path_never_touches_the_panel() -> None:
    """The panel publishes its mask from `serviceDisplay`; the OLED module must not reach into it."""
    drawing = SCREEN.read_text(encoding="utf-8")
    for forbidden in ("displayMask", "displayMasks", "portENTER_CRITICAL"):
        assert forbidden not in drawing, f"the OLED path reached into the panel: {forbidden}"
    loop = MAIN.read_text(encoding="utf-8")
    assert "displayMasks[d] = mask[d];" in loop, "the panel mask is still published by the loop"


def test_the_waiting_title_is_the_house_size_and_the_body_carries_the_rest() -> None:
    """The character count was the cause, not the font: a short title keeps the one house size."""
    drawing = SCREEN.read_text(encoding="utf-8")
    start = drawing.index("//: `Pairing`:")
    body = drawing[start : start + drawing[start:].index("\n}\n")]
    assert '"WAITING"' in body, "the title must be the short word, not a sentence"
    assert "drawStatusFace(" in body

    # One face, one title size, no per-face font: every headline is short enough for bold 12.
    status = drawing[drawing.index("void drawStatusFace(") :]
    status = status[: status.index("\n}\n")]
    assert "u8g2_font_helvB12_tr" in status
    assert "u8g2_font_helvB08_tr" not in drawing, (
        "a shrunken title is what made the face look empty"
    )
    for headline in re.findall(r'drawStatusFace\(display, "([^"]+)"', drawing):
        assert len(headline) <= len("RADIO FAULT"), f"{headline!r} is too long for the house size"

    # The waiting body still says what is missing, because the title is only `WAITING`.
    line = 'cfg::BLE_CARRIER ? "NO LINK TO PC" : "CHECK USB CABLE"'
    call = drawing[drawing.index("void drawWaitingForPc(") :]
    call = call[: call.index("\n}\n")]
    assert line in call, "the body line has to carry the `NO LINK` half of the message"


# The two rules the bench found, kept as checks on the code that implements them --------------------


def test_a_capture_cancels_the_previous_verdict_timer() -> None:
    """`CAP` must not be pulled back to `READY` by the verdict face timer of the shot before it."""
    loop = MAIN.read_text(encoding="utf-8")
    start = loop.index("void serviceButton(")
    body = loop[start : loop.index("\n}\n", start)]
    assert "state.verdictAt = 0;" in body, (
        "starting a capture must disarm the previous verdict's face timer"
    )
    assert body.index("state.verdictAt = 0;") > body.index("state.screen = rig::Screen::Capturing;")

    timeout = loop[loop.index("void serviceVerdictTimeout(") :]
    timeout = timeout[: timeout.index("\n}\n")]
    assert "rig::verdictFaceExpired(" in timeout, (
        "the window has to come from the shared predicate, which refuses an unarmed timer too"
    )
    assert "cfg::VERDICT_FACE_MS" in timeout


def test_the_verdict_face_is_stamped_with_the_loops_clock() -> None:
    """One event, one clock. A second `millis()` here is the flashback: the stamp lands one millisecond
    past the loop's reading, the unsigned age wraps, and the face expires the instant it appears."""
    parser = PROTOCOL.read_text(encoding="utf-8")
    code = re.sub(r"//[^\n]*", "", parser)
    assert "millis()" not in code, (
        "the parser must take the loop's clock reading, not a second one of its own"
    )
    assert "rig::armVerdictFace(state, now)" in parser
    assert "bool poll(rig::State& state, uint32_t now)" in parser
    assert "handleResult(state, &cursor, now)" in parser
    # And the expiry, which is the only reader that matters, is the shared predicate.
    state = (REPO / "firmware" / "main" / "src" / "rig_state.h").read_text(encoding="utf-8")
    assert "inline void armVerdictFace(State& state, uint32_t now)" in state
    assert "static_cast<int32_t>(now - verdictAt)" in state, (
        "a signed age, so a stamp a millisecond ahead cannot invert the comparison"
    )


def test_nothing_else_writes_the_verdict_timer() -> None:
    """Set when a verdict arrives, cleared when a capture starts, written by nothing else."""
    writers: list[str] = []
    for rel in ("firmware/main/src/main.cpp", "firmware/main/src/protocol.cpp"):
        for line in (REPO / rel).read_text(encoding="utf-8").splitlines():
            code = line.split("//")[0].strip()
            if "verdictAt =" in code:
                writers.append(f"{rel}: {code}")
    assert writers == ["firmware/main/src/main.cpp: state.verdictAt = 0;"], (
        f"the verdict timer has more writers than the capture-start clear: {writers}"
    )
    # The stamp itself lives in the one helper, and both arming sites go through it.
    loop = MAIN.read_text(encoding="utf-8")
    assert loop.count("rig::armVerdictFace(state, now)") == 1
    assert "state.verdictAt = now;" not in loop
    parser = PROTOCOL.read_text(encoding="utf-8")
    assert parser.count("rig::armVerdictFace(state, now)") == 1


def test_live_is_a_subscriber_listening_not_an_attachment() -> None:
    """`Live` and the button must be the same condition, and that condition is `Streaming`."""
    ble = (REPO / "firmware" / "main" / "src" / "transport_ble.cpp").read_text(encoding="utf-8")
    listening = ble[ble.index("bool listening()") :]
    listening = listening[: listening.index("\n}\n")]
    assert "State::Streaming" in listening, "`Live` must key on the subscriber, not the connection"
    assert "State::Connected" not in listening, (
        "an attached central that has not subscribed cannot hear EVT TRIGGER"
    )

    loop = MAIN.read_text(encoding="utf-8")
    presentation_service = loop[loop.index("void servicePresentation(") :]
    presentation_service = presentation_service[: presentation_service.index("\n}\n")]
    assert "transport::listening()" in presentation_service
    assert "transport::attached()" not in loop, "the old attachment fact must be gone"
    assert "presentation::begin(transport::listening());" in loop

    # And the press reads the same state the face table is indexed by - one condition, not two.
    button = loop[loop.index("void serviceButton(") :]
    button = button[: button.index("\n}\n")]
    assert "presentation::state() != presentation::State::Live" in button


def test_a_new_subscription_flushes_the_input() -> None:
    """A half-received line must not be completed by the next session's first write."""
    ble = (REPO / "firmware" / "main" / "src" / "transport_ble.cpp").read_text(encoding="utf-8")
    assert "transport::flushRx();" in ble, "the carrier must drop its rx ring on subscribe"
    assert "Event::Subscribe" in ble

    parser = PROTOCOL.read_text(encoding="utf-8")
    flush = parser[parser.index("void flushInput()") :]
    flush = flush[: flush.index("\n}\n")]
    assert "length = 0;" in flush, "the parser must drop a partial line"

    loop = MAIN.read_text(encoding="utf-8")
    subscribed = loop[loop.index("if (transport::subscribed())") :]
    assert "protocol::flushInput();" in subscribed[: subscribed.index("\n  }")]


def test_the_radio_fault_owns_the_blink_clock() -> None:
    """One writer for (fault, faultAt), and `Err4` outranks: a later fault must not restart its blink."""
    for rel in ("firmware/main/src/main.cpp", "firmware/main/src/protocol.cpp"):
        code = re.sub(r"//[^\n]*", "", (REPO / rel).read_text(encoding="utf-8"))
        assert "faultAt =" not in code, f"{rel} writes faultAt outside the one helper"
        assert "fault = rig::Fault::" not in code, f"{rel} writes fault outside the one helper"
    state = (REPO / "firmware" / "main" / "src" / "rig_state.h").read_text(encoding="utf-8")
    raise_fault = state[state.index("inline void raiseFault(") :]
    raise_fault = raise_fault[: raise_fault.index("\n}\n")]
    assert "state.fault == Fault::Radio && fault != Fault::Radio" in raise_fault, (
        "a dead radio must keep its stamp against every later fault"
    )


def test_a_press_captures_in_live_and_is_refused_only_by_the_faces() -> None:
    """`Gone` is an attached, quiet peer: a press there captures and reports `Err1` if it stays silent."""
    loop = MAIN.read_text(encoding="utf-8")
    start = loop.index("void serviceButton(")
    body = loop[start : loop.index("\n}\n", start)]
    assert "state.link" not in body, "the button must not consult the protocol layer's Gone flag"
    assert "presentation::state() != presentation::State::Live" in body, (
        "only a face that owns the screens may refuse the press"
    )
    # The refusal covers `Pairing` and `RadioFault`; `Live` always captures.
    assert "presentation::State::Live" in body
