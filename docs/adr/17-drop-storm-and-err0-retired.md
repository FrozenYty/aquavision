# 17 — The drop-storm rule and `Err0` are retired, and ADR 16's two statements are superseded

- **Status:** Accepted
- **Date:** 2026-11-27
- **Decides:** the `P4-05` entry the 2026-11-26 audit raised against
  `docs/adr/16-rig-cable-free-over-ble.md` — what an accepted record does when firmware has retired two
  of its rules, and what those two rules are now. The contract they belong to is
  `docs/rig-transport-en.md` §5 and `docs/rig-transport-zh.md` §5

## Context

ADR 16 was accepted on 2026-11-15 and settled how the finished rig reaches the PC: the line protocol
rides BLE, `rig-serial` stays as a build variant, and the link layer and the protocol layer are two
state machines. That decision stands. Two rules it states do not.

**The drop-storm rule is gone.** ADR 16 says "the firmware drops to `Fault` after five disconnects
inside a minute". Firmware 1.24 deleted it. `firmware/main/src/config.h` records the reason in its
version changelog — "1.24 deletes the drop-storm rule: it could not fire ... its remedy was wrong" —
and `FIRMWARE_VERSION` is `"1.24"`. The constants the rule read are gone too
(`BLE_DROP_STORM_WINDOW_MS`, `BLE_DROP_STORM_LIMIT`, `dropTimes`, `dropIndex`), so a reconnect has
nothing left to count. `tests/test_rig_presentation.py::test_there_is_no_drop_storm_rule` names all
four and fails if any returns, asserts that `Fault` has no disconnect route, and requires the
transport document's "There is no drop-storm rule" sentence to stay.

**`Err0` is not a live face.** ADR 16 treats `Err0` as the lost-link face and distinguishes `Err4`
from it by what the operator should do. Firmware 1.21 removed `OFFLINE`, `Err0` and the `NoLink`
presentation state; `config.h` says "`Err0` is retired and its number is not reused", and
`firmware/main/src/presentation.h` declares three states — `Pairing`, `Live`, `RadioFault` — with no
link-lost state among them. `Err1`-`Err3` keep their numbers and `Err4` is the radio that would not
start.

Both deletions were carried by commit `d9b0f36` ("feat(rig): write to the turbidity registers, and
plan the wireless rig (P3-37, P3-38)", PR #196, 2026-11-16), the same commit that added ADR 16 and §5
rule 5, so the record and the rule it contradicted landed together. The `PROGRESS.md` entry dated
2026-11-16 records both removals with their reasons: the rule could not fire (noticing a rude
disconnect takes the ~20 s link supervision timeout, so five never fit a minute) and its remedy was
wrong (the far end's radio is transient, while `Fault` is cleared only by a power cycle); `Err0`
called waiting a fault and gave two faces to one remedy.

`docs/rig-transport-en.md` §5 rule 5 already states the first result as a decision — "There is no
drop-storm rule, and its absence is a decision", ending "**Do not reintroduce the rule** without a
cause that only the rig can see" — and §3 defines the five BLE states in which `Fault` means only
that the radio did not start. `firmware/README.md` repeats both facts beside the panel's fault codes.
What was missing was the decision record: the audit found ADR 16 as the repository's only text still
stating both rules as live, and a reader who reached the ADR before the contract would reintroduce
them. The repository's rule for this is explicit: an accepted ADR is closed, and a change is written
as a new ADR that supersedes it (`AGENTS.md` §5, the `adr/` row in `docs/INDEX-en.md`).

## Decision

**This record supersedes the drop-storm rule and the `Err0` face in ADR 16. Every other statement in
ADR 16 stands, and ADR 16 itself is not edited.**

- **A disconnect is not a fault.** Whatever state it leaves, a disconnect lands in `Advertising`: the
  rig returns to waiting, advertises, and keeps trying. `Fault` is reachable only through F7, the
  radio failing to start, so `Err4` has exactly one cause. Whether a particular link is workable is
  the PC's judgement, and its client makes that judgement with a bounded attempt budget ending in
  `Failed` — the half of ADR 16's rule that remains.
- **`Err0` stays retired and its number is not reused.** A BLE link simply ends; an attached client
  that stops talking and one that never attached have the same remedy — wait — so they have one face
  and no code. The remaining faults keep `Err1`-`Err4`.
- **The contract is `docs/rig-transport-en.md` §5 rule 5 and §3**, with the Chinese pair saying the
  same. This ADR records why that statement exists, so a reader who meets the contradiction in ADR 16
  finds its resolution beside it.

## Alternatives considered

**Edit ADR 16 in place.** It would leave one document instead of two and is the cheapest diff. Rejected:
an accepted ADR records what was decided on its date, and editing it erases why the decision changed;
the repository says so twice (`AGENTS.md` §5, the `adr/` row in `docs/INDEX-en.md`). A reader would
also have no way to tell that firmware 1.24, not the ADR, is the source of the change.

**Leave ADR 16 alone and rely on `rig-transport` §5.** The contract already says both things correctly,
so the contradiction exists in only one file. Rejected: the decision table is where "why" is answered,
and an accepted ADR saying the rig faults on five drops is a live instruction to the next implementer.
Without a superseding record the contradiction is permanent rather than resolved.

**Keep the drop-storm rule behind a constant, defaulting to off.** It would preserve the option and
answer "it could not fire" with configuration. Rejected: the rule had no reachable path even with a
wider window — noticing a rude disconnect takes the ~20 s link supervision timeout — and its remedy is
wrong for the cause: the far end's radio is transient, while `Fault` is left only by a power cycle.

**Keep `Err0` as a diagnostic face beside `Err4`.** Two codes would say more than one. Rejected: the two
faces had one remedy — wait — so the second code made the operator think a step further for nothing, and
`Err0` called waiting a fault.

## Consequences

- `docs/adr/16-rig-cable-free-over-ble.md` is untouched. Its drop-storm sentence and its `Err0`/`Err4`
  distinction are superseded here; the rest of it — BLE, the serial variant, the two layers, the PC's
  bounded attempt budget — remains current.
- `docs/rig-transport-en.md` §5 rule 5 and §3 are the contract a reader is sent to, and so is the
  Chinese pair. `firmware/main/src/config.h`'s changelog and `firmware/README.md` are the firmware-side
  record; `tests/test_rig_presentation.py` is the check that keeps the absence from regressing.
- `PLAN.md` `P4-05`'s ADR-16 entry is closed by this record. The code defects in the same list stay
  open until their pull requests land, and the list is not shortened.
- No server, firmware or test code changes follow from this record: firmware 1.24 already behaves this
  way. This ADR is documentation of a decision the implementation had already taken.
- The PC-side attempt budget is unchanged: five attempts and `Failed` remain ADR 16's decision and the
  bound that stops a broken link looking like a working one.

## Revisit when

A cause only the rig can observe is found that a repeated drop would diagnose — the rig's own stack
reporting a loss the PC cannot see — because rule 5 forbids reintroducing the rule "without a cause that
only the rig can see". Or the transport gains a state for an attached-but-silent peer, which would give
`Err0`'s old case a face again; neither exists today.
