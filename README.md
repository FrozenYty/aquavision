# AquaVision

[中文](README-zh.md)

Underwater species detection and monitoring built on YOLOv8. A live camera feed is analysed to
count and locate four classes — sea cucumber, sea urchin, scallop and starfish —
with a human review loop that feeds corrections back into training.

**Status**: phase P1, see [PROGRESS.md](PROGRESS.md). The backend answers (`uvicorn`, 42 contract
routes), the thirteen pages run on mock data, and the ESP32 firmware compiles; the capture rig is not
assembled yet.

## Documents

| Document | Notes |
|---|---|
| [Documentation index](docs/INDEX-en.md) | Which document answers what, and what else changes with it |
| [SRS v1.10](docs/srs-en.md) | 29 functional requirements, 9 use cases, 13 tables, 36 acceptance items |
| [Plan](PLAN.md) | Phases, tasks and gates — the task contract for the team |
| [Architecture](docs/architecture-en.md) | Layers, dependency rules, runtime model, frame lifecycle |
| [API contract](docs/api-contract-en.md) | REST paths, response envelope, error codes, WebSocket protocol |
| [Data model](docs/data-model-en.md) | Thirteen tables, fields, indexes, file storage |
| [Test plan](docs/test-plan-en.md) | Test levels, dataset splitting, metrics and acceptance |
| [Glossary](docs/glossary-en-zh.md) | English ↔ Chinese, the single word list shared by code and docs |
| [Decisions](docs/adr/) | Ten accepted decisions and their reasoning; `docs/architecture-en.md` §10 lists them |

English is the source of truth for design documents; the Chinese files are reference versions and
must be updated in the same commit.

## Layout

```
docs/        design documents and the SRS
docs/adr/    architecture decision records
scripts/     dataset preparation, training, document checks
server/      FastAPI backend
web/         static frontend pages
firmware/    ESP32 firmware
tests/       tests
```

## Stack

| Layer | Choice |
|---|---|
| Capture | USB camera (1080P, manual exposure, UVC) with OpenCV |
| Detection | PyTorch + Ultralytics YOLOv8n, three improvements: underwater colour correction, EMA attention, WIoU v3 |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.1, PostgreSQL 14 |
| Frontend | HTML5, Bootstrap 5.3.3, ECharts 5, plain ES modules, no build step; libraries vendored in `web/static/vendor/` |
| Rig controller | ESP32-S3 on the Arduino framework, built with PlatformIO; a 0.96" OLED and two status LEDs |

Targets: mAP@0.5 ≥ 0.75 on the four species, +0.03 over the baseline, and
inference speed at least 90% of the baseline.

## Frontend preview

The pages need no build. Serve `web/` and open the login page:

```bash
python -m http.server 8765 --directory web
```

Then visit <http://localhost:8765/templates/login.html?mock=1>. The `?mock=1` flag runs the pages on
`web/static/mock/` for that browser tab, so the prototype opens with no backend; without it every page
calls the real API and asks for a sign-in.

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
