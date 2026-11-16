// The Bluetooth implementation of `transport` - the `rig-ble` wire (docs/rig-transport-en.md).
//
// The rig's language is unchanged: the same bytes, the same lines, carried by a GATT notification
// instead of a UART, and nothing above `transport.h` can tell which one it is on. What this file adds is
// the layer the document writes out in §3 and §4 - five states, seven events, every cell decided - plus
// the two rules the protocol layer must not own: **only one central at a time**, and a central that
// connects and never subscribes is dropped, because otherwise one idle client holds the rig and the real
// PC can never get in.
//
// **This build writes nothing to the UART** (§11). The USB port stays for flashing and for the ROM's own
// output; a build that mirrored the protocol to both wires would be the two-carriers problem one cable
// away, and it would leave the cable looking like it still works.
//
// The service is the Nordic UART Service: the central writes to the RX characteristic, the rig notifies
// on TX. No pairing, no bonding and no passkey - a pairing prompt during a demonstration is a delay of
// unknown length, and this rig is not a security boundary.

#include "transport.h"

#include <Arduino.h>
#include <BLEAdvertising.h>
#include <BLEDevice.h>
#include <BLEServer.h>

#include <cstdarg>
#include <cstdint>
#include <cstdio>

#include "config.h"

namespace {

// The layer's five states (§3). `Idle` and `Advertising` are the only ones with no peer; `Fault` is the
// only one that does not recover on its own.
enum class State : uint8_t { Idle, Advertising, Connected, Streaming, Fault };

//: The seven events (§3). `Command` is here even though this layer never parses anything: its cell is the
//: one that says a command is **not** a BLE event. Nothing raises it, and that is safe for a reason worth
//: writing down - every cell of its column is `handled in place` or `ignored`, so an event that is never
//: delivered and an event that does nothing are the same thing here.
enum class Event : uint8_t {
  Connect,
  Disconnect,
  Subscribe,
  Unsubscribe,
  Command,
  IdleTimeout,
  InitFailure,
};

//: What a cell does. `Ignored` cannot move this layer and is not reported; `Handled` is consumed without a
//: state change; `Rejected` keeps the state *and* reports, because the sender has to learn it was
//: refused; `Move` is a transition.
enum class Outcome : uint8_t { Ignored, Handled, Rejected, Move };

struct Cell {
  Outcome outcome;
  State target;
};

constexpr Cell kIgnored{Outcome::Ignored, State::Idle};
constexpr Cell kHandled{Outcome::Handled, State::Idle};
constexpr Cell kToAdvertising{Outcome::Move, State::Advertising};
constexpr Cell kToFault{Outcome::Move, State::Fault};

//: §4, row by row and in the document's column order F1..F7. A table rather than a chain of `if`s, so a
//: reader can check it against the document cell by cell - which is the whole point of a matrix that has
//: no empty cells.
constexpr Cell kMatrix[5][7] = {
    // F1 connect, F2 disconnect, F3 subscribe, F4 unsubscribe, F5 command, F6 idle timeout, F7 init failure
    {kIgnored, kIgnored, kIgnored, kIgnored, kIgnored, kIgnored, kToFault},                     // Idle
    {{Outcome::Move, State::Connected}, kIgnored, kIgnored, kIgnored, kIgnored, kIgnored, kToFault},   // Advertising
    {{Outcome::Rejected, State::Connected}, kToAdvertising, {Outcome::Move, State::Streaming}, kIgnored,
     kIgnored, kToAdvertising, kToFault},                                                       // Connected
    {{Outcome::Rejected, State::Streaming}, kToAdvertising, kHandled, {Outcome::Move, State::Connected},
     kHandled, kIgnored, kToFault},                                                             // Streaming
    {kIgnored, kIgnored, kIgnored, kIgnored, kIgnored, kIgnored, kHandled},                     // Fault
};

//: The handle that means "no peer": `dispatch` takes one only for the two events a radio callback carries
//: a peer with.
constexpr uint16_t kNoHandle = 0xFFFF;

//: Everything the layer knows, behind one lock: the NimBLE host task runs the callbacks and the Arduino
//: loop runs the protocol, and the two ask about the same state.
struct Layer {
  State state = State::Idle;
  //: The central that holds the rig. One at a time: a second connection is refused rather than shared.
  uint16_t connHandle = kNoHandle;
  //: When the idle timer was armed, and whether it is armed at all. Armed by F1, disarmed by F3 (§5 rule
  //: 2); a client that unsubscribes (F4) is back to `Connected` and is timed again.
  uint32_t armedAt = 0;
  bool timerArmed = false;
  //: Set by F3 and cleared by `transport::subscribed()`. The protocol layer asks this once a loop pass, so
  //: a PC that has just subscribed learns the screen instead of inferring it from the next change.
  bool subscriptionPending = false;
  //: Set when a return to `Advertising` did not take. The stack can still be finishing the disconnect, so
  //: `ble_gap_adv_start` answers busy rather than the radio being broken; the loop asks again. Without
  //: this, a failed restart is a rig that is running and cannot be found, which looks exactly like a rig
  //: that is switched off - the failure the bench report of 2026-11-15 came from.
  bool advertisingWanted = false;
  uint32_t advertisingAskedAt = 0;
  //: The drop-storm window (§5 rule 5): the last `BLE_DROP_STORM_LIMIT` disconnect times.
  uint32_t dropTimes[cfg::BLE_DROP_STORM_LIMIT] = {0};
  uint8_t dropIndex = 0;
  //: The negotiated ATT MTU, or zero while nothing is negotiated.
  uint16_t mtu = 0;
};

Layer layer;
portMUX_TYPE layerMux = portMUX_INITIALIZER_UNLOCKED;

//: Bytes that came in from the central, waiting for `protocol::poll`. A ring rather than a buffer that
//: grows: a central that floods the rig must lose the oldest bytes, not its last memory.
constexpr size_t RX_CAPACITY = 512;
uint8_t rxRing[RX_CAPACITY];
size_t rxHead = 0;
size_t rxTail = 0;
portMUX_TYPE rxMux = portMUX_INITIALIZER_UNLOCKED;

//: One outgoing line, assembled from the fragments `protocol` writes. The longest line this firmware emits
//: is 29 bytes, so the ceiling here is a guard against a format bug rather than a size anything needs.
constexpr size_t TX_CAPACITY = 96;
char txLine[TX_CAPACITY];
size_t txLength = 0;

BLEServer* server = nullptr;
BLECharacteristic* txCharacteristic = nullptr;

State currentState() {
  portENTER_CRITICAL(&layerMux);
  const State state = layer.state;
  portEXIT_CRITICAL(&layerMux);
  return state;
}

bool startAdvertising();
void stopAdvertising();
void requestAdvertising();
void dropCentral();
void dispatch(Event event, uint16_t handle = kNoHandle);

//: One notification per line, split to the negotiated payload. A line under forty bytes normally fits one
//: notification, but the peer may grant a 23-byte MTU, and the wire is a byte stream either way: the PC
//: end reassembles on `\n` exactly as it does over the cable. Splitting here rather than in the protocol
//: keeps the sentence "the transport carries bytes" true.
void notifyBytes(const char* data, size_t length) {
  if (txCharacteristic == nullptr || currentState() != State::Streaming) {
    // Nobody subscribed. The three lines emitted during boot have no reader; the PC learns the screen from
    // the first change after it attaches, which its own first keepalive produces.
    return;
  }
  portENTER_CRITICAL(&layerMux);
  const uint16_t mtu = layer.mtu;
  portEXIT_CRITICAL(&layerMux);
  //: Three bytes of ATT header. Before an exchange has happened the specification's floor of 23 - twenty
  //: bytes of payload - is the only safe assumption.
  const size_t payload = (mtu > 3 ? static_cast<size_t>(mtu) - 3 : 20);
  size_t offset = 0;
  while (offset < length) {
    const size_t chunk = (length - offset < payload) ? (length - offset) : payload;
    txCharacteristic->setValue(reinterpret_cast<const uint8_t*>(data + offset), chunk);
    txCharacteristic->notify();
    offset += chunk;
  }
}

//: The state machine's one entry point. Everything that can move this layer - a radio callback, the idle
//: timer - comes through here, so the matrix above is the only authority on what happens next.
void dispatch(Event event, uint16_t handle) {
  portENTER_CRITICAL(&layerMux);
  const State from = layer.state;
  portEXIT_CRITICAL(&layerMux);

  Cell cell = kMatrix[static_cast<uint8_t>(from)][static_cast<uint8_t>(event)];

  // §5 rule 5, which the table deliberately does not carry: a counter in every cell would stop the matrix
  // being readable. **Only a disconnect from `Streaming` counts**, and that narrowing is the fix for the
  // bench report of 2026-11-15: five deliberate connects - connect, subscribe, stop - each end in a
  // disconnect, and the unqualified rule turned the fifth of them into `Fault`, stopped the advertisement
  // and left a running rig that could not be found. What the rule is for is a link that vanishes while it
  // is carrying the protocol: that is a radio failing, and five of those inside the window turn the cell
  // that said `Advertising` into `Fault`. A peer that never became the PC, or one that said goodbye by
  // unsubscribing first (F4, which lands it in `Connected`), is not evidence against the radio.
  if (event == Event::Disconnect && from == State::Streaming) {
    const uint32_t now = millis();
    portENTER_CRITICAL(&layerMux);
    layer.dropTimes[layer.dropIndex] = now;
    layer.dropIndex = static_cast<uint8_t>((layer.dropIndex + 1) % cfg::BLE_DROP_STORM_LIMIT);
    uint8_t recent = 0;
    for (uint8_t i = 0; i < cfg::BLE_DROP_STORM_LIMIT; ++i) {
      const uint32_t at = layer.dropTimes[i];
      if (at != 0 && now - at < cfg::BLE_DROP_STORM_WINDOW_MS) {
        ++recent;
      }
    }
    portEXIT_CRITICAL(&layerMux);
    if (recent >= cfg::BLE_DROP_STORM_LIMIT) {
      cell = kToFault;
    }
  }

  switch (cell.outcome) {
    case Outcome::Move:
      portENTER_CRITICAL(&layerMux);
      layer.state = cell.target;
      portEXIT_CRITICAL(&layerMux);
      break;
    case Outcome::Rejected:
      // §5 rule 1: the second central is told, not ignored. A client that believes it subscribed will wait
      // for notifications that are going to somebody else, so the newcomer is disconnected rather than left
      // hanging - and the incumbent keeps the rig.
      if (server != nullptr && handle != kNoHandle) {
        server->disconnect(handle);
      }
      break;
    case Outcome::Handled:
    case Outcome::Ignored:
      break;
  }

  // F1 arms the idle timer (§5 rule 2) and records which central holds the rig.
  if (event == Event::Connect && cell.outcome == Outcome::Move) {
    portENTER_CRITICAL(&layerMux);
    layer.connHandle = handle;
    layer.armedAt = millis();
    layer.timerArmed = true;
    portEXIT_CRITICAL(&layerMux);
  }
  // F3 disarms it: from here the protocol's own keepalive is what says whether the PC is there, and two
  // liveness rules for one link is the merge §2 forbids.
  if (event == Event::Subscribe && from == State::Connected) {
    portENTER_CRITICAL(&layerMux);
    layer.timerArmed = false;
    portEXIT_CRITICAL(&layerMux);
  }
  // F4 is back to `Connected`, so the ten seconds start again: the client is once more attached and not
  // listening, which is the one case the timer exists for.
  if (event == Event::Unsubscribe && from == State::Streaming) {
    portENTER_CRITICAL(&layerMux);
    layer.armedAt = millis();
    layer.timerArmed = true;
    portEXIT_CRITICAL(&layerMux);
  }

  const State to = currentState();
  if (event == Event::Disconnect && to == State::Advertising) {
    portENTER_CRITICAL(&layerMux);
    layer.connHandle = kNoHandle;
    portEXIT_CRITICAL(&layerMux);
    requestAdvertising();
  }
  if (event == Event::IdleTimeout) {
    // §5 rule 2: the peer that never subscribed is dropped, and the rig goes back to offering the service
    // rather than waiting for a client that is not listening.
    dropCentral();
    requestAdvertising();
  }
  if (event == Event::Subscribe && from == State::Connected) {
    // F3: tell the protocol layer, once, that somebody is listening. The panel's screen is the loop's to
    // report, and this layer does not know what a screen is.
    portENTER_CRITICAL(&layerMux);
    layer.subscriptionPending = true;
    portEXIT_CRITICAL(&layerMux);
  }
  if (to == State::Fault) {
    // §5 rule 7: the layer stops retrying. A radio that has refused five times is a radio a sixth attempt
    // will not fix, and leaving the advertisement up would hide the fault behind motion.
    portENTER_CRITICAL(&layerMux);
    layer.connHandle = kNoHandle;
    layer.timerArmed = false;
    layer.advertisingWanted = false;
    portEXIT_CRITICAL(&layerMux);
    stopAdvertising();
  }
}

// ---------------------------------------------------------------------------------- radio glue

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer* pServer, ble_gap_conn_desc* desc) override {
    (void)pServer;
    // One central at a time. In `Connected` or `Streaming` the event is rejected and the newcomer is
    // disconnected by `dispatch`; in `Advertising` it is the transition itself.
    dispatch(Event::Connect, desc->conn_handle);
  }

  void onDisconnect(BLEServer* pServer, ble_gap_conn_desc* desc) override {
    (void)pServer;
    bool mine = false;
    portENTER_CRITICAL(&layerMux);
    mine = layer.connHandle == desc->conn_handle;
    if (mine) {
      layer.timerArmed = false;
    }
    portEXIT_CRITICAL(&layerMux);
    if (!mine) {
      return;  // a refused newcomer leaving is not the central disconnecting
    }
    dispatch(Event::Disconnect, desc->conn_handle);
  }

  void onMtuChanged(BLEServer* pServer, ble_gap_conn_desc* desc, uint16_t mtu) override {
    (void)pServer;
    (void)desc;
    portENTER_CRITICAL(&layerMux);
    layer.mtu = mtu;
    portEXIT_CRITICAL(&layerMux);
  }
};

class RxCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* characteristic) override {
    const String value = characteristic->getValue();
    if (value.isEmpty()) {
      return;
    }
    portENTER_CRITICAL(&rxMux);
    for (size_t i = 0; i < value.length(); ++i) {
      const size_t next = (rxHead + 1) % RX_CAPACITY;
      if (next == rxTail) {
        rxTail = (rxTail + 1) % RX_CAPACITY;  // full: the oldest byte goes, never the newest
      }
      rxRing[rxHead] = static_cast<uint8_t>(value[i]);
      rxHead = next;
    }
    portEXIT_CRITICAL(&rxMux);
  }
};

class TxCallbacks : public BLECharacteristicCallbacks {
  void onSubscribe(BLECharacteristic* characteristic, ble_gap_conn_desc* desc, uint16_t subValue) override {
    (void)characteristic;
    (void)desc;
    // F3 when notifications are enabled, F4 when they are turned off again: the two halves of one write to
    // the client characteristic configuration, and the only way this layer learns that a PC has stopped
    // listening.
    dispatch(subValue == 0 ? Event::Unsubscribe : Event::Subscribe, desc->conn_handle);
  }
};

ServerCallbacks serverCallbacks;
RxCallbacks rxCallbacks;
TxCallbacks txCallbacks;

bool startAdvertising() {
  if (server == nullptr) {
    return false;
  }
  BLEAdvertising* advertising = BLEDevice::getAdvertising();
  if (advertising == nullptr) {
    return false;
  }
  // The name goes in the advertisement and the service UUID in the scan response, because one packet
  // cannot hold both: flags, a 128-bit UUID and a ten-character name come to 33 bytes against the 31 an
  // advertisement may carry. Both are read from a scan, and a person looking at the rig with a phone app
  // sees the name first.
  BLEAdvertisementData advertisement;
  advertisement.setFlags(0x06);  // LE General Discoverable, BR/EDR not supported
  advertisement.setName(cfg::BLE_NAME);
  BLEAdvertisementData scanResponse;
  scanResponse.setCompleteServices(BLEUUID(cfg::BLE_SERVICE_UUID));
  if (!advertising->setAdvertisementData(advertisement)) {
    return false;
  }
  advertising->setScanResponse(true);
  if (!advertising->setScanResponseData(scanResponse)) {
    return false;
  }
  return advertising->start();
}

void stopAdvertising() {
  BLEAdvertising* advertising = BLEDevice::getAdvertising();
  if (advertising != nullptr) {
    advertising->stop();
  }
}

//: Ask for the advertisement, and remember the request if the stack is not ready for it.
//:
//: A restart immediately after a disconnect can be refused - the host may still be finishing the
//: disconnect - and a refused restart is otherwise silent and final: no advertisement, no fault, no code
//: on the panel, and a rig that is running and cannot be found. `serviceAdvertising` asks again from the
//: loop, which is also where this layer's idle timer is read.
void requestAdvertising() {
  if (startAdvertising()) {
    portENTER_CRITICAL(&layerMux);
    layer.advertisingWanted = false;
    portEXIT_CRITICAL(&layerMux);
    return;
  }
  portENTER_CRITICAL(&layerMux);
  layer.advertisingWanted = true;
  layer.advertisingAskedAt = millis();
  portEXIT_CRITICAL(&layerMux);
}

//: The retry, paced: fast enough that the rig is findable a moment after a client leaves, slow enough not
//: to spin at loop rate on a stack that is finishing a disconnect.
void serviceAdvertising() {
  const uint32_t now = millis();
  portENTER_CRITICAL(&layerMux);
  const bool wanted = layer.advertisingWanted && layer.state == State::Advertising &&
                      now - layer.advertisingAskedAt >= cfg::BLE_ADVERTISE_RETRY_MS;
  portEXIT_CRITICAL(&layerMux);
  if (wanted) {
    requestAdvertising();
  }
}

void dropCentral() {
  uint16_t handle = kNoHandle;
  portENTER_CRITICAL(&layerMux);
  handle = layer.connHandle;
  portEXIT_CRITICAL(&layerMux);
  if (server != nullptr && handle != kNoHandle) {
    server->disconnect(handle);
  }
}

//: The idle timer of F6, read here because this is the call the loop makes every iteration. It runs only in
//: `Connected` (§5 rule 4): a PC that stopped sending commands has not gone away, and a timer that dropped
//: it would be rule 3 contradicted by a timer. What does drop a peer is the stack's own link supervision
//: timeout, which runs whether or not this layer watches it.
void serviceIdleTimer() {
  portENTER_CRITICAL(&layerMux);
  const bool armed = layer.timerArmed && layer.state == State::Connected;
  const uint32_t armedAt = layer.armedAt;
  portEXIT_CRITICAL(&layerMux);
  if (!armed || millis() - armedAt < cfg::BLE_SUBSCRIBE_GRACE_MS) {
    return;
  }
  dispatch(Event::IdleTimeout);
}

}  // namespace

namespace transport {

Result begin() {
  // `Idle` becomes `Advertising` once, at boot: it is not an event, and a stack that starts successfully
  // has exactly one thing to do (§5 rule 6). A stack that refuses is `Fault` (F7) and `Err4` on the panel:
  // waiting will not fix it, so nothing here retries.
  if (!BLEDevice::init(cfg::BLE_NAME)) {
    dispatch(Event::InitFailure);
    return Result::Failed;
  }
  if (BLEDevice::setMTU(cfg::BLE_PREFERRED_MTU) != ESP_OK) {
    dispatch(Event::InitFailure);
    return Result::Failed;
  }
  server = BLEDevice::createServer();
  if (server == nullptr) {
    dispatch(Event::InitFailure);
    return Result::Failed;
  }
  server->setCallbacks(&serverCallbacks);
  // The layer decides when to advertise, because only it knows whether a drop was a hiccup or the fifth in
  // a minute; a stack that re-advertised on its own would hide the fault behind motion.
  server->advertiseOnDisconnect(false);

  BLEService* service = server->createService(cfg::BLE_SERVICE_UUID);
  if (service == nullptr) {
    dispatch(Event::InitFailure);
    return Result::Failed;
  }
  BLECharacteristic* rx = service->createCharacteristic(
      cfg::BLE_RX_UUID, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  txCharacteristic = service->createCharacteristic(cfg::BLE_TX_UUID, BLECharacteristic::PROPERTY_NOTIFY);
  if (rx == nullptr || txCharacteristic == nullptr) {
    dispatch(Event::InitFailure);
    return Result::Failed;
  }
  rx->setCallbacks(&rxCallbacks);
  txCharacteristic->setCallbacks(&txCallbacks);
  // No `BLE2902` is added by hand: this library creates the client characteristic configuration itself for
  // a characteristic with the notify property, and adding one only logs a warning.
  service->start();
  server->start();

  if (!startAdvertising()) {
    dispatch(Event::InitFailure);
    return Result::Failed;
  }
  portENTER_CRITICAL(&layerMux);
  layer.state = State::Advertising;  // the one unconditional transition in this layer
  portEXIT_CRITICAL(&layerMux);
  return Result::Ok;
}

int available() {
  portENTER_CRITICAL(&rxMux);
  const size_t head = rxHead;
  const size_t tail = rxTail;
  portEXIT_CRITICAL(&rxMux);
  return static_cast<int>((head + RX_CAPACITY - tail) % RX_CAPACITY);
}

int readByte() {
  int value = -1;
  portENTER_CRITICAL(&rxMux);
  if (rxHead != rxTail) {
    value = rxRing[rxTail];
    rxTail = (rxTail + 1) % RX_CAPACITY;
  }
  portEXIT_CRITICAL(&rxMux);
  return value;
}

void printf(const char* format, ...) {
  char buffer[TX_CAPACITY];
  va_list arguments;
  va_start(arguments, format);
  const int written = vsnprintf(buffer, sizeof(buffer), format, arguments);
  va_end(arguments);
  if (written <= 0) {
    return;
  }
  const size_t length =
      (static_cast<size_t>(written) < sizeof(buffer)) ? static_cast<size_t>(written) : sizeof(buffer) - 1;
  for (size_t i = 0; i < length; ++i) {
    if (txLength == TX_CAPACITY) {
      // A line longer than the ceiling is a format bug, not a size anything needs: send what is there
      // rather than silently dropping the tail of a line the PC is waiting for.
      notifyBytes(txLine, txLength);
      txLength = 0;
    }
    txLine[txLength++] = buffer[i];
    // A line ends at `\n`, however it was built: most of `protocol.cpp` writes the newline inside the
    // format string and only `EVT PONG` uses `newline()`, and a carrier that flushed on the call instead
    // of the byte would hold every event except the pong until the next one - which is the kind of
    // silence that reads as a dead rig.
    if (buffer[i] == '\n') {
      notifyBytes(txLine, txLength);
      txLength = 0;
    }
  }
}

void newline() {
  // `\r\n`, exactly as the serial implementation writes: the PC strips both, and a carrier that quietly
  // changed the line ending would be a protocol change nobody asked for.
  if (txLength + 2 > TX_CAPACITY) {
    notifyBytes(txLine, txLength);
    txLength = 0;
  }
  txLine[txLength++] = '\r';
  txLine[txLength++] = '\n';
  notifyBytes(txLine, txLength);
  txLength = 0;
}

//: The loop's tick into this layer as well as its query: the idle timer is the one deadline here that no
//: radio callback will ever raise on its own, and a refused advertisement is retried from here too.
bool faulted() {
  serviceIdleTimer();
  serviceAdvertising();
  return currentState() == State::Fault;
}

//: True once for each central that enables notifications, and cleared by the question.
bool subscribed() {
  portENTER_CRITICAL(&layerMux);
  const bool pending = layer.subscriptionPending;
  layer.subscriptionPending = false;
  portEXIT_CRITICAL(&layerMux);
  return pending;
}

//: True while a central holds the link: `Connected` before it subscribes and `Streaming` after. This is
//: the carrier fact the presentation layer reads to separate `Pairing` from `Live`
//: (docs/rig-state-machine-en.md §11); `Advertising` and `Fault` answer false, because there is nobody
//: attached in either. It is not a liveness claim: the protocol layer still calls a silent central
//: `Gone`, which no longer chooses a face.
bool attached() {
  const State state = currentState();
  return state == State::Connected || state == State::Streaming;
}

}  // namespace transport
