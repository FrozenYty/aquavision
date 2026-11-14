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
// Red marks RETAKE, because the lamp that says "shoot it again" is the one that must not be missed and red
// is the colour a reader already stops for. White marks PASS: it is the brightest thing available at 9 mA
// and carries no bad news. Blue marks the state, because an always-on lamp must recede - white there would
// dominate the two that matter, and it blooms into a white blob on a phone camera.
// Green for PASS was the obvious choice and was given up twice over: the parts on hand were too dim at 9 mA
// to read from a metre, and red against green is the one pair a red-green colour-blind operator cannot
// separate. Red, white and blue differ in brightness as well as hue.
constexpr int PIN_LED_PASS = 5;    // white, anode to +5 V, cathode through 330 ohm: LOW lights it
constexpr int PIN_LED_RETAKE = 6;  // red, the same
constexpr int PIN_LED_STATE = 7;   // blue, the same
constexpr int PIN_I2C_SDA = 8;
constexpr int PIN_I2C_SCL = 9;
// The score bar is ten more of the same low-side lamps: the anode goes to the 5 V rail through 330 ohm and
// the cathode to the pin, so **LOW lights a lamp and HIGH leaves it dark**, exactly as with the three above.
// Ten lamps rather than one brightness, because a bar is counted at a glance from across a room, while the
// brightness of a single lamp has to be compared against something to mean anything.
// The pins are GPIO 10-18 and then GPIO 21: the list is not contiguous because 19 and 20 are the USB pair.
//: Only two colours, and the count is the signal: the bar runs yellow for everything up to 70 and white for
//: the top band, 80 and above (index 0-6 yellow, 7-9 white). Red was dropped because the bench's red LEDs are
//: a different height, and a row of mismatched lamps reads as damage rather than as design. Blue is still
//: deliberately absent: it belongs to the state lamp, so a blue segment would be misread as "the rig is idle".
//: Pass and fail stay with the two separate verdict lamps, which are not in this row.
constexpr uint8_t PIN_BAR_FIRST = 10;  // bar lamp 0; the rest of the order is in `PIN_BAR` below
constexpr uint8_t BAR_LEDS = 10;
constexpr uint8_t PIN_BAR[BAR_LEDS] = {PIN_BAR_FIRST, 11, 12, 13, 14, 15, 16, 17, 18, 21};

// ---------------------------------------------------------------------------- i2c

constexpr uint8_t OLED_ADDR = 0x3C;

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
constexpr uint32_t HEARTBEAT_PERIOD_MS = 1000;
// The three-dot spinner on CAPTURING. Fast enough to read as motion, slow enough not to strobe.
constexpr uint32_t SPIN_PERIOD_MS = 250;
// The score bar's two animations: the READY dot moves one lamp per step, and the CAPTURING fill adds one
// lamp per step before starting over. Both carry their meaning in the movement itself, so neither may
// stutter - a step slower than this reads as a stalled rig, and a faster one as a flicker.
constexpr uint32_t BAR_SWEEP_PERIOD_MS = 150;
constexpr uint32_t BAR_FILL_PERIOD_MS = 80;
constexpr uint32_t SPLASH_MS = 1500;

// ---------------------------------------------------------------------------- identity

//: Bumped whenever the wire protocol or what the panel and lamps do changes, because `EVT HELLO` is how a
//: host knows which build is on the board - a feature added without a bump is a feature nobody can
//: confirm is running. 1.2 added the blue state lamp on GPIO7; 1.3 moved the lamps to the 5 V rail with
//: the pin switching the low side, which inverted what HIGH means for all three; 1.4 made the lamps follow
//: the screen instead of pulsing for 300 ms, so the two verdict lamps are steady while their verdict is shown;
//: 1.5 made the turbidity read address a register instead of reading whatever the pointer happened to hold;
//: 1.6 added `CMD TREAD`, which is how that register's command byte was found and how it stays findable;
//: 1.7 added `CMD TDUMP`, because two bytes turned out to be byte-identical in air and in water and the whole
//: frame had to be seen.
//: 1.12 removed all three: the vendor published no register map, a full sweep of the address space on a bus
//: that was proven clean found nothing that followed the light, and the sensor left with the bench commands it
//: had needed. The ten-lamp score bar now sits on GPIO 10-18 and 21.
//: Turbidity is history from 1.12 on: 1.5-1.7 above are the record of what those builds did, not a description
//: of this one, and nothing they name is still in the firmware.
constexpr char FIRMWARE_VERSION[] = "1.12";

}  // namespace cfg