#include "presentation.h"

#include "config.h"

namespace {

using presentation::Cell;
using presentation::Event;
using presentation::Face;
using presentation::Outcome;
using presentation::State;

//: The four kinds of cell, named once so a row reads like the document's. `Ignored` and `Handled` carry
//: a target that is never used; they keep the table's cell type uniform, and the `target` is only read
//: for `Move` and `Rejected` (which names the state the layer stays in).
constexpr Cell kIgnored{Outcome::Ignored, State::Pairing};
constexpr Cell kHandled{Outcome::Handled, State::Pairing};
constexpr Cell kToPairing{Outcome::Move, State::Pairing};
constexpr Cell kToNoLink{Outcome::Move, State::NoLink};
constexpr Cell kToLive{Outcome::Move, State::Live};
constexpr Cell kToRadioFault{Outcome::Move, State::RadioFault};

//: §11, row by row and in the document's column order B1..P2. A table rather than a chain of `if`s, so
//: a reader - and the test - can check it against the document cell by cell, which is the whole point
//: of a matrix with no empty cells.
//:
//: `NoLink`'s P2 cell is §11's "already here": the state already says this, so the event is consumed
//: and nothing changes, which is `Handled` in the shared vocabulary. `Live`'s B1 cell is `Rejected`
//: because a second central must not repaint a live screen; the BLE layer has already disconnected
//: that central, and this cell is what keeps the presentation from following it.
constexpr Cell kMatrix[4][6] = {
    // B1 attached, B2 subscribed, B3 detached, B4 fault, P1 command, P2 silence
    {kToNoLink, kIgnored, kIgnored, kToRadioFault, kIgnored, kIgnored},  // Pairing
    {kIgnored, kToLive, kToPairing, kToRadioFault, kToLive, kHandled},   // NoLink
    {{Outcome::Rejected, State::Live}, kIgnored, kToPairing, kToRadioFault, kHandled,
     kToNoLink},                                                          // Live
    {kIgnored, kIgnored, kIgnored, kHandled, kIgnored, kIgnored},        // RadioFault
};

//: §11's face table. `Pairing` draws `PAr` with the fourth digit rotating, because the rig really is
//: ready and only the link detail differs; `NoLink` keeps the `OFFLINE` box and `Err0` because a PC
//: was there and left, which is worth reporting; `RadioFault` keeps `Err4`/`RADIO FAULT` because that
//: is the one fault no protocol event can report. `Live` is the only row that hands the glass back to
//: `state.screen`, and that is what makes the outranking rule structural.
constexpr Face kFaces[4] = {
    {presentation::OledFace::WaitingForPc, presentation::PanelFace::Pairing},  // Pairing
    {presentation::OledFace::Offline, presentation::PanelFace::Err0},          // NoLink
    {presentation::OledFace::RigScreen, presentation::PanelFace::RigScreen},   // Live
    {presentation::OledFace::RadioFault, presentation::PanelFace::Err4},       // RadioFault
};

constexpr State kInitialState = State::Pairing;

State current = kInitialState;

}  // namespace

namespace presentation {

State state() { return current; }

void begin(bool attached, bool protocolAlive) {
  if (!attached) {
    current = State::Pairing;
  } else {
    current = protocolAlive ? State::Live : State::NoLink;
  }
}

Cell apply(Event event) {
  const Cell cell = kMatrix[static_cast<uint8_t>(current)][static_cast<uint8_t>(event)];
  if (cell.outcome == Outcome::Move) {
    current = cell.target;
  }
  // `Rejected` changes nothing and is not logged: this layer has no wire, and the refusal an operator
  // has to learn about is the second central's, which the BLE layer reports by disconnecting it. The
  // cell still matters - it is the reason a second attach cannot repaint a `Live` screen.
  return cell;
}

const Face& faceFor(State state) { return kFaces[static_cast<uint8_t>(state)]; }

uint8_t rotationStep(uint32_t faceAgeMs) {
  // One clock for the two faces that rotate: `CAPTURING` and `Pairing`. Derived from the age, never
  // advanced by a counter - a counter loses a step whenever an iteration runs long, and the two would
  // then disagree about which segment is lit.
  return static_cast<uint8_t>((faceAgeMs / cfg::DISPLAY_ROTATE_MS) % cfg::DISPLAY_ROTATE_STEPS);
}

}  // namespace presentation
