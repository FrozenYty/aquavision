// The 128x64 layout — DRAFT.
//
// This is the first draft of the rig screen, agreed on 2026-11-07 and not yet seen on real hardware.
// Treat every coordinate below as provisional until the panel is on the bench: the glyph widths used
// here come from the font metrics, not from a photograph of the display.
//
// How to change it: every vertical position is a constant in `layout` below, and every state has its
// own `drawX` function. A new state costs an enum entry in `rig_state.h`, a case in `render()`, and one
// function here. Nothing else in the firmware knows about pixels.

#include "screen.h"

#include <cstdio>

#include "config.h"

namespace {

namespace layout {

// Vertical bands, in pixels. The bands do not move between states — only their contents change — so a
// glance at the rig always looks at the same place.
constexpr int HEADER_BASELINE = 7;
constexpr int RULE_TOP = 9;
constexpr int LABEL_BASELINE = 26;   // QUALITY
constexpr int VALUE_BASELINE = 32;   // the 24 px score, chosen so label and value share a centre line
constexpr int BANNER_TOP = 35;
constexpr int BANNER_BOTTOM = 49;
constexpr int BANNER_TEXT_BASELINE = 45;
constexpr int RULE_BOTTOM = 51;
constexpr int FOOTER_BASELINE = 62;

// Horizontal margins. Values are right-aligned so two- and three-digit numbers share an edge; centred
// numbers jump about, which is the one thing a gauge must not do.
constexpr int MARGIN = 4;
constexpr int RIGHT_EDGE = 128 - MARGIN;

}  // namespace layout

using namespace layout;

void rightAligned(U8G2& display, const char* text, int baseline) {
  display.setFont(u8g2_font_5x7_tf);
  display.drawStr(RIGHT_EDGE - display.getStrWidth(text), baseline, text);
}

void drawHeader(U8G2& display, const rig::State& state) {
  display.setFont(u8g2_font_5x7_tf);
  display.drawStr(MARGIN, HEADER_BASELINE, "AQUAVISION");

  const char* link = state.pcAlive ? "ONLINE" : "OFFLINE";
  const int width = display.getStrWidth(link);
  // One disc, not three: the heartbeat doubles as the status dot. A disc before the word and another
  // beside it read as decoration rather than state.
  if (state.heartbeatOn || !state.pcAlive) {
    display.drawDisc(RIGHT_EDGE - width - 8, 5, 1);
  }
  display.drawStr(RIGHT_EDGE - width, HEADER_BASELINE, link);

  display.drawHLine(0, RULE_TOP, 128);
}

void drawScoreRow(U8G2& display, const rig::State& state, bool showScore) {
  display.setFont(u8g2_font_5x7_tf);
  display.drawStr(MARGIN, LABEL_BASELINE, "QUALITY");
  if (!showScore) {
    return;
  }
  display.setFont(u8g2_font_helvB24_tn);
  char score[8];
  snprintf(score, sizeof(score), "%d", state.score);
  display.drawStr(RIGHT_EDGE - display.getStrWidth(score), VALUE_BASELINE, score);
}

void drawBanner(U8G2& display, const char* text, bool inverted) {
  display.setFont(u8g2_font_5x7_tf);
  if (inverted) {
    display.drawBox(0, BANNER_TOP, 128, BANNER_BOTTOM - BANNER_TOP);
    display.setDrawColor(0);
  } else {
    display.drawFrame(0, BANNER_TOP, 128, BANNER_BOTTOM - BANNER_TOP);
  }
  display.drawStr((128 - display.getStrWidth(text)) / 2, BANNER_TEXT_BASELINE, text);
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

  // "TURB", not "TURBIDITY": at 6 px per glyph the full word reaches x=88 while "FRAMES 34" starts at
  // x=70. Dropping the counter would let the full word back in.
  char turbidity[24];
  if (state.turbidity < 0) {
    snprintf(turbidity, sizeof(turbidity), "TURB --");
  } else {
    const char* glyph = state.trend == 1 ? "^" : (state.trend == 2 ? "v" : "-");
    snprintf(turbidity, sizeof(turbidity), "TURB %d %s", state.turbidity, glyph);
  }
  display.drawStr(MARGIN, FOOTER_BASELINE, turbidity);

  char frames[16];
  snprintf(frames, sizeof(frames), "FRAMES %d", state.frames);
  display.drawStr(RIGHT_EDGE - display.getStrWidth(frames), FOOTER_BASELINE, frames);

  display.drawHLine(0, RULE_BOTTOM, 128);
}

void drawOffline(U8G2& display) {
  display.drawBox(0, 0, 128, 64);
  display.setDrawColor(0);
  display.setFont(u8g2_font_5x7_tf);
  display.drawStr(MARGIN, 10, "AQUAVISION");
  display.setFont(u8g2_font_helvB12_tr);
  display.drawStr(MARGIN, 32, "SERIAL OFFLINE");
  display.setFont(u8g2_font_5x7_tf);
  display.drawStr(MARGIN, 46, "CHECK USB CONNECTION");
  display.setDrawColor(1);
}

void drawReady(U8G2& display, const rig::State& state) {
  drawScoreRow(display, state, false);
  drawBanner(display, "READY", false);
}

void drawCapturing(U8G2& display, const rig::State& state) {
  drawScoreRow(display, state, false);
  drawBanner(display, "CAPTURING", false);
}

void drawResult(U8G2& display, const rig::State& state, bool passed) {
  drawScoreRow(display, state, true);
  drawBanner(display, passed ? "PASS >=60" : "RETAKE <60", true);
  if (!passed) {
    // The footer answers "why" instead of repeating the turbidity, because a score without a cause
    // tells the operator nothing to fix.
    display.setFont(u8g2_font_5x7_tf);
    display.drawStr(MARGIN, FOOTER_BASELINE, reasonWords(state.reason));
  }
}

}  // namespace

namespace screen {

void renderSplash(U8G2& display) {
  display.clearBuffer();
  display.setFont(u8g2_font_helvB12_tr);
  const char* title = "AQUAVISION";
  display.drawStr((128 - display.getStrWidth(title)) / 2, 32, title);
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
      drawReady(display, state);
      break;
    case rig::Screen::Capturing:
      drawCapturing(display, state);
      break;
    case rig::Screen::Pass:
      drawResult(display, state, true);
      break;
    case rig::Screen::Retake:
      drawResult(display, state, false);
      break;
    case rig::Screen::Offline:
      break;  // handled above
  }

  display.sendBuffer();
}

}  // namespace screen
