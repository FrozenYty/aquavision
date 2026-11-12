# 14 — What a day means

- **Status:** Accepted
- **Date:** 2026-11-12
- **Amends:** the `start`/`end` clause of `docs/api-contract-en.md` section 6, which said "the server time
  zone" while the code did something else; and the question recorded as `P3-18` after the 11-11 audit

## Context

The frame list filters by date, and the comparison was wrong in a way nobody could see from a test that
only asked whether the route answered 200. The filter built a naive `datetime` from `start`/`end` and
compared it against `captured_at`, which the capture route stores as naive UTC. A capture taken at 03:00
on 2 November in Beijing is stored as `2026-11-01T19:00:00`, so it was **absent from its own day** and
appeared under 1 November:

```
local capture 2026-11-02T03:00:00+08:00  ->  stored 2026-11-01T19:00:00
GET /api/frames?start=2026-11-02&end=2026-11-02 -> total=0
GET /api/frames?start=2026-11-01&end=2026-11-01 -> total=1
```

The contract said the range is "interpreted in the server time zone", which was neither what the code did
nor a thing the code could do: nothing in the process knew a zone. The same document's own response
example shows `"captured_at": "2026-11-03T19:30:12.418+08:00"`, while the server emitted a naive string
with no offset, so every client had to guess what it was looking at.

The decision is not only about that filter. **Five separate features ask a calendar question**: which
frames fall in a date range, which day a statistics bucket belongs to, which period a report covers, what
"N days old" means for retention cleanup, and what a page displays as a capture time. Left alone, five
authors answer it five ways and the answers disagree — which is exactly how the reported defect arose.

## Decision

- **Storage stays UTC**, naive in the database, as it is today. UTC is the only representation in which
  two deployments' rows are comparable, and it is the one part of the current behaviour that is right.
- **One configured zone answers every calendar question**, `AV_TIMEZONE`, defaulting to `Asia/Shanghai`.
  A day is `00:00:00` to `23:59:59.999999` **in that zone**, both bounds inclusive, which is the
  boundary the operator expects when they pick a date.
- **Every timestamp the API emits is offset-aware ISO-8601 in that zone**, matching the contract's
  example. A timestamp without an offset is a value the reader must interpret, and readers interpret
  differently.
- **One module owns the arithmetic** (`server/app/timebase.py`): the zone, the day bounds, the conversion
  for responses. No other module converts a date, and no other module does its own `timedelta` on a
  calendar boundary.
- **`tzdata` becomes a dependency.** Windows ships no IANA database, so `ZoneInfo("Asia/Shanghai")` raises
  there unless the package is installed. Relying on the developer's machine having it is how a feature
  works for one person.

## Alternatives considered

**The process's local time zone.** The contract's own words, and the smallest change. Rejected because it
makes behaviour depend on the machine's configuration: the same database, queried by two servers in
different zones, answers two different questions. This repository already treats machine-dependence as a
defect — `server/app/db.py` anchors a relative DSN to the repository root rather than the working
directory for exactly this reason, and `scripts/check-paths.py` exists to keep machine-specific paths out
of documents.

**A hardcoded `+08:00` offset.** Correct today, since Beijing has no daylight saving. Rejected because it
bakes a deployment assumption into arithmetic that will be spread across several modules, and because it
cannot express a zone that does change — the point of naming the zone is to leave that door open at the
cost of one settings field.

**Storing local time.** Then no two rows taken in different zones share a timeline, every comparison needs
the zone that was in force when the row was written, and the zone becomes part of the data rather than of
the deployment. Rejected.

**Returning naive timestamps and documenting the offset.** This is what the code did, and it is the
narrower half of the reported defect: the frontend's idea of "today" then disagrees with the filter's, and
both disagree with the statistics page, silently, in three different places.

**Fixing only the filter.** The immediate bug, at its immediate site. Rejected because a second and third
site would each be fixed the same week by a different person, and the next one would be missed.

## Consequences

- `AV_TIMEZONE` joins the configuration table in `docs/architecture-en.md` and `architecture-zh.md`.
- A test pins the boundary: a capture at `00:00:00` local is in that day, `23:59:59` local is in that day,
  and `00:00:00` the next day is not. It fails against the naive comparison.
- The interface must **display the time it is given**, with the offset the server sent, and must not
  re-derive a date from the browser's zone. Otherwise a reviewer in another zone reads one date on the
  dashboard and a different one in a filtered list, and both are "correct" by their own rule.
- `P3-18` is replaced by the task that implements this; the retention work (`P3-08`) and the two calendar
  features still to be built (`P3-02`, `P3-07`) use the same module rather than their own arithmetic.
- A future deployment outside UTC+8 changes one setting, and every calendar feature follows.

## Revisit when

A deployment needs per-user display zones rather than one operational zone — at which point the storage
decision above is what makes that a presentation change and not a migration.
