# 03 — Single FastAPI process, no microservices

- **Status:** Accepted
- **Date:** 2026-11-03
- **Supersedes:** —

## Context

The system has three distinct concerns: capture, detection and business logic. Splitting them into
separate services (or introducing Celery and Redis for task handling) is a common textbook layout.

## Decision

One FastAPI process holds all three. Capture runs in a background thread, batch detection in a
fixed thread pool of two workers, and task state lives in PostgreSQL rather than in memory.

## Rationale

- Four people, eight weeks: every extra process is one more thing to start, log, debug and keep
  alive on the demo laptop.
- Detection rate and display rate are already decoupled (`detect_interval_ms`), which is the real
  performance concern; separating the process does not help with it.
- Task state in the database survives a restart, which an in-memory queue does not.
- Single process means single deployment: `cd server && uvicorn app.main:app`, or from the repository
  root `python -m uvicorn app.main:app --app-dir server`, plus a `.env` file. `--app-dir` adds `server/`
  to the import path, because the `app` package lives there and cannot be imported from the root.

## Consequences

- A crashed detection worker can stall the event loop if written carelessly — blocking calls must
  stay off the async path and run in the pool.
- Scaling out later would require extracting `vision/`. The layer boundary is already drawn for
  that reason: `vision` does not know about HTTP or the database.

## Revisit when

Two detection jobs must run concurrently on separate GPUs, or the process exceeds the memory of
the target machine. Neither is expected within this project.
