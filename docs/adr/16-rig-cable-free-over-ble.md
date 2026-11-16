# 16 — The finished rig is cable-free over BLE, and the serial build stays

- **Status:** Accepted
- **Date:** 2026-11-15
- **Decides:** the question recorded as `P3-38` — how the finished rig reaches the PC with no cable, and
  whether the serial transport is deleted once the radio works. The states, timings and failure faces are the
  contract in `docs/rig-transport-en.md` and `docs/rig-transport-zh.md`

## Context

The rig is a capture station on a desk and the PC is a separate machine, and today one USB cable does two jobs
at once: it powers the controller and it carries the protocol. `P3-38` fixes the end state — the assembled rig
runs from its own supply with no data cable to the PC — and the transport is the part of that which no amount
of bench work removes. BLE was chosen in that task's own text, and the reason is written there in one sentence
that is nowhere else in the repository: **the network available at the site is a campus one, either
WPA2-Enterprise or a browser portal, and an ESP32 can join neither without machinery it does not have.**

That sentence decides more than it looks like it does. A WPA2-Enterprise network needs an 802.1X supplicant,
an identity and a certificate behind it, and a clock roughly in step with the RADIUS server; a browser portal
needs a browser to open the page and authenticate, and the rig has no browser. Either one is a second product
living inside the firmware, with credentials an administrator can rotate and a failure mode that appears only
on the day. BLE asks for no network, no SSID, no password and no adapter on the rig's side, and nothing about
it can be changed by somebody who has never heard of this project.

Two seams already exist for exactly this change, and they are why the decision is a decision about a
transport rather than a redesign. The firmware reaches the wire only through `firmware/main/src/transport.h`
and `transport.cpp`, and `protocol.cpp` parses and emits lines without knowing what carries them. On the PC,
`server/app/rig/link.py` declares `Transport` as a `Protocol` with `readline`, `write` and `close`, and
`RigLink` takes an `open_transport` factory. **The transport changes; the language does not** — no line, no
state and no timing of the protocol moves.

The part that is expensive to reverse is not the radio. It is three things that would each be re-litigated by
the next person who finds them: that the protocol and the link are two state machines rather than one, that
the rig keeps a build that still speaks over the cable, and that a dead radio has its own code on the panel.

## Decision

**The finished rig speaks the same line-oriented protocol over BLE, carried by a BLE layer that owns the
connection and the notification subscription and nothing else.** The BLE layer changes at power-up and on a
drop; the protocol layer keeps `Alive`/`Gone`, the two-second keepalive and the four-second capture timeout,
and it changes every two seconds. They are not merged, because merging them forces a choice between
"reconnect" and "resume talking" that corresponds to nothing real: a PC that stops sending commands has not
dropped the connection — the link layer keeps an idle connection alive with empty packets — and a connection
that drops does not mean the PC is dead. The serial link never had a carrier signal, which is why liveness
has always been the protocol's job; BLE does have one, and that fact belongs to the BLE layer as an addition,
not as a replacement.

**`rig-serial` survives as a build variant, and the wire protocol, the panel and the version string are shared
between the two targets.** The serial build keeps flashing, keeps being compiled, and keeps owning bench work:
every wiring change is tested over the cable with `scripts/test_rig_link.py --port COM<n> --scan`, and a
misbehaving radio must cost thirty seconds and one cable rather than the demonstration. `rig-ble` writes the
protocol to BLE and nothing to the UART, so a plugged-in cable cannot look like it is doing something.

**A radio that failed to start is `Err4` on the panel, and it has no window.** It is distinguishable from
`Err0` (the link lost) because both are true at the same moment and only one of them tells the operator what
to do: waiting for the link to come back is the right response to `Err0` and the wrong one to `Err4`. `Err4`
uses the alphabet the panel already has, and the OLED — which has no code face — draws the radio fault itself
instead of the `Offline` screen underneath. The `Err0` line `CHECK USB CABLE` becomes build-dependent,
because in `rig-ble` it would point at a cable that does not exist.

**The PC never retries without a bound.** The BLE client has a `Failed` state after five attempts, and the
firmware drops to `Fault` after five disconnects inside a minute. An unbounded reconnect loop makes a broken
link look like a working one: the log fills, the page says "reconnecting", and no state ever admits that this
is not going to work.

## Alternatives considered

**WiFi with WPA2-Enterprise.** The transport everyone reaches for first, and the one the site's network
refuses. It needs an 802.1X supplicant, a certificate and its trust chain on the board, somewhere to keep
them, and a clock close enough to the server's for the certificate check; then it needs DHCP, an IP address
and a listening port, and the PC needs to know how to find the rig on a campus subnet that may or may not
allow peer-to-peer traffic between two clients. All of that machinery exists to carry thirty bytes every two
seconds. Rejected: it is more moving parts than the feature, and every one of them is owned by somebody else.

**WiFi with a browser portal.** Worse than it looks, because the portal is a web page: something has to fetch
it, follow the redirect and post the credentials. A controller with no browser can approximate this with an
HTTP client and a hardcoded form, and it will work until the portal vendor changes the form. Rejected for the
same reason as the line above, plus the failure appears on the day rather than on the bench.

**A phone hotspot or a travel router at the site.** The cheapest answer that needs no firmware change at all:
join a network this project controls. Rejected because it is a second device to power, configure and carry,
with its own password to keep, and because the demonstration then depends on a device that is not part of the
project. It stays available as a fallback for a WiFi variant that does not exist.

**BLE and delete the serial transport once it works.** The tidiest reading of "the finished rig is
cable-free", and the one this ADR rejects. Deleting it means the only path to the rig is the radio, so any
radio problem — an adapter missing on the demonstration laptop, a driver update, a stack that will not bond —
becomes a problem with the demonstration rather than a problem with the transport. Keeping it costs a build
target and one `#ifdef`; the fallback is worth more than the tidiness, and it is only a fallback if it still
compiles and is still used, which is why it owns the bench work rather than a comment.

**One state machine for the link and the protocol.** Fewer states, one place to look, and it is wrong in both
directions at once: the rig would flash `Err0` for a two-second radio hiccup, or keep drawing `Ready` on a rig
nobody can reach. Rejected — see the Decision above.

**Keep the cable and put the rig on a longer one.** Honest, free, and it does not solve the problem the task
states: the rig has to stand where the tank is, and the cable is the thing being removed. Rejected, while
noting that this is the fallback that requires no decision at all.

**A BLE-to-serial bridge dongle on the rig's UART.** No firmware change and no PC-side stack work: the rig
stays a serial device and the dongle hides the radio. Rejected as the primary answer because it is a second
radio to power and pair, it holds a cable to the rig anyway, and its pairing is another thing to get wrong on
the day — but it is the first thing to reach for if the on-board stack proves unreliable, and it is why the
serial build must keep working.

## Consequences

- `docs/rig-transport-en.md` and `-zh.md` become the contract: the two state machines, both transition
  matrices, the timings with their measured-versus-assumed status, and the failure faces.
- The firmware gains a BLE layer, a `Fault::Radio` and an `Err4` face, and `transport::begin()` has to be able
  to report a radio that did not start. The protocol layer, the parser, the keepalive and the five screens do
  not change.
- The PC gains a BLE client with its own state machine and a `Transport` implementation. `link.py` is not
  edited: the client returns a transport only in `Streaming` and raises otherwise, so the existing invariant —
  a transport exists if and only if the state is `OPEN` — keeps holding one layer down.
- `firmware/main/platformio.ini` gains a second environment. Two targets means every firmware change is
  compiled twice, which is the cost of the fallback and is paid on purpose.
- The OLED's `OFFLINE` copy becomes build-dependent, and the OLED gains a radio-fault face. Both are firmware
  changes this decision requires and neither is optional: a face that contradicts the panel is worse than no
  face.
- **The connect time on the demonstration laptop is unmeasured, and it is the first thing the implementation
  measures.** Every timing in the transport document except the keepalive is a decision or an assumption; the
  20-second scan and connect budget comes from `P3-38`'s platform observation, not from a stopwatch. A number
  nobody has must not be reported as a measurement.
- The demonstration gains two dependencies it did not have: a BLE adapter on the PC, and a rehearsal that
  includes a dry run over BLE as well as the fallback drill. `P4-07`'s three rehearsals are not complete until
  both have been run.
- `P3-38` stays open. This record decides the shape; the implementation, the measurement and the rehearsal are
  what close it.

## Revisit when

The site's network becomes joinable — an open network, a pre-shared key, or a wired port at the desk — at
which point WiFi is cheap again and the BLE layer's reason for existing has to be re-read rather than assumed.
Or the rig needs to carry something bigger than a line: images, logs or a firmware update over the air would
each want a transport with real throughput, and notifications are not that transport. Or Windows BLE proves
unreliable enough in rehearsal that a bridge dongle on the UART is the better answer — the serial build is
what makes that a thirty-second change rather than a rewrite.
