"""Draw the rig wiring diagram: one page a person can wire from at the bench.

Not a mechanical drawing. Boxes are on a grid with gaps, so no net has to cross a box and no label lands on
top of another; the ESP32's pin column keeps its real order so the reader can count down the header.
Colour says which wire it is, and the label on the line says the same thing for a printout. A junction
carries a dot and a crossing does not, which is the only convention the picture relies on.

    python scripts/draw_wiring.py            # writes docs/rig-wiring.svg
    python scripts/draw_wiring.py --png      # also writes docs/rig-wiring.png, which is not committed

The picture is generated from this file on purpose. `CONTRIBUTING.md` asks for Mermaid rather than image
files, and this is the one exception: Mermaid cannot show a header's pin order, which is the thing a person
holding a jumper wire actually needs. Committing the script with the SVG keeps the exception honest - the
drawing is reproducible, and a wire that moves is a change to this file and to the table beside it.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

W, H = 16.0, 12.0
#: The diagram lives beside the document that describes the same wiring, so neither can be read alone.
DOCS = Path(__file__).resolve().parent.parent / "docs"

C = {
    "3v3": "#D97A00",
    "sda": "#B8860B",
    "scl": "#1F7A3D",
    "btn": "#6A1B9A",
    "seg": "#8D6E63",
    "com": "#1565C0",
    "gnd": "#111111",
    "box": "#2B2B2B",
    "unused": "#C4C4C4",
}

plt.rcParams["font.family"] = "DejaVu Sans"
fig, ax = plt.subplots(figsize=(W, H), dpi=150)
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")


def box(x, y, w, h, title=None, subtitle=None, ts=10.5, ss=7.6):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=1.4,
            edgecolor=C["box"],
            facecolor="#F7F7F7",
            zorder=2,
        )
    )
    if title:
        ax.text(
            x + w / 2,
            y + h - 0.22,
            title,
            ha="center",
            va="top",
            fontsize=ts,
            fontweight="bold",
            zorder=4,
        )
    if subtitle:
        ax.text(
            x + w / 2,
            y + h - 0.50,
            subtitle,
            ha="center",
            va="top",
            fontsize=ss,
            color="#555555",
            zorder=4,
        )


def term(x, y, label, side="left", size=8.4):
    ax.add_patch(plt.Circle((x, y), 0.045, color=C["box"], zorder=5))
    if label:
        if side == "left":
            ax.text(x + 0.11, y, label, ha="left", va="center", fontsize=size, zorder=5)
        else:
            ax.text(x - 0.11, y, label, ha="right", va="center", fontsize=size, zorder=5)


def wire(pts, key, lw=2.4):
    ax.plot(
        [p[0] for p in pts],
        [p[1] for p in pts],
        color=C[key],
        linewidth=lw,
        solid_capstyle="round",
        solid_joinstyle="round",
        zorder=3,
    )


def junction(x, y, key):
    ax.add_patch(plt.Circle((x, y), 0.055, color=C[key], zorder=6))


def label(x, y, text, key=None, size=7.6):
    ax.text(
        x,
        y,
        text,
        fontsize=size,
        color=C[key] if key else "#333333",
        ha="center",
        va="center",
        fontweight="bold",
        zorder=7,
        bbox=dict(
            boxstyle="round,pad=0.15",
            facecolor="white",
            edgecolor=C[key] if key else "#999999",
            linewidth=0.6,
        ),
    )


def digit(cx, cy, w=0.44, h=0.72):
    """One seven-segment digit, drawn as the seven bars it is."""
    left, right = cx - w / 2, cx + w / 2
    top, bottom = cy + h / 2, cy - h / 2
    for pts in (
        [(left, top), (right, top)],  # A
        [(right, top), (right, cy)],  # B
        [(right, cy), (right, bottom)],  # C
        [(left, bottom), (right, bottom)],  # D
        [(left, cy), (left, bottom)],  # E
        [(left, top), (left, cy)],  # F
        [(left, cy), (right, cy)],  # G
    ):
        ax.plot(
            [p[0] for p in pts],
            [p[1] for p in pts],
            color="#3A3A3A",
            linewidth=2.6,
            solid_capstyle="round",
            zorder=5,
        )


# ------------------------------------------------------------------ title
ax.text(0.5, 11.55, "AquaVision rig — wiring", fontsize=17, fontweight="bold", va="center")
ax.text(
    0.5,
    11.20,
    "ESP32-S3-N16R8   ·   SSD1306 OLED 0x3C   ·   four-digit display, common anode   ·   "
    "every panel pin is a GPIO: no 5 V rail",
    fontsize=8.6,
    color="#444444",
    va="center",
)

# ------------------------------------------------------------------ ESP32
EX, EW = 0.40, 3.10
EY, EH = 3.40, 7.50
box(EX, EY, EW, EH, "ESP32-S3-N16R8", "left header, names as printed")
PINS = [
    "3V3",
    "3V3",
    "RST",
    "4",
    "5",
    "6",
    "7",
    "15",
    "16",
    "17",
    "18",
    "8",
    "3",
    "46",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
]
TOP, STEP = 9.90, 0.28
#: Every GPIO this rig wires, and which wire it is. The wiring test parses this table and holds it to
#: `config.h`; the drawing itself reads the same entries, so a pin cannot be drawn that is not listed here.
#: Segment A is GPIO 3 and B-G are 13-18; the four commons are 5, 6, 7 and 10, digit 1 first.
USED = {
    "3V3": "3v3",
    "4": "btn",
    "5": "com",
    "6": "com",
    "7": "com",
    "10": "com",
    "3": "seg",
    "13": "seg",
    "14": "seg",
    "15": "seg",
    "16": "seg",
    "17": "seg",
    "18": "seg",
    "8": "sda",
    "9": "scl",
}
PINY = {}
for i, name in enumerate(PINS):
    y = TOP - i * STEP
    key = USED.get(name)
    if key and name not in PINY:
        PINY[name] = y
        ax.add_patch(plt.Circle((EX + 0.20, y), 0.045, color=C[key], zorder=5))
        ax.text(
            EX + 0.31, y, name, fontsize=9.2, fontweight="bold", color=C[key], va="center", zorder=5
        )
        ax.plot([EX + 0.52, EX + EW], [y, y], color=C[key], linewidth=1.0, zorder=3)
    else:
        ax.text(EX + 0.31, y, name, fontsize=8.0, color=C["unused"], va="center", zorder=5)
ax.text(
    EX + EW / 2,
    4.25,
    "pins by the USB ports",
    fontsize=6.9,
    color="#777777",
    ha="center",
    va="center",
)
EGND_Y = 3.80
ax.add_patch(plt.Circle((EX + 0.20, EGND_Y), 0.045, color=C["gnd"], zorder=5))
ax.text(
    EX + 0.31, EGND_Y, "GND", fontsize=9.2, fontweight="bold", color=C["gnd"], va="center", zorder=5
)
ax.plot([EX + 0.52, EX + EW], [EGND_Y, EGND_Y], color=C["gnd"], linewidth=1.0, zorder=3)

# ------------------------------------------------------------------ lanes and ribbons
# The panel leaves the header as two ribbons - seven segment wires and four common wires - and they hug the
# header because the two pin groups are interleaved: a ribbon that started further right would be crossed by
# every stub of the other one. The four single nets leave in their own lanes beyond them.
SEG_BUS, COM_BUS = 3.62, 3.78
L_BTN, L_3V3, L_SDA, L_SCL = 3.98, 4.18, 4.38, 4.58

# ------------------------------------------------------------------ segment ribbon
for pin in ("15", "16", "17", "18", "3", "13", "14"):
    y = PINY[pin]
    ax.plot([EX + EW, SEG_BUS], [y, y], color=C["seg"], linewidth=1.8, zorder=3)
    junction(SEG_BUS, y, "seg")

# ------------------------------------------------------------------ common ribbon
# No resistor anywhere on this one: a common is the anode of its digit, and it carries the sum of that
# digit's segment currents, so exactly one of the four may be high at a time.
for pin in ("5", "6", "7", "10"):
    y = PINY[pin]
    ax.plot([EX + EW, COM_BUS], [y, y], color=C["com"], linewidth=1.8, zorder=3)
    junction(COM_BUS, y, "com")
wire([(COM_BUS, PINY["5"]), (COM_BUS, 8.10), (6.60, 8.10)], "com", 2.8)
label(5.10, 8.32, "4 commons", "com", size=7.2)
wire([(SEG_BUS, PINY["15"]), (SEG_BUS, 4.95), (6.60, 4.95)], "seg", 2.8)
label(5.05, 4.72, "7 segments", "seg", size=7.2)

# ------------------------------------------------------------------ 3.3 V net
wire([(EX + EW, PINY["3V3"]), (L_3V3, PINY["3V3"]), (L_3V3, 10.65), (6.70, 10.65)], "3v3")
label(5.80, 10.86, "3.3 V", "3v3")

# ------------------------------------------------------------------ SDA and SCL
wire([(EX + EW, PINY["8"]), (L_SDA, PINY["8"]), (L_SDA, 10.25), (6.70, 10.25)], "sda")
label(5.80, 10.46, "SDA", "sda")
wire([(EX + EW, PINY["9"]), (L_SCL, PINY["9"]), (L_SCL, 9.90), (6.70, 9.90)], "scl")
label(5.80, 10.06, "SCL", "scl")

# ------------------------------------------------------------------ button
wire([(EX + EW, PINY["4"]), (L_BTN, PINY["4"]), (L_BTN, 3.40), (6.70, 3.40)], "btn")
label(5.30, 3.62, "GPIO4", "btn", size=7.2)

# ------------------------------------------------------------------ the display
DX, DW = 6.60, 6.00
DY, DH = 4.60, 4.30
box(
    DX,
    DY,
    DW,
    DH,
    "four-digit seven-segment display",
    "common anode · 240 Ω per segment · the four commons are direct",
)
# Four digits, left to right, the order the firmware calls 1-4.
for index in range(4):
    cx = DX + 1.65 + index * 0.90
    digit(cx, 7.25)
    ax.text(cx, 6.70, str(index + 1), ha="center", va="center", fontsize=7.4, color="#555555")
ax.text(
    DX + DW / 2,
    6.30,
    "one common high at a time",
    ha="center",
    va="center",
    fontsize=6.8,
    color="#666666",
    zorder=5,
)
# The seven segment resistors, drawn as the row of identical parts they are.
for index in range(7):
    rx = DX + 1.40 + index * 0.45
    ax.add_patch(
        Rectangle(
            (rx, 5.52),
            0.30,
            0.16,
            facecolor="#FFFFFF",
            edgecolor=C["seg"],
            linewidth=1.2,
            zorder=5,
        )
    )
wire([(DX, 4.95), (DX + 1.20, 4.95), (DX + 1.20, 5.60), (DX + 1.40, 5.60)], "seg", 2.0)
ax.text(
    DX + DW / 2 + 0.35,
    5.15,
    "240 Ω ×7, one per segment",
    ha="center",
    va="center",
    fontsize=6.8,
    color=C["seg"],
    zorder=5,
)
ax.text(
    DX + DW / 2 + 0.35,
    4.80,
    "segments A-G drive that segment on the digit whose common is high",
    ha="center",
    va="center",
    fontsize=6.4,
    color="#666666",
    zorder=5,
)

# ------------------------------------------------------------------ OLED
OX, OW = 6.60, 3.30
OY, OH = 9.30, 1.70
box(OX, OY, OW, OH, "OLED SSD1306", "3.3 V part · address 0x3C")
OL = OX + 0.10
O_VCC_Y, O_SDA_Y, O_SCL_Y = 10.65, 10.25, 9.90
term(OL, O_VCC_Y, "VCC", size=8.2)
term(OL, O_SDA_Y, "SDA", size=8.2)
term(OL, O_SCL_Y, "SCL", size=8.2)
O_GND_Y = 9.55
term(OX + OW - 0.10, O_GND_Y, "GND", side="right", size=8.2)

# ------------------------------------------------------------------ button
BX, BW = 6.60, 3.30
BY, BH = 3.00, 1.00
box(BX, BY, BW, BH, None)
ax.text(
    BX + BW / 2,
    BY + BH - 0.20,
    "momentary button",
    ha="center",
    va="top",
    fontsize=9.5,
    fontweight="bold",
)
B_Y = 3.40
term(BX + 0.10, B_Y, "GPIO4 side", size=8.0)
term(BX + BW - 0.10, B_Y, "GND side", side="right", size=8.0)

# ------------------------------------------------------------------ ground bus
BUS_Y = 1.40
ax.plot(
    [0.95, 12.95], [BUS_Y, BUS_Y], color=C["gnd"], linewidth=4.2, zorder=3, solid_capstyle="round"
)
ax.text(
    6.9,
    0.98,
    "one ground — every part, including the adapter's negative lead if it is used",
    ha="center",
    va="center",
    fontsize=8.6,
    color=C["gnd"],
    fontweight="bold",
)


def ground(x_from, y_from, x_bus):
    ax.plot(
        [x_from, x_bus, x_bus],
        [y_from, y_from, BUS_Y],
        color=C["gnd"],
        linewidth=2.2,
        zorder=3,
        solid_joinstyle="round",
    )
    junction(x_bus, BUS_Y, "gnd")


ground(EX + EW, EGND_Y, 3.25)
ground(OX + OW - 0.10, O_GND_Y, 12.90)
ground(BX + BW - 0.10, B_Y, 12.60)

# ------------------------------------------------------------------ checks
ax.text(13.30, 10.60, "Before the first power-on", fontsize=10.0, fontweight="bold", va="center")
for i, line in enumerate(
    [
        "1.  240 Ω between each pin and",
        "    its own segment.",
        "2.  No resistor on a common.",
        "3.  Never two commons high.",
        "4.  No panel pin on a power rail.",
    ]
):
    ax.text(13.30, 10.18 - i * 0.32, line, fontsize=7.4, color="#333333", va="center")

# ------------------------------------------------------------------ legend
LX, LYW = 13.30, 2.40
LY, LH = 2.60, 5.60
ax.add_patch(
    FancyBboxPatch(
        (LX, LY),
        LYW,
        LH,
        boxstyle="round,pad=0.03,rounding_size=0.08",
        linewidth=1.2,
        edgecolor=C["box"],
        facecolor="white",
        zorder=2,
    )
)
ax.text(
    LX + LYW / 2,
    LY + LH - 0.28,
    "wire colour",
    ha="center",
    va="center",
    fontsize=9.4,
    fontweight="bold",
    zorder=4,
)
rows = [
    ("3v3", "3.3 V"),
    ("gnd", "ground"),
    ("sda", "SDA"),
    ("scl", "SCL"),
    ("btn", "GPIO4"),
    ("seg", "segment, 240 Ω"),
    ("com", "common, direct"),
]
for i, (key, name) in enumerate(rows):
    y = LY + LH - 0.75 - i * 0.60
    ax.plot([LX + 0.20, LX + 0.78], [y, y], color=C[key], linewidth=3.2, solid_capstyle="round")
    ax.text(LX + 0.92, y, name, ha="left", va="center", fontsize=7.8, zorder=4)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", action="store_true", help="also write a PNG beside the SVG")
    args = parser.parse_args()

    # Written through `io` and as bytes rather than straight to the path so the file keeps LF endings.
    # Matplotlib opens the target in text mode, which on Windows writes CRLF; `.gitattributes` stores this
    # file as `eol=lf`, so a direct save shows every line as changed and leaves a line-ending warning.
    svg = DOCS / "rig-wiring.svg"
    buffer = io.BytesIO()
    fig.savefig(buffer, format="svg", facecolor="white", bbox_inches="tight")
    svg.write_bytes(buffer.getvalue().replace(b"\r\n", b"\n"))
    print(f"wrote {svg.relative_to(svg.parent.parent)}")
    if args.png:
        png = DOCS / "rig-wiring.png"
        fig.savefig(png, dpi=150, facecolor="white", bbox_inches="tight")
        print(f"wrote {png.relative_to(png.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
