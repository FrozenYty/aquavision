// Everything a person might want to change without reading the rest of the firmware.
//
// Pins and timings live here and nowhere else. If a wire moves, this file changes and nothing else
// does — that is the whole reason it exists.

#pragma once

#include <cstdint>

namespace cfg {

// ---------------------------------------------------------------------------- pins

constexpr int PIN_BUTTON = 4;      // to GND, INPUT_PULLUP: a press reads LOW
constexpr int PIN_LED_PASS = 5;    // green, 330 ohm to GND
constexpr int PIN_LED_RETAKE = 6;  // yellow, 330 ohm to GND
constexpr int PIN_I2C_SDA = 8;
constexpr int PIN_I2C_SCL = 9;

// ---------------------------------------------------------------------------- i2c

constexpr uint8_t OLED_ADDR = 0x3C;
constexpr uint8_t TURBIDITY_ADDR = 0x49;

// ---------------------------------------------------------------------------- timing

constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 25;
constexpr uint32_t LED_PULSE_MS = 300;
constexpr uint32_t OFFLINE_AFTER_MS = 10000;  // silence from the PC for this long flips to OFFLINE
// A capture that gets no verdict by then is reported as NO REPLY. Shorter than OFFLINE_AFTER_MS on
// purpose: the operator should learn that this shot failed before the whole link is declared dead.
constexpr uint32_t CAPTURE_TIMEOUT_MS = 5000;
constexpr uint32_t TURBIDITY_PERIOD_MS = 5000;
constexpr uint32_t HEARTBEAT_PERIOD_MS = 1000;
// The three-dot spinner on CAPTURING. Fast enough to read as motion, slow enough not to strobe.
constexpr uint32_t SPIN_PERIOD_MS = 250;
constexpr uint32_t SPLASH_MS = 1500;

// ---------------------------------------------------------------------------- identity

constexpr char FIRMWARE_VERSION[] = "1.1";

}  // namespace cfg
