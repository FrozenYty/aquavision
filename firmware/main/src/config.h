// Everything a person might want to change without reading the rest of the firmware.
//
// Pins and timings live here and nowhere else. If a wire moves, this file changes and nothing else
// does — that is the whole reason it exists.

#pragma once

#include <cstdint>

namespace cfg {

// ---------------------------------------------------------------------------- pins

constexpr int PIN_BUTTON = 4;      // to GND, INPUT_PULLUP: a press reads LOW
//: The four-digit seven-segment display is **common anode**: a digit's common pin driven HIGH selects
//: that digit, and a segment pin driven LOW lights that segment. Each segment has its own 240 ohm
//: resistor between the pin and the segment; the commons have none, so a common carries the sum of its
//: digit's segment currents and **only one common may be high at any moment**.
constexpr uint8_t SEGMENT_PINS[7] = {3, 13, 14, 15, 16, 17, 18};  // segments A, B, C, D, E, F, G
constexpr uint8_t DIGIT_PINS[4] = {5, 6, 7, 10};  // digit commons 1-4, digit 1 (left) first
constexpr int PIN_I2C_SDA = 8;
constexpr int PIN_I2C_SCL = 9;

// ---------------------------------------------------------------------------- i2c

constexpr uint8_t OLED_ADDR = 0x3C;

// ---------------------------------------------------------------------------- timing

constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 25;
//: The PC is required to send `CMD PING` at least every two seconds, and **this is the unit the link
//: intervals are multiples of**: two is the capture timeout, five the offline threshold and six the verdict
//: face, with one for the fault face. They are written as products of it on purpose - a keepalive that
//: changes must move all of them with it, and this is the one number that cannot be edited alone.
constexpr uint32_t PC_KEEPALIVE_MS = 2000;
// Silence for five keepalives is a real disconnection rather than an idle rig - enough to ride out a busy
// PC without flashing `Offline` at a hiccup, at the cost of up to ten seconds of stale display.
constexpr uint32_t OFFLINE_AFTER_MS = 5 * PC_KEEPALIVE_MS;
// A capture that gets no verdict by then is reported as NO REPLY: the PC's answer normally lands inside a
// second, so two keepalives leave it ample room and still tell the operator early that this shot failed.
// Shorter than OFFLINE_AFTER_MS on purpose.
constexpr uint32_t CAPTURE_TIMEOUT_MS = 2 * PC_KEEPALIVE_MS;
constexpr uint32_t HEARTBEAT_PERIOD_MS = 1000;  // the OLED's header dot, not the PC keepalive
// The display lights one digit at a time, 250 us each, so the whole panel is refreshed at about 1 kHz -
// above the flicker the eye can see, which is what makes four multiplexed digits read as four steady
// ones. The pacing below is a rule rather than a set of numbers: **what is working runs at a steady pace,
// what failed blinks at a warning pace, and nothing on a desk instrument exceeds about 1 Hz.** The boot
// self-test walks one segment at a time and then settles, READY walks one dash along the four positions,
// CAPTURING turns the digit a quarter second at a step, PASS wipes left to right once, and RETAKE and every
// one of the fault codes blink at one hertz.
constexpr uint32_t DISPLAY_DIGIT_US = 250;
//: The display's base unit. **Every face interval below is an integer multiple of it**, written as a
//: product so that any of them divides by this and gives a whole number - the sweep is one unit per
//: segment, the settled eights are twelve, the blank is forty, and so on. The digit period above is a
//: hardware figure in microseconds and stays out of this scheme; this unit governs the faces.
constexpr uint32_t DISPLAY_UNIT_MS = 25;
// The self-test: one unit per segment through the twenty-eight positions - 700 ms - then the settled `8888`
// for twelve units, then forty units of dark. The dark phase is the largest of the three because it is the
// part that went by too fast to be seen, and two seconds is the shortest total that holds both a sweep slow
// enough to show which segment is dead and a blank long enough to register. Sequential rather than a static
// row of eights, because a dead segment then shows as a gap at a known position in the sweep.
constexpr uint32_t DISPLAY_BOOT_SWEEP_MS = 1 * DISPLAY_UNIT_MS;
constexpr uint32_t DISPLAY_BOOT_TEST_MS = 12 * DISPLAY_UNIT_MS;
constexpr uint32_t DISPLAY_BOOT_BLANK_MS = 40 * DISPLAY_UNIT_MS;
// READY walks one dash along the four positions - 1, 2, 3, 4 and back to 1 - twenty units at each, so the
// cycle is two seconds. The dash starts over at the first digit rather than turning round: **that wrap is
// deliberate**, a conveyor with a visible break, not a defect to be "fixed" into a bounce. No frame is ever
// dark and no more than one dash is ever lit; it cannot be mistaken for OFFLINE either, because that face
// is the code `Err0`.
constexpr uint32_t DISPLAY_READY_STEP_MS = 20 * DISPLAY_UNIT_MS;
constexpr uint32_t DISPLAY_ROTATE_MS = 10 * DISPLAY_UNIT_MS;
//: The rotating indicator has six steps on both screens: the panel's segment walks the digit's six rim
//: segments A-F clockwise, and the OLED fills one of six dots above the banner in that same order. One
//: constant, so the two cannot end up with different step counts. `Pairing`'s fourth digit uses this same
//: rotation, from the same expression `CAPTURING` uses.
constexpr uint8_t DISPLAY_ROTATE_STEPS = 6;
// The arrival sweep is ten units, so the score lands a quarter second after the verdict arrives.
constexpr uint32_t DISPLAY_SWEEP_MS = 10 * DISPLAY_UNIT_MS;
// One hertz, half a second either way: the RETAKE warning, and every fault code. The codes all blink at
// this same rate - see `faultMask` - so the rhythm carries no information.
constexpr uint32_t DISPLAY_BLINK_MS = 20 * DISPLAY_UNIT_MS;
// A fault takes the panel for one keepalive - two seconds, forty units: those events used to be swallowed
// and silence looks exactly like a healthy rig, and a four-character code is read well inside two seconds.
constexpr uint32_t FAULT_FACE_MS = 1 * PC_KEEPALIVE_MS;
// A verdict is a conclusion, not a permanent label: six keepalives after the verdict the panel goes back to
// the idle face. The number is `OFFLINE_AFTER_MS` plus one keepalive, and that relationship is the point:
// **a verdict outlives the link-loss threshold on purpose**, so the link is always reported before a
// verdict clears on its own. Were it the other way round, a dead link would first look like an ordinary
// return to idle, and the operator would be shown a healthy panel for two seconds after the rig had
// stopped talking. Nothing else is lost by moving on - the OLED tally keeps the session and the PC keeps
// the record, and the panel's job is the present state. OFFLINE is deliberately excluded: a lost link is a
// fault, not a completion, and it stays visible until the link returns.
constexpr uint32_t VERDICT_FACE_MS = 6 * PC_KEEPALIVE_MS;

// ---------------------------------------------------------------------------- ble

//: Which carrier this build runs. The build environment defines it - `rig-ble` sets `AV_BLE_CARRIER` -
//: and nothing sets it by hand: two builds of one firmware that disagree about their own wire is the
//: failure this flag exists to prevent. It selects the OLED's offline line, which is the one string on
//: the panel that is false in the other build (docs/rig-transport-en.md §10, §11).
#ifdef AV_BLE_CARRIER
constexpr bool BLE_CARRIER = true;
#else
constexpr bool BLE_CARRIER = false;
#endif

//: The advertised name is ours; the three UUIDs are not. This is the Nordic UART Service, a de-facto
//: standard, so a phone app or a terminal that speaks NUS reaches the rig without a profile of our own:
//: the central writes to the RX characteristic and the rig notifies on TX. Both ends read these strings -
//: `server/app/rig/ble.py` carries the same four - and they are written down here rather than in the
//: transport because a name is an identity, not a pin.
constexpr char BLE_NAME[] = "AQUAVISION";
constexpr char BLE_SERVICE_UUID[] = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E";
constexpr char BLE_RX_UUID[] = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E";
constexpr char BLE_TX_UUID[] = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E";

//: A central that connects and never subscribes is dropped after ten seconds (§5 rule 2): five
//: keepalives, and deliberately longer than the PC's own five-second subscription timeout, so that in the
//: ordinary failure the PC's timer fires first and the operator reads a PC-side timeout rather than a
//: rig-side eviction.
constexpr uint32_t BLE_SUBSCRIBE_GRACE_MS = 5 * PC_KEEPALIVE_MS;
//: Five disconnects inside sixty seconds - thirty keepalives - is a fault, not a link a sixth attempt
//: will fix (§5 rule 5). The state stays `Advertising` and this count carries the decision.
constexpr uint32_t BLE_DROP_STORM_WINDOW_MS = 30 * PC_KEEPALIVE_MS;
constexpr uint8_t BLE_DROP_STORM_LIMIT = 5;

//: The MTU this end asks for. A protocol line is under forty bytes, so any MTU above 43 - forty plus the
//: three-byte notification header - carries one in a single notification; 247 is what most stacks accept
//: and it is well under the 512 an attribute may hold. The measured figure is what matters, not this one:
//: the peer may grant less, and `transport_ble.cpp` splits a line to whatever was negotiated.
constexpr uint16_t BLE_PREFERRED_MTU = 247;
//: How often the loop asks to advertise again while a return to `Advertising` has not taken. A restart
//: immediately after a disconnect can be refused while the host finishes that disconnect, and a refused
//: restart that is never retried is a rig that is running and cannot be found. Fast enough to be
//: findable a moment later, slow enough not to spin at loop rate.
constexpr uint32_t BLE_ADVERTISE_RETRY_MS = 250;

// ---------------------------------------------------------------------------- identity

//: Bumped whenever the wire protocol or what the panel shows changes, because `EVT HELLO` is how a host
//: knows which build is on the board - a feature added without a bump is a feature nobody can confirm is
//: running. 1.2 added the blue state lamp on GPIO7; 1.3 moved the lamps to the 5 V rail with the pin
//: switching the low side, which inverted what HIGH means for all three; 1.4 made the lamps follow the
//: screen instead of pulsing for 300 ms, so the two verdict lamps are steady while their verdict is shown;
//: 1.5 made the turbidity read address a register instead of reading whatever the pointer happened to hold;
//: 1.6 added `CMD TREAD`, which is how that register's command byte was found and how it stays findable;
//: 1.7 added `CMD TDUMP`, because two bytes turned out to be byte-identical in air and in water and the whole
//: frame had to be seen.
//: 1.12 removed all three: the vendor published no register map, a full sweep of the address space on a bus
//: that was proven clean found nothing that followed the light, and the sensor left with the bench commands it
//: had needed. The four-digit seven-segment display now sits on GPIO 3 and 13-18 for its segments, with its
//: digit commons on 5, 6, 7 and 10.
//: Turbidity is history from 1.12 on: 1.5-1.7 above are the record of what those builds did, not a description
//: of this one, and nothing they name is still in the firmware.
//: 1.13 puts the score and the process states on that display. The boot self-test walks all 28 segments one
//: at a time and then settles on eights; READY walks one dash along the four positions and starts over;
//: CAPTURING shows `CAP` with a segment turning in the fourth digit; PASS wipes left to right once and then
//: shows the score right-aligned with `P`, and RETAKE blinks the same with `F`; the faults that used to be
//: swallowed are the codes `Err0` a lost link, `Err1` a capture timeout, `Err2` a stray result and `Err3` a
//: broken invariant, all four blinking at one hertz, and a verdict goes back to READY after
//: `cfg::VERDICT_FACE_MS`. The button has one meaning - a press captures - and the multiplexer runs in a
//: hardware timer, so an OLED transfer cannot stall the panel. Both screens read one boot clock, so the
//: splash is held until the panel's self-test has finished. The
//: ten-lamp bar never shipped, and the display's commons are the pins the three status lamps sat on, so
//: this build retires those as well.
//: 1.14 adds the presentation layer (docs/rig-state-machine-en.md §11): with no central attached the
//: OLED says `WAITING FOR PC` and the panel keeps the ordinary READY marquee, instead of drawing `Err0`
//: at a rig where nothing is wrong; `Err0` now means a PC was attached and left. The wire is unchanged.
//: 1.15 was never flashed: on sight the bench rejected the reversed-direction marquee as too weak a
//: distinction, because two dashes moving opposite ways look the same out of the corner of the eye.
//: 1.16 replaced that animation and the four-dot row with one large ring around all four digits: twelve
//: stops, 250 ms each, clockwise - the `CAPTURING` rotation at four times the scale - mirrored by a dot
//: travelling the OLED's border, where the frame is sent once and only the two changing dots after it.
//: 1.17 makes the cursor a snake with a body, and puts `WAITING FOR PC` in the same inverted status face
//: as `OFFLINE` and `RADIO FAULT` instead of a third layout of its own. **1.18 was built but never
//: flashed**: it replaced the partial tile update with a full frame per step and the border snake with a
//: row of twelve cells.
//: 1.19 is the fix for what the glass showed: the ring's position table had **two entries for the fourth
//: digit's bottom and none for the first digit's**, so one position never appeared and another appeared
//: twice - a table is a place to be wrong. The ring and everything built on it are gone; the panel draws a
//: three-letter word with the fourth digit rotating through the same six segments `CAPTURING` turns, and
//: the OLED draws `WAITING FOR PC` as `OFFLINE`'s face with no moving element at all.
//: 1.20 changes that word from `PAr` to `APP` - it names the PC-side application the operator is about to
//: open, which is the action this state waits for, where `PAr` named the act of pairing - and shortens the
//: waiting title to `WAITING`. **The title shrank because of the character count, not the font**: thirteen
//: characters did not fit the house's bold 12, and setting it smaller to fit is what made the face read as
//: empty; the body line already carries `NO LINK TO PC`. The waiting face and `OFFLINE` are now the same
//: face and the same size, and differ only in their words.
constexpr char FIRMWARE_VERSION[] = "1.20";

}  // namespace cfg