# 15 — Parameters take effect at the next decision point

- **Status:** Accepted
- **Date:** 2026-11-12
- **Decides:** the question recorded as `P3-18` after the 11-11 audit — whether `PATCH /api/params` is
  write-only by design or by omission

## Context

`PATCH /api/params` persists a value into `sys_param`, validates the caller's role, and writes an audit
row carrying the before and after values. Every part of that works. **Nothing reads the table.** The
consumers of those same numbers read `Settings`, which is loaded once from the environment at process
start: the capture quality threshold, the detection worker's concurrency, and the retention period.

So the parameter page edits a copy nobody consults, and the operator's mental model — "I changed the
concurrency limit, so new jobs are limited" — is false until the next restart. The acceptance item that
tests this (`AC-27`) asserts exactly that the change binds new work, which is why the audit called it out:
not as a missing route, but as a route whose effect does not exist.

`FR-M7-01` promises a change "needs no rebuild". Every version of the current behaviour satisfies that
sentence, which is why the defect survived: the requirement is not precise enough to fail. What it should
mean is the thing an operator actually wants — **a change takes effect without a restart** — and today the
system does not deliver it.

## Decision

A parameter that the operator can change takes effect **at the next decision point**, in the running
process, without a restart:

- **One accessor** reads a parameter's effective value: it consults `sys_param`, falls back to the
  configured default in `Settings` when the row is absent, and caches the result for a few seconds.
- **Consumers call it at the moment they need the number** — the capture route when it judges quality, the
  worker when it decides how many tasks to claim, the cleanup when it decides what is old enough. Not once
  at start-up.
- **Each parameter declares its range**, validated on write and refused with the project's envelope when
  out of range. A limit of zero workers or a negative retention period is a configuration error, and it
  should be refused at the page rather than discovered by an empty queue.
- **The cache is a short time-to-live, not an invalidation push.** In one process, invalidating on write
  would be tidier; with more than one, the writer's invalidation reaches only itself. A bounded TTL is
  correct for both, and a delay of seconds is indistinguishable to a person clicking a form. **The TTL is
  a stated number in one place, not a hidden default.**
- **The page states what is in effect**, and does not tell the operator that a restart is required, because
  it is not.

## Alternatives considered

**Keep it write-only and document "restart required".** The smallest honest change, and it would have closed
the audit finding by editing a sentence. Rejected because it makes the parameters page a form that writes to
a file for later: the operator still cannot see the effect of what they just did, `AC-27` can never pass, and
`FR-M7-01`'s promise stays empty. It also means the value in the database and the value in force differ
indefinitely, which is the state that produced this defect.

**Read the parameter fresh on every use, no cache.** Correct and simple. Rejected on the hot path: a query
per captured frame for a number that changes once a month, when the frame is already the most expensive
request in the system.

**Invalidate from the writer.** Precise within one process and the design a larger system would choose.
Rejected as the wrong complexity at this size — it needs a shared cache and a cross-process signal to be
correct, and being correct only in the single-process deployment is the kind of assumption that becomes a
bug the day a second process starts. Revisit if the deployment ever runs more than one.

**Do nothing and drop `AC-27`.** The acceptance criterion would then describe behaviour the system never
promised. Rejected because the promise is worth keeping: an operator changing a limit expects it to apply.

## Consequences

- `AC-27` becomes reachable: a limit changed through the API binds a job created after the change and not
  one created before, and a test asserts exactly that.
- The audit trail already records before and after, so no new history mechanism is needed — the value now
  has an effect as well as a record.
- A bad parameter value can now damage a running system (a concurrency of zero stops detection), which is
  why the range check is part of this decision and not a later refinement.
- `P3-09` keeps monitoring and the message store; the parameter half moves to its own task, so the person
  who implements live effect is not the same person reading `/api/monitor` for the first time.

## Revisit when

The deployment runs more than one application process, or a parameter needs to reach a component that
cannot read the database (the firmware, for instance) — then the TTL cache is no longer sufficient and this
becomes a signal, not a lookup.
