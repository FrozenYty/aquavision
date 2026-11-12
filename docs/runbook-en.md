# Operations runbook

What to do when the system is not the point — when you have to start it, move it, back it up, or find out
why it stopped. Everything here was run on this project before it was written down.

If a step does not work, that is a defect in this page, not in you. Say so.

## 1. What this is for

The `README` gets a clone running. This page is for everything after that: the second machine, the
inference environment, the backup before a risky change, the log you read at 2 a.m. It assumes you can
read a shell and nothing more.

## 2. What you need before you start

- Python 3.11 or newer.
- The web application and its tests: `pip install -r requirements-server.txt`.
- Detection, which the demo needs: the **full** environment, `pip install -r requirements.txt`. It pins
  `ultralytics`, which pulls torch, torchvision and a second OpenCV build — several gigabytes, and the
  server never imports it. Keep the two environments separate; see section 4.
- Nothing else. The camera, the ESP32 and the training stack are optional: the application starts without
  any of them, and says so instead of failing.

## 3. First deployment from a clone

Three commands, in this order, from the repository root.

```bash
python -m pip install -r requirements-server.txt
python scripts/init_db.py
python -m uvicorn app.main:app --app-dir server --port 8000
```

- `init_db.py` creates the fourteen tables, seeds the four species, registers any version delivered under
  `models/`, and — **on an empty database only** — creates the first account. It prints that account's
  password once and never again; copy it before the terminal scrolls. It is safe to re-run: it never
  overwrites a password and never takes an online model away from the operator.
- On an existing database it is still safe, but it will not add a **column** — see section 7.
- `--app-dir server` is what makes `app.main` importable from the repository root. Running `uvicorn` from
  inside `server/` also works, but then relative paths in configuration resolve differently, so prefer
  this form.

Then open the page and sign in with the account from step 2. `/api/health` from a terminal is the faster
first check: it reports the database, the mounted route count and whether the JWT secret is still the
default one.

## 4. The inference environment

Detection needs `ultralytics` and torch. The server environment deliberately does not have them — that is
ADR 11's argument, and it keeps a clone that only runs the API small. So a machine that demonstrates
detection has **two** environments.

Build the second one, once per checkout, in an environment of its own:

```bash
python -m venv .venv-infer
.venv-infer/Scripts/python -m pip install -r requirements.txt
```

`.venv-infer/` is in `.gitignore`, so it stays out of the repository. Then run anything that loads a model
with that interpreter:

```bash
.venv-infer/Scripts/python -m pytest tests/test_detect_real.py -o addopts="" -q
```

Three tests run there that skip everywhere else, because they are the only evidence that the delivered
weights load and produce the boxes the API reports. If they pass, detection works.

**Two things that go wrong on Windows, both seen on this project:**

- `python -m venv` or `pip` failing with `PermissionError` while writing a **temporary** directory they
  just created. Python gives a temporary directory owner-only permissions, and a sandboxed or restricted
  process is not that owner, so pointing `TMP` elsewhere does not help. Run the install with the access
  it asks for instead of working around it.
- `ultralytics` writing its settings directory into the **current** directory when the user config
  directory is not writable, which puts `Ultralytics/` at the repository root. Set `YOLO_CONFIG_DIR` to a
  writable path outside the repository before running it; the directory is also git-ignored, so a stray
  copy can never be committed.

## 5. Back up and restore

Two things make up the state: the database and the stored frames under the data root (`data/` by default,
`AV_DATA_DIR` if set). Back up both, or a restore comes back with rows pointing at images that are gone.

The SQLite development default:

```bash
python -c "import sqlite3; sqlite3.connect('data/app.db').execute('VACUUM INTO \"data/backup-app.db\"')"
```

That is the safe form: **copying the file while the service is running can capture a half-written page**.
`VACUUM INTO` writes a consistent copy. Stop the service first if you can, and you may copy the file
instead.

PostgreSQL, when `DB_DSN` names one:

```bash
pg_dump --no-owner --format=custom "$DB_DSN" > backup.dump
```

Restore is the same in reverse: stop the service, put the database file or dump back, restore the frames
directory beside it, start the service. Then check `/api/health`, sign in, and open one frame — a restore
that answers health but cannot display a frame has restored the wrong half.

## 6. Rotate the JWT secret

Every issued token is signed with `AV_JWT_SECRET`, and tokens are stateless: there is no session table to
clear. So rotating the secret **invalidates every token at once**, and everyone signs in again. That is the
intended behaviour, not a side effect — it is the only way to retire a leaked secret.

```bash
# set a new value in .env or the service environment, then restart the process
AV_JWT_SECRET="<a long random string>"
```

`/api/health` reports `jwt_secret_is_default: true` while the shipped default is in force. That field
being `true` on a reachable machine is a finding, not a detail: anyone who can read the repository can
mint a token for it.

Rotating **does not** deliver on "a password change invalidates issued tokens" — that is a different
mechanism, now carried by a per-user token epoch, and it needs no operator action.

## 7. Upgrade the schema

**`init_db.py` upgrades an existing database in place.** It used to be honest about the gap: `create_all`
adds a missing *table*, not a **column** on a table that already exists, so a column added to
`server/app/models.py` reached a fresh database and broke every existing one with

```text
sqlite3.OperationalError: no such column: sys_user.token_epoch
```

which the application then reported as **"the database is unreachable, check that it is running"** - wrong,
because the database was reachable and one column was missing. That happened here on 2026-11-12.

Since `P3-25`, one command closes the gap:

```bash
python scripts/init_db.py
```

It creates what is missing, then adds each column the models declare and the table lacks, with the
default the model gives it, in place, keeping every row:

```text
schema upgraded: sys_user.token_epoch (existing rows kept)
```

The rule is **add, never rewrite**: nothing is dropped, nothing is retyped, and no row is touched. That is
deliberate - an unused column costs a few bytes, a wrong `DROP` costs data. A column that **cannot** be
added to a table that already has rows - `NOT NULL` with no default - is refused and the script exits 1
naming it, because a half-upgraded schema fails on the first query that selects the column:

```text
not upgraded: sys_user.real_name: NOT NULL without a server default
```

For that case, and for anything beyond adding a column (a rename, a type change), the manual route still
applies: back up, alter the table by hand, **and record what you did** - a hand-altered schema nobody wrote
down is how two machines end up disagreeing about what the database contains.

## 8. Read the log

Two places: the process log, which says what the application did, and the `sys_log` table, which is the
audit trail a reviewer reads. Both are needed and neither replaces the other.

A refused permission is a row in `sys_log` with `action = 'forbidden'`, the route in `target_id` and the
caller in `user_id`:

```bash
python -c "import sqlite3; [print(r) for r in sqlite3.connect('data/app.db').execute(\"SELECT created_at, module, action, target_id, user_id FROM sys_log WHERE action='forbidden' ORDER BY log_id DESC LIMIT 20\")]"
```

A **failed sign-in is deliberately not logged**. The decision is in `PROGRESS.md`: an unauthenticated
request never reaches the role matrix, it has no user to record, and logging every malformed header would
make the table a write sink reachable without credentials. Look in the process log for those, not here.

## 9. When the queue stops

`/api/monitor` is the operator's window: queue depth, frame counts, disk levels, and whether the detection
worker is alive. If it reports a `worker.problem`, the queue is not slow — it is stopped, and the message
says which of the two causes it is and what to do.

Three things to check, in this order: is the worker enabled (`AV_WORKER_ENABLED`), did the process log show
an exception in the worker thread, and does the queue have tasks its frames cannot be found for. Restarting
the service is safe: a task interrupted mid-run resumes rather than being lost.

## 10. Configurations you can change at runtime

These live in `sys_param` and are read **when they are needed**, not at start-up, so a change binds new
work within a couple of seconds and needs no restart (ADR 15). Each has a range, and a value outside it is
refused at the page and ignored if it got in some other way.

| Setting | Range | What it governs |
|---|---|---|
| `max_concurrency` | 1–32 | how many detection tasks may run at once |
| `quality_threshold` | 0–100 | the score a frame must reach to enter the queue |
| `detect_interval_ms` | 50–10000 | how often the live view runs detection |
| `camera_index` | 0–9 | which capture device the server opens |
| `retention_days` | 1–3650 | how old an intermediate frame must be to be a cleanup candidate |

Everything else is environment-only: the secret, the DSN, the time zone, the data root, the rig port. Those
are deployment decisions, and changing one means a restart on purpose.

## 11. What this runbook does not cover

- **Hardware.** Wiring, the level shifter and the optical numbers are in `procurement-en.md` and
  `rig-state-machine-en.md`.
- **Training.** `PLAN.md` P4 and `test-plan-en.md`.
- **The migration mechanism**, because it does not exist yet; when it does, section 7 shrinks to one
  command and this paragraph goes away.
- **A second application process.** The parameter cache is a short time-to-live rather than an
  invalidation push, which is correct for one process and untested for more; ADR 15 records what to
  revisit.
