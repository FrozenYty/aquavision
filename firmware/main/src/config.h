// Everything a person might want to change without reading the rest of the firmware.
//
// Pins and timings live here and nowhere else. If a wire moves, this file changes and nothing else
// does — that is the whole reason it exists.

#pragma once

#include <cstdint>

namespace cfg {

// ---------------------------------------------------------------------------- pins

constexpr int PIN_BUTTON = 4;      // to GND, INPUT_PULLUP: a press reads LOW
// The three lamps sit on the 5 V rail and the pin switches the low side, so **LOW lights a lamp and
// HIGH puts it out**. That is what makes them bright enough to read across a bench: from 3.3 V a 2 V LED
// has 1.3 V of headroom and 330 ohm leaves under 4 mA, while from 5 V the same resistor gives about 9 mA.
// The pin never sees 5 V - the LED is between it and the rail - and it sinks at most 9 mA.
constexpr int PIN_LED_PASS = 5;    // green, anode to +5 V, cathode through 330 ohm: LOW lights it
constexpr int PIN_LED_RETAKE = 6;  // yellow, the same
constexpr int PIN_LED_STATE = 7;   // blue, the same: the one that is always lit
constexpr int PIN_I2C_SDA = 8;
constexpr int PIN_I2C_SCL = 9;

// ---------------------------------------------------------------------------- i2c

constexpr uint8_t OLED_ADDR = 0x3C;
constexpr uint8_t TURBIDITY_ADDR = 0x49;

// ---------------------------------------------------------------------------- timing

constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 25;
constexpr uint32_t LED_PULSE_MS = 300;
// The blue state lamp is steady when the rig is idle, blinks slowly while a capture is in flight, and
// blinks fast when the link is gone. Two rates rather than one, because "busy" and "broken" are different
// questions, and a single pattern would make the operator read the panel twice to tell them apart.
constexpr uint32_t STATE_BLINK_MS = 500;
constexpr uint32_t FAULT_BLINK_MS = 150;
// The PC is required to send `CMD PING` at least every two seconds, so ten seconds of silence is five
// missed keepalives and therefore a real disconnection rather than an idle rig.
constexpr uint32_t OFFLINE_AFTER_MS = 10000;
// A capture that gets no verdict by then is reported as NO REPLY. Shorter than OFFLINE_AFTER_MS on
// purpose: the operator should learn that this shot failed before the whole link is declared dead.
constexpr uint32_t CAPTURE_TIMEOUT_MS = 5000;
constexpr uint32_t TURBIDITY_PERIOD_MS = 5000;
constexpr uint32_t HEARTBEAT_PERIOD_MS = 1000;
// The three-dot spinner on CAPTURING. Fast enough to read as motion, slow enough not to strobe.
constexpr uint32_t SPIN_PERIOD_MS = 250;
constexpr uint32_t SPLASH_MS = 1500;

// ---------------------------------------------------------------------------- identity

//: Bumped whenever the wire protocol or what the panel and lamps do changes, because `EVT HELLO` is how a
//: host knows which build is on the board - a feature added without a bump is a feature nobody can
//: confirm is running. 1.2 added the blue state lamp on GPIO7; 1.3 moved the lamps to the 5 V rail with
//: the pin switching the low side, which inverted what HIGH means for all three.
constexpr char FIRMWARE_VERSION[] = "1.3";

}  // namespace cfg
