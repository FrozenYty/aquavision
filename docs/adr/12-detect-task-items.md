# 12 — A task is assigned its frames; it does not discover them

- **Status:** Accepted
- **Date:** 2026-11-11
- **Amends:** ADR 08 — the table count moves from thirteen to fourteen

## Context

`_frames_for` builds a task's work list at run time by selecting the frames that have no `detect_object`
row. Its own comment admitted the weak spot: *a frame with zero boxes is indistinguishable from an
unprocessed one without a join table; the data model has none.* That was recorded as a `P2-05b` concern
and deferred. Measuring it on 11-11 showed the comment understated the problem, and showed a second
failure the comment did not mention.

**Two workers claim the same frames.** Two queued tasks, `workers=2`, `asset_count=10` each:

```
tasks (id,status,progress,obj_count): [(1, 2, 100, 10), (2, 2, 100, 10)]
OVERLAP between the two tasks: 10
```

Both workers call `_frames_for` inside their own transaction, and neither has written a box yet, so both
receive the same ten frames. Both then run inference on them, and both task rows report the same assets
as their own. The cost is doubled inference and two rows claiming one frame.

**A frame that genuinely contains nothing is never finished.** A frame the model finds no object in
produces no `detect_object` row, so it stays "unprocessed" forever and every later task picks it up
again. On the four-class tank this is not a corner: an empty frame is a legitimate, expected result.

The queue itself is sound — the task row is the state, cancellation is a row state, and a restart
reprocesses. The defect is narrower: **the frame set is a query re-evaluated by every worker, instead of
a set the task owns.**

## Decision

A task's frames are **assigned when the task is created** and recorded in a new table,
`detect_task_item` (data model §3.14). Fourteen tables.

- `create_batch` selects the frames and writes one item row per frame. The task's work list is fixed at
  that moment and identical for every worker that later touches it.
- An item carries its own state — pending, running, done, failed — and its own `box_count`. **A frame
  with zero boxes is recorded as done**, because `box_count = 0` is a result, not the absence of one.
- A worker claims an item with an atomic compare-and-swap:
  `UPDATE detect_task_item SET state = running WHERE item_id = ? AND state = pending`, and it treats a
  zero row count as "another worker won, take the next one". No lock is held across inference, which
  matters because the frame path deliberately ends its read transaction before the detector runs.
- Progress and `obj_count` are derived from the items, so they describe the task's own work rather than
  a query over whatever boxes happen to exist.
- A restart returns **running** items to pending and leaves done ones done: the resumed task continues
  where it stopped instead of reprocessing frames it already has results for.

**Which frames a batch takes.** `create_batch` takes the frames that have not been through detection and
are not already owned by a task: one with a `detect_object` row or any `detect_task_item` row is skipped.
Two batches created back to back therefore take disjoint sets, which is what makes the duplicate claim
impossible before a worker has even started. Two consequences are deliberate rather than accidental:

- a frame a task owns is not offered to a later batch, and that includes the frames of a cancelled task,
  whose items stay pending and keep holding them. Cancelling is not releasing; a retry of that task is
  the path that runs them again.
- a path that must run frames which have already been detected names them instead of asking for the next
  batch. `P4-10`'s same-frame comparison does exactly that through `POST /api/compare/frames/{id}`, which
  is why the item table rather than a claim column on the frame was the right shape.

## Alternatives considered

**A claim column on `media_asset`** — one field, no new table, and it does fix the duplicate claim. It
was rejected because it makes "processed" a property of the frame rather than of the task, and `P4-10`
needs the opposite: the same frame detected by two model versions, side by side, deliberately. A single
column cannot hold two answers, and the second comparison task would find every frame already done.

**Keep run-time selection and take a lock around it.** SQLite has no row locks, and the selection runs
in its own short transaction precisely so a cancel can land during inference. A lock long enough to help
would have to span the leading frames; a lock short enough to be safe does not prevent the race.

**Run one worker.** Correct by construction and costs one line. Rejected because the pool exists to keep
a long batch from blocking the queue, and `max_concurrency` is already a parameter an operator can set —
making it a lie for any value above one is the wrong trade.

**Record zero-box frames as a sentinel row in `detect_object`.** The table's `class_code` is a foreign key
to the species dictionary and a box's geometry is `NOT NULL`, so "no object" has no honest representation
there. Inventing a null class would push the special case into every query that reads the table.

## Consequences

- The duplicate claim and the never-finished frame are both closed by the same structure, which is the
  reason to do this as one change rather than two.
- **Cross-reference sweep:** the table count is written down in the data model, the SRS, the
  architecture, both READMEs, the handover and the plan's gate. Every one of those says *tables*; the
  repository also counts **thirteen pages**, which is a different number about a different thing and does
  not move.
- `EXPECTED_COLUMNS` in `tests/test_init_db.py` grows by one entry, and the schema test fails on a
  half-applied change — which is what it is for.
- The SRS revision history records the change, as ADR 08's precedent requires when §4.1 moves.
- A task now allocates rows at creation, so a batch of a few thousand frames writes a few thousand item
  rows before any inference happens. That is the intended trade: the queue becomes explicit.

## Revisit when

Frames are re-detected by several model versions often enough that per-task item rows become the larger
cost, or the pool is replaced by a broker that tracks assignment itself.
