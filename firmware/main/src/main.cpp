// Rig controller for AquaVision (P1-06).
//
// The ESP32 does four things and nothing else: it reports a button press, reads the turbidity sensor,
// shows the state of the last capture on a 0.96" OLED, and lights one of two LEDs. It does no imaging
// and no inference — the PC owns both, and the PC is the only source of truth for a frame's quality.
// The firmware's job is to be legible from across the room and to survive a stuck PC.
//
// Serial protocol, one event or command per line, ASCII, `\n` terminated:
//
//   ESP32 -> PC   EVT HELLO <version>
//                 EVT TRIGGER <millis>
//                 EVT TURBIDITY <0-100>
//                 EVT PONG
//   PC -> ESP32   CMD RESULT <score 0-100> <PASS|RETAKE> <REASON>
//                 CMD READY                 back to the idle screen
//                 CMD PING                  answered with EVT PONG
//
// REASON is one token: LOW_LIGHT, BLUR, COLOR_CAST or NONE. Any line the firmware does not understand
// is ignored rather than treated as an error — a garbled byte must not brick the rig.

#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace {

// ---------------------------------------------------------------------------- pins

constexpr int PIN_BUTTON = 4;
constexpr int PIN_LED_PASS = 5;    // green
constexpr int PIN_LED_RETAKE = 6;  // yellow
constexpr int PIN_I2C_SDA = 8;
constexpr int PIN_I2C_SCL = 9;

// The kit's OLED answers at 0x3C and the turbidity sensor at 0x49: one bus, two devices.
constexpr uint8_t TURBIDITY_ADDR = 0x49;

// ---------------------------------------------------------------------------- timing

constexpr uint32_t BUTTON_DEBOUNCE_MS = 25;
constexpr uint32_t LED_PULSE_MS = 300;
constexpr uint32_t OFFLINE_AFTER_MS = 10000;  // no word from the PC for this long
constexpr uint32_t TURBIDITY_PERIOD_MS = 5000;
constexpr uint32_t HEARTBEAT_PERIOD_MS = 1000;

U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(U8G2_R0, U8X8_PIN_NONE);

enum class Screen { Ready, Capturing, Pass, Retake, Offline };

struct State {
  Screen screen = Screen::Ready;
  int score = 0;
  char reason[12] = "NONE";
  int turbidity = -1;  // -1 means no reading yet
  int trend = 0;       // -1 falling, 0 flat, 1 rising
  int frames = 0;
  bool pcAlive = false;
  bool heartbeatOn = true;
} state;

uint32_t lastPcMessage = 0;
uint32_t lastTurbidity = 0;
uint32_t lastHeartbeat = 0;
uint32_t ledPassUntil = 0;
uint32_t ledRetakeUntil = 0;
uint32_t lastButtonEdge = 0;
bool lastButtonLevel = HIGH;
bool dirty = true;

// ---------------------------------------------------------------------------- sensor

int readTurbidity() {
  Wire.requestFrom(TURBIDITY_ADDR, (uint8_t)2);
  if (Wire.available() < 2) {
    return -1;
  }
  const int high = Wire.read();
  const int low = Wire.read();
  return (high << 8) | low;
}

void updateTrend(int fresh) {
  static int previous = -1;
  if (previous >= 0 && fresh >= 0) {
    const int delta = fresh - previous;
    state.trend = delta > 2 ? 1 : (delta < -2 ? -1 : 0);
  }
  if (fresh >= 0) {
    previous = fresh;
  }
}

// ---------------------------------------------------------------------------- drawing

// Right-aligned so two- and three-digit scores share an edge; centred numbers jump about.
void drawValue(const char* text, int baseline) {
  const int width = display.getStrWidth(text);
  display.drawStr(128 - 4 - width, baseline, text);
}

void drawBanner(const char* text, bool inverted) {
  constexpr int top = 52;
  constexpr int height = 12;
  display.setFont(u8g2_font_5x7_tf);
  if (inverted) {
    display.drawBox(0, top, 128, height);
    display.setDrawColor(0);
  } else {
    display.drawFrame(0, top, 128, height);
  }
  const int width = display.getStrWidth(text);
  display.drawStr((128 - width) / 2, top + 9, text);
  display.setDrawColor(1);
}

void drawHeader() {
  display.setFont(u8g2_font_5x7_tf);
  display.drawStr(4, 7, "AQUAVISION");

  const char* link = state.pcAlive ? "ONLINE" : "OFFLINE";
  const int width = display.getStrWidth(link);
  // One disc, not three: the heartbeat doubles as the status dot, because a disc before the word and
  // another beside it read as decoration rather than state.
  if (state.heartbeatOn || !state.pcAlive) {
    display.drawDisc(128 - 4 - width - 8, 5, 1);
  }
  display.drawStr(128 - 4 - width, 7, link);

  display.drawHLine(0, 16, 128);

  char turbidity[24];
  if (state.turbidity < 0) {
    snprintf(turbidity, sizeof(turbidity), "TURB --");
  } else {
    const char* glyph = state.trend > 0 ? "^" : (state.trend < 0 ? "v" : "-");
    snprintf(turbidity, sizeof(turbidity), "TURB %d %s", state.turbidity, glyph);
  }
  display.drawStr(4, 15, turbidity);

  char frames[16];
  snprintf(frames, sizeof(frames), "FRAMES %d", state.frames);
  display.drawStr(128 - 4 - display.getStrWidth(frames), 15, frames);
}

// While a retake is on screen the footer answers "why" instead of repeating the turbidity.
void drawReason(const char* reason) {
  const char* words = "UNKNOWN";
  if (strcmp(reason, "LOW_LIGHT") == 0) {
    words = "LOW LIGHT";
  } else if (strcmp(reason, "BLUR") == 0) {
    words = "BLUR";
  } else if (strcmp(reason, "COLOR_CAST") == 0) {
    words = "COLOR CAST";
  }
  display.setFont(u8g2_font_5x7_tf);
  display.drawStr(4, 15, words);
}

void renderOffline() {
  display.drawBox(0, 0, 128, 64);
  display.setDrawColor(0);
  display.setFont(u8g2_font_5x7_tf);
  display.drawStr(4, 10, "AQUAVISION");
  display.setFont(u8g2_font_helvB12_tr);
  display.drawStr(4, 32, "SERIAL OFFLINE");
  display.setFont(u8g2_font_5x7_tf);
  display.drawStr(4, 46, "CHECK USB CONNECTION");
  display.setDrawColor(1);
}

void render() {
  display.clearBuffer();

  if (state.screen == Screen::Offline) {
    renderOffline();
    display.sendBuffer();
    dirty = false;
    return;
  }

  drawHeader();
  display.setFont(u8g2_font_5x7_tf);
  display.drawStr(4, 25, "QUALITY");

  switch (state.screen) {
    case Screen::Ready:
      drawBanner("READY", false);
      break;

    case Screen::Capturing:
      drawBanner("CAPTURING", false);
      break;

    case Screen::Pass:
    case Screen::Retake: {
      display.setFont(u8g2_font_helvB24_tn);
      char score[8];
      snprintf(score, sizeof(score), "%d", state.score);
      drawValue(score, 48);
      if (state.screen == Screen::Pass) {
        drawBanner("PASS >=60", true);
      } else {
        drawBanner("RETAKE <60", true);
        drawReason(state.reason);
      }
      break;
    }

    case Screen::Offline:
      break;  // handled above
  }

  display.sendBuffer();
  dirty = false;
}

// ---------------------------------------------------------------------------- services

void serviceButton(uint32_t now) {
  const bool level = digitalRead(PIN_BUTTON);
  if (level == lastButtonLevel) {
    return;
  }
  if (now - lastButtonEdge < BUTTON_DEBOUNCE_MS) {
    return;
  }
  lastButtonEdge = now;
  lastButtonLevel = level;
  if (level != LOW) {
    return;
  }

  // A press with no PC listening would otherwise leave the screen on CAPTURING forever.
  if (!state.pcAlive) {
    state.screen = Screen::Offline;
    dirty = true;
    return;
  }
  state.screen = Screen::Capturing;
  dirty = true;
  Serial.printf("EVT TRIGGER %lu\n", (unsigned long)millis());
}

void serviceTurbidity(uint32_t now) {
  if (now - lastTurbidity < TURBIDITY_PERIOD_MS) {
    return;
  }
  lastTurbidity = now;
  const int value = readTurbidity();
  if (value < 0) {
    return;
  }
  updateTrend(value);
  state.turbidity = value;
  Serial.printf("EVT TURBIDITY %d\n", value);
  dirty = true;
}

void serviceHeartbeat(uint32_t now) {
  if (now - lastHeartbeat < HEARTBEAT_PERIOD_MS) {
    return;
  }
  lastHeartbeat = now;
  state.heartbeatOn = !state.heartbeatOn;
  // Only the idle screen blinks. During a result the score is what matters, and a redraw every second
  // would compete with it.
  if (state.screen == Screen::Ready) {
    dirty = true;
  }
}

void serviceLeds(uint32_t now) {
  digitalWrite(PIN_LED_PASS, now < ledPassUntil ? HIGH : LOW);
  digitalWrite(PIN_LED_RETAKE, now < ledRetakeUntil ? HIGH : LOW);
}

void serviceLink(uint32_t now) {
  const bool alive = (now - lastPcMessage) < OFFLINE_AFTER_MS;
  if (alive == state.pcAlive) {
    return;
  }
  state.pcAlive = alive;
  state.screen = alive ? Screen::Ready : Screen::Offline;
  dirty = true;
}

// ---------------------------------------------------------------------------- protocol

void handleLine(char* line) {
  char* saveptr = nullptr;
  char* verb = strtok_r(line, " ", &saveptr);
  if (verb == nullptr || strcmp(verb, "CMD") != 0) {
    return;
  }
  char* command = strtok_r(nullptr, " ", &saveptr);
  if (command == nullptr) {
    return;
  }

  lastPcMessage = millis();

  if (strcmp(command, "PING") == 0) {
    Serial.println("EVT PONG");
    return;
  }
  if (strcmp(command, "READY") == 0) {
    state.screen = Screen::Ready;
    dirty = true;
    return;
  }
  if (strcmp(command, "RESULT") != 0) {
    return;
  }

  const char* scoreText = strtok_r(nullptr, " ", &saveptr);
  const char* verdict = strtok_r(nullptr, " ", &saveptr);
  const char* reason = strtok_r(nullptr, " ", &saveptr);
  if (scoreText == nullptr || verdict == nullptr) {
    return;
  }

  state.score = constrain(atoi(scoreText), 0, 100);
  state.frames += 1;
  if (reason != nullptr) {
    strncpy(state.reason, reason, sizeof(state.reason) - 1);
    state.reason[sizeof(state.reason) - 1] = '\0';
  } else {
    strcpy(state.reason, "NONE");
  }

  if (strcmp(verdict, "PASS") == 0) {
    state.screen = Screen::Pass;
    ledPassUntil = millis() + LED_PULSE_MS;
  } else {
    state.screen = Screen::Retake;
    ledRetakeUntil = millis() + LED_PULSE_MS;
  }
  dirty = true;
}

void serviceSerial() {
  static char buffer[96];
  static size_t length = 0;

  while (Serial.available() > 0) {
    const char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (length > 0) {
        buffer[length] = '\0';
        handleLine(buffer);
        length = 0;
      }
      continue;
    }
    if (length < sizeof(buffer) - 1) {
      buffer[length++] = c;
    } else {
      length = 0;  // an overlong line is dropped rather than truncated into nonsense
    }
  }
}

}  // namespace

void setup() {
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_LED_PASS, OUTPUT);
  pinMode(PIN_LED_RETAKE, OUTPUT);
  digitalWrite(PIN_LED_PASS, LOW);
  digitalWrite(PIN_LED_RETAKE, LOW);

  Serial.begin(115200);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  // The HW I2C constructor is fixed at 0x3C; setI2CAddress after begin() has no effect.
  display.begin();

  display.clearBuffer();
  display.setFont(u8g2_font_helvB12_tr);
  const char* title = "AQUAVISION";
  display.drawStr((128 - display.getStrWidth(title)) / 2, 32, title);
  display.sendBuffer();
  delay(1500);

  lastPcMessage = millis();
  Serial.printf("EVT HELLO %s\n", "1.0");
  state.screen = Screen::Ready;
  dirty = true;
}

void loop() {
  const uint32_t now = millis();
  serviceSerial();
  serviceButton(now);
  serviceTurbidity(now);
  serviceHeartbeat(now);
  serviceLeds(now);
  serviceLink(now);
  if (dirty) {
    render();
  }
}
