// The rig's one line of I/O, behind an interface.
//
// `protocol` emits a line-oriented ASCII protocol and must not care which wire carries it. Today the wire is
// the UART the USB cable lands on; the finished rig has to run with no cable at all, so a Bluetooth service
// will implement the same four calls. Everything else - the parser, the state machine, the screens, the
// keepalive rule - is already transport-agnostic and does not change.
//
// The interface is deliberately `printf`-shaped rather than "write a string": rewriting fourteen call sites
// to build strings by hand would be a larger change than the seam it hides, and it would risk the byte-level
// output that the PC end and every test currently expect.

#pragma once

#include <cstdint>

namespace transport {

//: What `begin` reports. A radio that will not start has to be **reportable rather than fatal**: the rig
//: still runs, still draws its panel, and shows `Err4` - a dead radio is `Err0`'s lie with a plausible
//: face, because a rig nobody can reach looks exactly like a PC that stopped talking
//: (docs/rig-transport-en.md §8, §10).
enum class Result { Ok, Failed };

//: Opens the wire. Serial at the baud in `config.h` for now, and always `Ok`: a UART that is there at
//: boot is a UART that works, and this rig has never been able to see whether the cable is plugged in.
//: BLE starts the radio, registers the service and begins advertising, and returns `Failed` when the
//: stack refuses - the one thing a carrier can tell the layer above it.
Result begin();

//: Bytes waiting to be read. Zero when the wire is quiet.
int available();

//: One byte, or -1 when there is none.
int readByte();

//: Formats like `printf` and puts the bytes on the wire. Fragments are fine: `EVT PONG` goes out as two calls,
//: and the wire is a byte stream either way. Lines are short by design - the longest thing this firmware emits
//: is an `EVT INVARIANT` line, 29 bytes, and the longest routine one is `EVT SCREEN` at 24.
void printf(const char* format, ...);

//: Ends the current line. Bytes, not a newline convention: `Serial.println` writes `\r\n` and the PC end
//: strips both, so this writes `\r\n` too rather than quietly changing what is on the wire.
void newline();

//: True when the carrier itself is dead and waiting will not fix it: the radio did not start, or it has
//: dropped `cfg::BLE_DROP_STORM_LIMIT` times inside `cfg::BLE_DROP_STORM_WINDOW_MS` (§3 `Fault`).
//: **Serial always answers false** - a cable has no radio to fail, and a carry that cannot drop cannot
//: fault. The loop calls this once per iteration, so the BLE layer reads its own timers here instead of
//: running a second task for two deadlines; that is why this is the one accessor that is not a query
//: alone, and a carrier with no timers ignores it entirely.
bool faulted();

//: True **once** for each central that enables notifications, and cleared by the question; false on the
//: serial wire, where the peer is present or absent without an event to say so.
//:
//: It exists because a PC that has just subscribed has missed every line emitted while nobody was
//: listening - the boot `EVT HELLO`, the I2C scan, the starting screen - so the rig says where it is
//: instead of leaving the PC to infer it from the next change. **It is not a liveness claim**: a
//: subscription is a carrier fact, and the rig still calls the PC `Gone` after ten seconds without a
//: command, which is the separation §2 of the transport document insists on.
bool subscribed();

//: True while a central is attached and has not let go - the carrier fact the presentation layer reads
//: to tell "waiting for someone" from "someone left" (docs/rig-state-machine-en.md §11).
//:
//: **Serial always answers true**, and that is the honest answer rather than a shortcut: a UART is open
//: at boot and the rig cannot see whether a cable is plugged in (§2 of the transport document), so the
//: serial build boots `Live` or `NoLink` and never shows `WAITING`. It is not a liveness claim
//: either: an attached central that says nothing still makes the protocol layer `Gone`, and the
//: presentation layer is what keeps those two apart.
bool attached();

}  // namespace transport
