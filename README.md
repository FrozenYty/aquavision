# AquaVision

[中文](README-zh.md)

Underwater species detection and monitoring built on YOLOv8. A live camera feed is analysed to
count and locate four classes — sea cucumber, sea urchin, scallop and starfish —
with a human review loop that feeds corrections back into training.

**Status**: phase P2, see [PROGRESS.md](PROGRESS.md). The backend serves both the API and the thirteen
pages from one origin, sign-in works against a freshly created database, and the ESP32 firmware compiles
and drives its panel. Detection still returns 501 without weights, the capture rig is not assembled, and
the camera path is hardware-gated.

## Getting started

Everything below was run on a clean clone before it was written down. If a step does not work for you,
that is a defect in this file — say so.

**You need:** Python 3.11 or newer, and nothing else. The camera, the ESP32 and the training stack are
all optional; the application starts without any of them.

### 1. Clone and enter

```bash
git clone https://github.com/FrozenYty/aquavision.git
cd aquavision
```

### 2. Create an environment

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Windows cmd
.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements-server.txt
```

That is the web application and its tests. `requirements.txt` is the **full** environment and also
pins `ultralytics`, which pulls torch, torchvision and a second OpenCV build — several gigabytes, and
the server never imports it. Use the full file only on a machine that trains.

### 4. Create the database

```bash
python scripts/init_db.py
```

It creates the thirteen tables, seeds the four species, and — on an empty database only — creates the
first account. **It prints that account's password once**; copy it.

```
username: admin
password: <printed once, not recoverable>
```

Pass `--admin-password` (or set `AV_ADMIN_PASSWORD`) to choose your own instead, and
`--dsn` or `DB_DSN` to point at another database. The script is idempotent: running it again changes
nothing and never resets a password.

### 5. Run it

```bash
python -m uvicorn app.main:app --app-dir server --port 8000
```

One process. It serves the API **and** the pages, so there is no second server and no proxy to
configure.

### 6. Open it

| What | Where |
|---|---|
| The application | <http://127.0.0.1:8000/> — redirects to the sign-in page |
| Interactive API docs | <http://127.0.0.1:8000/api/docs> |
| Liveness and config | <http://127.0.0.1:8000/api/health> |

Sign in with `admin` and the password from step 4.

### 7. Run the tests

```bash
pytest -q
```

171 tests, about a minute. No camera, no database server and no network are needed.

### When something goes wrong

| Symptom | Cause and fix |
|---|---|
| Sign-in answers "wrong account or password" though the password is right | The database the server opened is not the one you created. Both use `data/app.db` **under the repository root** whatever directory you start from, so check `DB_DSN` is unset in both shells. |
| `Address already in use` | Port 8000 is taken — stop the other process, or `--port 8001`. |
| Every page says "interface not found" | The pages are being served from somewhere else (an old `python -m http.server` in another tab). Open the address from step 6. |
| Pages are blank and the console mentions CORS or `Origin null` | The HTML was opened from the filesystem. It needs an HTTP server — step 5 provides it. |
| `ModuleNotFoundError: app` | Uvicorn was started without `--app-dir server`, or from the wrong directory. |

### What works, and what does not

Honest list, because a README that overstates is worse than a short one.

- **Works**: sign-in and roles, the frame list and detail, review submissions, statistics, the
  dataset export, system settings — against real tables and a real database.
- **Works without hardware**: everything above; the camera pages fall back to an empty list.
- **Not yet**: detection returns 501 until weights are registered (`P2-05`), the live capture page has
  no `/ws/capture` socket so it polls, and the ESP32 rig link has no PC-side implementation yet
  (`P2-17`).

### Prototype mode, no backend

The pages can also run on mock data, for a demo without a database:

```bash
python -m http.server 8765 --directory web
```

Then open <http://127.0.0.1:8765/templates/login.html?mock=1>. The flag applies to that browser tab
and switches every call to `web/static/mock/`; without it the pages call the real API and ask for a
sign-in. Mock mode hides backend defects by design — use it to show the interface, not to test it.

## Documents

| Document | Notes |
|---|---|
| [Documentation index](docs/INDEX-en.md) | Which document answers what, and what else changes with it |
| [SRS v1.11](docs/srs-en.md) | 29 functional requirements, 9 use cases, 13 tables, 36 acceptance items |
| [Plan](PLAN.md) | Phases, tasks and gates — the task contract for the team |
| [Architecture](docs/architecture-en.md) | Layers, dependency rules, runtime model, frame lifecycle |
| [API contract](docs/api-contract-en.md) | REST paths, response envelope, error codes, WebSocket protocol |
| [Data model](docs/data-model-en.md) | Thirteen tables, fields, indexes, file storage |
| [Test plan](docs/test-plan-en.md) | Test levels, dataset splitting, metrics and acceptance |
| [Glossary](docs/glossary-en-zh.md) | English ↔ Chinese, the single word list shared by code and docs |
| [Decisions](docs/adr/) | Ten decision records, one of them superseded, with the reasoning; `docs/architecture-en.md` §10 lists them |

English is the source of truth for design documents; the Chinese files are reference versions and
must be updated in the same commit.

## Layout

```
docs/        design documents and the SRS
docs/adr/    architecture decision records
scripts/     dataset preparation, training, database setup, document checks
server/      FastAPI backend — the API and, from this release, the pages
web/         static frontend pages
firmware/    ESP32 firmware
tests/       tests
```

## Stack

| Layer | Choice |
|---|---|
| Capture | USB camera (1080P, manual exposure, UVC) with OpenCV |
| Detection | PyTorch + Ultralytics YOLOv8n, three improvements: underwater colour correction, EMA attention, WIoU v3 |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.1; SQLite for a local run, PostgreSQL 14 for deployment |
| Frontend | HTML5, Bootstrap 5.3.3, hand-rolled SVG charts, plain ES modules, no build step; Bootstrap is vendored in `web/static/vendor/` |
| Rig controller | ESP32-S3 on the Arduino framework, built with PlatformIO; a 0.96" OLED and two status LEDs |

Targets: mAP@0.5 ≥ 0.75 on the four species, +0.03 over the baseline, and
inference speed at least 90% of the baseline.

## Team

| Member | Responsibility |
|---|---|
| Yao Tianyu | Capture pipeline, system architecture, requirements |
| Gao Tianxiang | Model training and improvements, inference service, backend API |
| Sun Jianheng | Frontend pages, annotation and datasets |
| Fu Yijia | Documentation, test cases, acceptance checks |

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before the first commit.
Branches, commits, pull requests and document rules all live there.

If you are an AI assistant, read [AGENTS.md](AGENTS.md) first — it tells you which lane you are in.

## License

MIT. See [LICENSE](LICENSE).

## Notes

Training data comes from public underwater datasets and images captured by the team; no real survey data and no personal information is included.
