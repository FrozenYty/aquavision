// The 128x64 layout: one band structure for every state, one function per state.
//
// A new state costs an enum entry in `rig_state.h`, a case in `render`, and a `drawX` here. Nothing
// else in the firmware needs to know the screen exists.
//
// The bands do not move between states. An operator glancing at the rig always looks at the same place
// for the same kind of information, whether the frame passed or failed.

#include "screen.h"

#include <cstdio>

#include "config.h"
#include "rig_state.h"

namespace {

namespace layout {

// Vertical bands, in pixels.
constexpr int HEADER_BASELINE = 7;
constexpr int RULE_TOP = 8;
// The label is bold 7x13 so it reads as a caption rather than as fine print, and its baseline lands on 26
// because that puts the label's band (17-26) on the same centre line as the number's (12-31, from the
// 19 px ascent of the score font measured on the panel). A 5x7 label at the same baseline sat 1.5 px low.
constexpr int LABEL_BASELINE = 26;
constexpr int VALUE_BASELINE = 31;    // the 18 px score, clear of the header rule above it
constexpr int BANNER_TOP = 33;
constexpr int BANNER_BOTTOM = 53;
constexpr int BANNER_SINGLE = 48;     // one line of the proportional banner font, centred in the band
constexpr int HINT_BASELINE = 25;     // the free band above the banner
constexpr int RULE_BOTTOM = 54;
constexpr int FOOTER_BASELINE = 62;

// Horizontal bands. The footer is two fixed columns so a five-digit turbidity reading cannot walk into
// the frame counter: the largest value the sensor produces is 16000, so five digits is the normal case,
// not an edge case.
constexpr int MARGIN = 4;
constexpr int RIGHT_EDGE = 128 - MARGIN;
// The footer keeps one gutter width in both columns: label, six pixels, value. The turbidity value is
// left-aligned after that gutter rather than right-aligned to a column edge, because a right-aligned
// value leaves a two-pixel gap after a five-digit reading and a wide one after a three-digit reading -
// two different gaps in the same row.
constexpr int FOOTER_VALUE_LEFT = 34;  // 4 + "TURB" (24) + 6
constexpr int FRAMES_EDGE = RIGHT_EDGE; // the frame counter is right-aligned as one string

}  // namespace layout

using namespace layout;

// Where a radius-1 dot belongs so that it reads level with a row of capitals.
//
// Measured on the panel: this font reports ascent 6 and descent -1, so at baseline 7 the capitals cover
// rows 1-6 and their centre is 3.5. A radius-1 disc covers three rows, so it can sit on 3 or on 4 but
// never on 3.5; 4 reads low, 3 reads level. The previous version tried `(ascent + 1) / 2` to nudge it
// up and changed nothing, because 6 / 2 and 7 / 2 are both 3 in integer arithmetic.
int dotRow(U8G2& display) {
  const int capTop = HEADER_BASELINE - display.getAscent();
  const int capBottom = HEADER_BASELINE - 1;
  return (capTop + capBottom) / 2;  // floors 3.5 to 3 on purpose
}

void drawCentred(U8G2& display, const char* text, int baseline) {
  display.drawStr((128 - display.getStrWidth(text)) / 2, baseline, text);
}

void drawHeader(U8G2& display, const rig::State& state) {
  display.setFont(u8g2_font_5x7_tf);
  display.drawStr(MARGIN, HEADER_BASELINE, "AQUAVISION");

  const char* link = state.pcAlive ? "ONLINE" : "OFFLINE";
  const int width = display.getStrWidth(link);
  const int text_x = RIGHT_EDGE - width;

  // The dot sits on the text's optical centre rather than on a hand-picked baseline: a disc drawn by eye
  // landed a pixel low, which reads as "slightly wrong" without anyone being able to name the cause.
  if (state.heartbeatOn || !state.pcAlive) {
    display.drawDisc(text_x - 7, dotRow(display), 1);
  }
  display.drawStr(text_x, HEADER_BASELINE, link);

  display.drawHLine(0, RULE_TOP, 128);
}

// `label` sits above and to the left of the number, like a gauge's caption. On a RETAKE it is the reason
// rather than the word QUALITY, which is what freed the banner to carry one word instead of two lines
// crammed into twenty pixels.
void drawScoreRow(U8G2& display, const rig::State& state, const char* label) {
  display.setFont(u8g2_font_7x13B_tf);
  display.drawStr(MARGIN, LABEL_BASELINE, label);

  // Values are right-aligned so two- and three-digit numbers share an edge; centred numbers jump about,
  // which is the one thing a gauge must not do.
  //
  // 18 px, not 24: at 24 the digits started on the header rule and read as touching the status line.
  // Ascending 18 from the baseline at 31 puts their top at 13, leaving a clear band under the rule.
  display.setFont(u8g2_font_helvB18_tn);
  char score[8];
  snprintf(score, sizeof(score), "%d", state.score);
  display.drawStr(RIGHT_EDGE - display.getStrWidth(score), VALUE_BASELINE, score);

  display.setFont(u8g2_font_5x7_tf);
}

// Filled means the frame passed, outlined means it has to be taken again. Shape carries the verdict on
// its own, so a glance from across the room works before a single letter is legible.
void drawBannerFrame(U8G2& display, bool filled) {
  if (filled) {
    display.drawBox(0, BANNER_TOP, 128, BANNER_BOTTOM - BANNER_TOP);
    display.setDrawColor(0);
  } else {
    display.drawFrame(0, BANNER_TOP, 128, BANNER_BOTTOM - BANNER_TOP);
  }
}

void drawBanner(U8G2& display, const char* text, bool filled) {
  drawBannerFrame(display, filled);

  // A proportional face for the verdict. The 5x7 bitmap font is fixed at six pixels per glyph, and its
  // even tracking makes "CAPTURING" read as "CAP TURING" - the eye finds a gap where the stems happen to
  // be furthest apart. Proportional spacing closes it and looks less like debug output.
  display.setFont(u8g2_font_helvB10_tr);
  drawCentred(display, text, BANNER_SINGLE);

  display.setDrawColor(1);
}

const char* reasonWords(rig::Reason reason) {
  switch (reason) {
    case rig::Reason::LowLight:
      return "LOW LIGHT";
    case rig::Reason::Blur:
      return "BLUR";
    case rig::Reason::ColorCast:
      return "COLOR CAST";
    case rig::Reason::None:
      return "OK";
    default:
      return "UNKNOWN";
  }
}

void drawFooter(U8G2& display, const rig::State& state) {
  display.setFont(u8g2_font_5x7_tf);

  display.drawStr(MARGIN, FOOTER_BASELINE, "TURB");
  if (state.turbidity < 0) {
    // Five dashes, not two: the reading is four or five digits wide, so the placeholder occupies the
    // same stretch as the number will and the row does not jump when data arrives.
    display.drawStr(FOOTER_VALUE_LEFT, FOOTER_BASELINE, "-----");
  } else {
    char value[8];
    snprintf(value, sizeof(value), "%d", state.turbidity);
    display.drawStr(FOOTER_VALUE_LEFT, FOOTER_BASELINE, value);
  }

  char frames[16];
  snprintf(frames, sizeof(frames), "FRAMES %d", state.frames);
  display.drawStr(FRAMES_EDGE - display.getStrWidth(frames), FOOTER_BASELINE, frames);

  display.drawHLine(0, RULE_BOTTOM, 128);
}

void drawOffline(U8G2& display) {
  display.drawBox(0, 0, 128, 64);
  display.setDrawColor(0);

  // "SERIAL OFFLINE" on one line at 12 px was wider than the panel and lost its last letters, which is
  // how a whole message becomes "SERIAL OFFILN". Three short centred lines cannot be clipped.
  display.setFont(u8g2_font_5x7_tf);
  drawCentred(display, "AQUAVISION", 12);

  display.setFont(u8g2_font_helvB12_tr);
  drawCentred(display, "OFFLINE", 34);

  display.setFont(u8g2_font_5x7_tf);
  drawCentred(display, "CHECK USB CABLE", 52);

  display.setDrawColor(1);
}

void drawReady(U8G2& display) {
  // The band above the banner is empty on every score-less state, so it carries the one thing an
  // operator needs there: what to do next.
  display.setFont(u8g2_font_5x7_tf);
  drawCentred(display, "PRESS TO CAPTURE", HINT_BASELINE);
  drawBanner(display, "READY", false);
}

// Three dots under the word, one alight at a time. A still CAPTURING screen cannot say whether the
// board is waiting on the PC or has stopped working, and the press is the moment an operator most wants
// to know the rig is alive.
void drawCapturing(U8G2& display, const rig::State& state) {
  drawBannerFrame(display, false);

  display.setFont(u8g2_font_helvB10_tr);
  drawCentred(display, "CAPTURING", BANNER_SINGLE);

  // The dots live in the free band above the banner, not in the strip under the word: at three pixels
  // across a filled and a hollow mark are nearly indistinguishable, which made the animation read as a
  // static row of specks. At radius 2 they are five pixels across - one solid, two open - and the band
  // from 10 to 32 is unused on this screen anyway, because CAPTURING carries no score.
  constexpr int spacing = 14;
  constexpr int dot_y = 24;
  for (int i = 0; i < 3; ++i) {
    const int x = 64 + (i - 1) * spacing;
    if (i == state.animPhase) {
      display.drawDisc(x, dot_y, 2);
    } else {
      display.drawCircle(x, dot_y, 2);
    }
  }
}

void drawPass(U8G2& display, const rig::State& state) {
  drawScoreRow(display, state, "QUALITY");
  drawBanner(display, "PASS", true);
}

void drawRetake(U8G2& display, const rig::State& state) {
  // The reason takes the caption slot above the score; the banner keeps a single word. Two stacked lines
  // in a twenty-pixel band left one pixel between them, which read as a smudge rather than as a heading
  // and its cause.
  drawScoreRow(display, state, reasonWords(state.reason));
  drawBanner(display, "RETAKE", false);
}

}  // namespace

namespace screen {

void renderSplash(U8G2& display) {
  display.clearBuffer();
  // The name alone, on the centre line. A firmware version under it was the kind of second line that
  // reads as debug output on a screen meant to identify the instrument; `EVT HELLO` already carries the
  // version to whoever needs it.
  display.setFont(u8g2_font_helvB12_tr);
  drawCentred(display, "AQUAVISION", 38);
  display.sendBuffer();
}

void render(U8G2& display, const rig::State& state) {
  display.clearBuffer();

  if (state.screen == rig::Screen::Offline) {
    drawOffline(display);
    display.sendBuffer();
    return;
  }

  drawHeader(display, state);
  drawFooter(display, state);

  switch (state.screen) {
    case rig::Screen::Ready:
      drawReady(display);
      break;
    case rig::Screen::Capturing:
      drawCapturing(display, state);
      break;
    case rig::Screen::Pass:
      drawPass(display, state);
      break;
    case rig::Screen::Retake:
      drawRetake(display, state);
      break;
    case rig::Screen::Offline:
      break;  // handled above
  }

  display.sendBuffer();
}

}  // namespace screen
