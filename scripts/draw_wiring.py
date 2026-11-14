"""Draw the rig wiring diagram: one page a person can wire from at the bench.

Not a mechanical drawing. Boxes are on a grid with gaps, so no net has to cross a box and no label lands on
top of another; the ESP32's pin column keeps its real order so the reader can count down the header.
Colour says which wire it is, and the label on the line says the same thing for a printout.

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
from matplotlib.patches import FancyBboxPatch

W, H = 16.0, 12.0
#: The diagram lives beside the document that describes the same wiring, so neither can be read alone.
DOCS = Path(__file__).resolve().parent.parent / "docs"

C = {
    "3v3": "#D97A00",
    "5v": "#C8102E",
    "gnd": "#111111",
    "sda": "#B8860B",
    "scl": "#1F7A3D",
    "btn": "#6A1B9A",
    "led1": "#7A7A7A",
    "led2": "#4A4A4A",
    "led3": "#1565C0",
    "bar": "#8D6E63",
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


def lane_label(x, y, text, key):
    ax.text(
        x,
        y,
        text,
        fontsize=7.8,
        color=C[key],
        rotation=90,
        ha="center",
        va="center",
        fontweight="bold",
        zorder=7,
        bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor=C[key], linewidth=0.6),
    )


# ------------------------------------------------------------------ title
ax.text(0.5, 11.55, "AquaVision rig — wiring", fontsize=17, fontweight="bold", va="center")
ax.text(
    0.5,
    11.20,
    "ESP32-S3-N16R8   ·   MB-102 (7–12 V in)   ·   SSD1306 OLED 0x3C   ·   10-LED bar on GPIO 10–18 and 21",
    fontsize=8.6,
    color="#444444",
    va="center",
)

# ------------------------------------------------------------------ ESP32
EX, EW = 0.4, 3.1
EY, EH = 3.55, 7.45
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
TOP, STEP = 10.30, 0.28
USED = {
    "3V3": "3v3",
    "4": "btn",
    "5": "led1",
    "6": "led2",
    "7": "led3",
    "8": "sda",
    "9": "scl",
    "10": "bar",
    "11": "bar",
    "12": "bar",
    "13": "bar",
    "14": "bar",
    "15": "bar",
    "16": "bar",
    "17": "bar",
    "18": "bar",
    "21": "bar",
}
PINY = {}
for i, name in enumerate(PINS):
    y = TOP - i * STEP
    key = USED.get(name)
    if key and name not in PINY:
        PINY[name] = y
        ax.add_patch(plt.Circle((EX + 0.20, y), 0.045, color=C[key], zorder=5))
        ax.text(
            EX + 0.31, y, name, fontsize=9.4, fontweight="bold", color=C[key], va="center", zorder=5
        )
        ax.plot([EX + 0.52, EX + EW], [y, y], color=C[key], linewidth=1.0, zorder=3)
    elif key:
        ax.text(EX + 0.31, y, name, fontsize=8.0, color=C["unused"], va="center", zorder=5)
    else:
        ax.text(EX + 0.31, y, name, fontsize=8.2, color=C["unused"], va="center", zorder=5)
ax.text(
    EX + EW / 2,
    3.66,
    "pins by the USB ports",
    fontsize=6.9,
    color="#777777",
    ha="center",
    va="center",
)
EGND_Y, E5V_Y, E21_Y = 4.22, 3.95, 4.55
ax.add_patch(plt.Circle((EX + 0.20, EGND_Y), 0.045, color=C["gnd"], zorder=5))
ax.text(
    EX + 0.31, EGND_Y, "GND", fontsize=9.4, fontweight="bold", color=C["gnd"], va="center", zorder=5
)
ax.add_patch(plt.Circle((EX + 0.20, E5V_Y), 0.045, color=C["unused"], zorder=5))
ax.text(EX + 0.31, E5V_Y, "5V", fontsize=8.2, color=C["unused"], va="center", zorder=5)
# GPIO 21 is the bar's last lamp and it is **not** in the left column: it sits on the right header, beside
# the USB pair, so it is drawn with these rows instead of in the order above.
ax.add_patch(plt.Circle((EX + 0.20, E21_Y), 0.045, color=C["bar"], zorder=5))
ax.text(
    EX + 0.31, E21_Y, "21", fontsize=9.4, fontweight="bold", color=C["bar"], va="center", zorder=5
)
ax.text(
    EX + 0.55,
    E21_Y,
    "right header",
    fontsize=6.6,
    color="#777777",
    va="center",
    zorder=5,
)
ax.plot([EX + 1.65, EX + EW], [E21_Y, E21_Y], color=C["bar"], linewidth=1.0, zorder=3)

# ------------------------------------------------------------------ MB-102
MX, MW = 0.4, 2.5
MY, MH = 1.15, 2.15
box(MX, MY, MW, MH, "MB-102", "12 V into the DC jack")
ax.text(
    MX + MW / 2,
    MY + 0.55,
    "rail A jumper:  5 V\nrail B jumper:  OFF",
    ha="center",
    va="center",
    fontsize=8.0,
    color="#333333",
    zorder=5,
)
M5_Y, MG_Y = 2.85, 2.15
term(MX + MW - 0.10, M5_Y, "5V", side="right")
term(MX + MW - 0.10, MG_Y, "GND", side="right")

# ------------------------------------------------------------------ LED bar
# Ten single LEDs on GPIO 10-18 and 21. Wired exactly like the three lamps below: anode on the 5 V
# rail through its own 330 Ohm, cathode on its own pin, so the pin sinks the current and LOW lights it.
# Level 1 is GPIO 10 and level 10 is GPIO 21; the lamps are yellow for levels 1-7 and white for 8-10,
# which is the split the parts on hand support - see `config.h`.
BAR_PINS = [str(number) for number in [*range(10, 19), 21]]
BAR_COLOURS = ["#F2C200"] * 7 + ["#FFFFFF"] * 3
BARX, BARW = 8.90, 3.50
BARY, BARH = 1.55, 2.55
box(
    BARX,
    BARY,
    BARW,
    BARH,
    "LED bar — GPIO 10-18, 21",
    "yellow 1-7, white 8-10 · 5 V → 330 Ω → anode",
)
BAR_X0, BAR_Y, BAR_R = 9.30, 2.55, 0.085
BAR_DX = (12.30 - BAR_X0) / (len(BAR_PINS) - 1)
BAR_RAIL_Y = 3.20
bar_x = [BAR_X0 + index * BAR_DX for index in range(len(BAR_PINS))]
wire([(BARX, BAR_RAIL_Y), (12.35, BAR_RAIL_Y)], "5v", 2.2)
for index, (pin, x) in enumerate(zip(BAR_PINS, bar_x, strict=True)):
    ax.plot([x, x], [BAR_RAIL_Y, BAR_Y + BAR_R], color=C["5v"], linewidth=1.8, zorder=3)
    ax.add_patch(
        plt.Circle(
            (x, BAR_Y),
            BAR_R,
            facecolor=BAR_COLOURS[index],
            edgecolor=C["bar"],
            linewidth=1.3,
            zorder=5,
        )
    )
    ax.text(x, BAR_Y - 0.28, pin, ha="center", va="center", fontsize=6.4, zorder=5)
ax.text(
    BARX + BARW / 2,
    BARY + 0.22,
    "level 1 (left)  →  10 (right)",
    fontsize=6.6,
    color="#666666",
    ha="center",
    va="center",
    zorder=5,
)
# The ten pins leave as one ribbon: a stub from each pin to a bus beside the header, then a single line to
# the bar. Ten separate wires across the I2C lanes would be ten crossings and one lie - a ribbon cable is
# what a person actually plugs in, and the last lamp joins it from the right header.
BAR_BUS = 3.62
for pin in BAR_PINS:
    y = E21_Y if pin == "21" else PINY[pin]
    ax.plot([EX + EW, BAR_BUS], [y, y], color=C["bar"], linewidth=2.0, zorder=3)
    junction(BAR_BUS, y, "bar")
ax.plot([BAR_BUS, BAR_BUS], [4.30, PINY["15"]], color=C["bar"], linewidth=3.2, zorder=3)
wire([(BAR_BUS, 4.30), (8.75, 4.30), (8.75, 3.85), (BARX, 3.85)], "bar", 3.0)
ax.text(
    7.20,
    4.60,
    "10 wires",
    fontsize=7.4,
    color=C["bar"],
    ha="center",
    va="center",
    fontweight="bold",
    zorder=7,
    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor=C["bar"], linewidth=0.6),
)

# ------------------------------------------------------------------ OLED
OX, OW = 8.90, 3.50
OY, OH = 9.00, 2.10
box(OX, OY, OW, OH, "OLED SSD1306", "3.3 V part · address 0x3C")
OL = OX + 0.10
O_VCC_Y, O_SDA_Y, O_SCL_Y, O_GND_Y = 10.35, 9.85, 9.45, 9.30
term(OL, O_VCC_Y, "VCC", size=8.2)
term(OL, O_SDA_Y, "SDA", size=8.2)
term(OL, O_SCL_Y, "SCL", size=8.2)
term(OL, O_GND_Y, "GND", size=8.2)

# ------------------------------------------------------------------ button
BX, BW = 8.90, 3.50
BY, BH = 7.60, 1.10
box(BX, BY, BW, BH, None)
ax.text(
    BX + BW / 2,
    BY + BH - 0.22,
    "momentary button",
    ha="center",
    va="top",
    fontsize=9.5,
    fontweight="bold",
)
B_Y = 8.00
term(BX + 0.10, B_Y, "GPIO4 side", size=8.0)
term(BX + BW - 0.10, B_Y, "GND side", side="right", size=8.0)

# ------------------------------------------------------------------ LEDs
LED1_Y, LED2_Y, LED3_Y = 6.95, 6.35, 5.75
# The lamp colour is the fill of its symbol and the word on its row; the wire colour stays the pin's, so
# that red here cannot be confused with the red 5 V rail running past on the right.
for y, name, key, lamp in (
    (LED1_Y, "white LED  (PASS)", "led1", "#FFFFFF"),
    (LED2_Y, "red LED  (RETAKE)", "led2", "#CC2222"),
    (LED3_Y, "blue LED  (state)", "led3", "#1B62C8"),
):
    ax.add_patch(
        FancyBboxPatch(
            (BX, y - 0.24),
            BW,
            0.48,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            linewidth=1.1,
            edgecolor=C["box"],
            facecolor="#F7F7F7",
            zorder=2,
        )
    )
    ax.text(BX + 0.14, y, name, ha="left", va="center", fontsize=8.4, zorder=5)
    ax.text(BX + 1.75, y, "330 Ω", ha="center", va="center", fontsize=7.8, zorder=5)
    ax.plot([BX + 2.25, BX + 2.75], [y, y], color=C[key], linewidth=2.6, zorder=3)
    ax.add_patch(
        plt.Circle((BX + 2.95, y), 0.10, facecolor=lamp, edgecolor=C[key], linewidth=1.6, zorder=5)
    )
    ax.text(BX + 2.95, y - 0.27, "LED", ha="center", va="center", fontsize=6.2, zorder=5)
    ax.add_patch(plt.Circle((BX + 0.10, y), 0.045, color=C["box"], zorder=5))

# ------------------------------------------------------------------ checks
ax.text(9.20, 5.35, "Before the first power-on", fontsize=10.0, fontweight="bold", va="center")
for i, line in enumerate(
    [
        "1.  5 V rail with nothing on it: 5 V, not 12 V.",
        "2.  COM port, not native USB.",
    ]
):
    ax.text(9.20, 5.00 - i * 0.30, line, fontsize=7.7, color="#333333", va="center")

# ------------------------------------------------------------------ ground bus
BUS_Y = 0.70
ax.plot(
    [0.95, 12.60], [BUS_Y, BUS_Y], color=C["gnd"], linewidth=4.2, zorder=3, solid_capstyle="round"
)
ax.text(
    6.8,
    0.33,
    "one ground — every part, including the adapter's negative lead",
    ha="center",
    va="center",
    fontsize=8.8,
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


ground(3.05, EGND_Y, 3.20)
ground(MX + MW - 0.10, MG_Y, 2.80)
ground(OL, O_GND_Y, 12.55)
ground(BX + BW - 0.10, B_Y, 12.45)
# The lamps' anodes go to the 5 V rail and the pin sinks them, so the line on their right is a supply
# rather than a return - the one place where the colour says the current runs the other way.
for y, xd in ((LED1_Y, 12.75), (LED2_Y, 12.95), (LED3_Y, 13.15)):
    ax.plot([BX + 3.05, xd], [y, y], color=C[key], linewidth=2.0, zorder=3)
    ax.plot([xd, xd], [y, 1.05], color=C["5v"], linewidth=2.2, zorder=3)
    junction(xd, 1.05, "5v")

# ------------------------------------------------------------------ 3.3 V net
L33 = 3.75
wire([(EX + EW, PINY["3V3"]), (L33, PINY["3V3"]), (L33, O_VCC_Y), (OL, O_VCC_Y)], "3v3")
ax.text(
    5.60,
    O_VCC_Y + 0.14,
    "3.3 V",
    fontsize=7.8,
    color=C["3v3"],
    ha="center",
    va="center",
    fontweight="bold",
    zorder=7,
    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor=C["3v3"], linewidth=0.6),
)

# ------------------------------------------------------------------ SDA
LS = 4.05
wire([(EX + EW, PINY["8"]), (LS, PINY["8"]), (LS, O_SDA_Y), (OL, O_SDA_Y)], "sda")
lane_label(LS, 8.20, "SDA", "sda")

# ------------------------------------------------------------------ SCL
LC = 4.35
wire([(EX + EW, PINY["9"]), (LC, PINY["9"]), (LC, O_SCL_Y), (OL, O_SCL_Y)], "scl")
lane_label(LC, 7.60, "SCL", "scl")

# ------------------------------------------------------------------ button / LEDs
LB = 4.65
wire([(EX + EW, PINY["4"]), (LB, PINY["4"]), (LB, B_Y), (BX + 0.10, B_Y)], "btn")
LL1 = 4.95
wire([(EX + EW, PINY["5"]), (LL1, PINY["5"]), (LL1, LED1_Y), (BX + 0.10, LED1_Y)], "led1")
LL2 = 5.25
wire([(EX + EW, PINY["6"]), (LL2, PINY["6"]), (LL2, LED2_Y), (BX + 0.10, LED2_Y)], "led2")
LL3 = 5.45
wire([(EX + EW, PINY["7"]), (LL3, PINY["7"]), (LL3, LED3_Y), (BX + 0.10, LED3_Y)], "led3")

# ------------------------------------------------------------------ 5 V
L5 = 3.30
wire([(MX + MW, M5_Y), (L5, M5_Y), (L5, 1.05), (13.25, 1.05)], "5v", 2.6)
# The bar's rail: every anode comes off it through its own 330 Ohm inside the box.
junction(8.55, 1.05, "5v")
wire([(8.55, 1.05), (8.55, BAR_RAIL_Y), (BARX, BAR_RAIL_Y)], "5v", 2.6)
ax.text(
    6.05,
    1.32,
    "5 V",
    fontsize=8.0,
    color=C["5v"],
    ha="center",
    va="center",
    fontweight="bold",
    zorder=7,
    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor=C["5v"], linewidth=0.6),
)
# ------------------------------------------------------------------ legend
LX, LYW = 13.45, 2.10
LY, LH = 4.90, 5.70
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
    ("5v", "5 V"),
    ("gnd", "ground"),
    ("sda", "SDA"),
    ("scl", "SCL"),
    ("btn", "GPIO4"),
    ("led1", "GPIO5"),
    ("led2", "GPIO6"),
    ("led3", "GPIO7"),
    ("bar", "GPIO10-18, 21"),
]
for i, (key, name) in enumerate(rows):
    y = LY + LH - 0.70 - i * 0.46
    ax.plot([LX + 0.20, LX + 0.78], [y, y], color=C[key], linewidth=3.2, solid_capstyle="round")
    ax.text(LX + 0.92, y, name, ha="left", va="center", fontsize=8.6, zorder=4)


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
