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
// **Colour is a convention here, not a requirement**, and this set was chosen on three grounds.
// White marks PASS: it is the brightest thing available at 9 mA and carries no bad news. Yellow marks
// RETAKE, because that is the signal nobody may miss and yellow is the conventional warning colour. Blue
// marks the state, because an always-on lamp must recede - white there would dominate the two that matter,
// and it blooms into a featureless blob on a phone camera.
// Green was the obvious choice for PASS and was given up twice over: the parts on hand were too dim at 9 mA
// to read from a metre, and red against green is the one pair a red-green colour-blind operator cannot
// separate. A red lamp was the first choice for RETAKE and was set aside on the bench for a mechanical
// reason, not an optical one: its leads were too short to seat beside the other two. **White and yellow are
// therefore the closest pair in this set**, so position - not hue - is what separates the two verdict lamps
// at a glance, which is why they sit in fixed, labelled rows.
constexpr int PIN_LED_PASS = 5;    // white, anode to +5 V, cathode through 330 ohm: LOW lights it
constexpr int PIN_LED_RETAKE = 6;  // yellow, the same
constexpr int PIN_LED_STATE = 7;   // blue, the same
constexpr int PIN_I2C_SDA = 8;
constexpr int PIN_I2C_SCL = 9;

// ---------------------------------------------------------------------------- i2c

constexpr uint8_t OLED_ADDR = 0x3C;
constexpr uint8_t TURBIDITY_ADDR = 0x49;

// ---------------------------------------------------------------------------- timing

constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 25;
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
//: the pin switching the low side, which inverted what HIGH means for all three; 1.4 made the lamps follow
//: the screen instead of pulsing for 300 ms, so the two verdict lamps are steady while their verdict is shown.
constexpr char FIRMWARE_VERSION[] = "1.4";

}  // namespace cfg