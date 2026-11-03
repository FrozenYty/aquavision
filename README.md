# AquaVision

[中文](README-zh.md)

Underwater species detection and monitoring built on YOLOv8. A live camera feed is analysed to
count and locate five classes — sea cucumber, sea urchin, scallop, starfish and marine debris —
with a human review loop that feeds corrections back into training.

**Status**: requirements complete; SRS v1.2 under review. No code yet.

## Documents

| Document | Notes |
|---|---|
| [SRS v1.2](docs/srs-v1.2.docx) | 29 functional requirements, 9 use cases, 9 tables, 36 acceptance items |
| [Plan](PLAN.md) | Phases, tasks and gates — the task contract for the team |
| [Architecture](docs/architecture-en.md) | Layers, dependency rules, runtime model, frame lifecycle |
| [API contract](docs/api-contract-en.md) | REST paths, response envelope, error codes, WebSocket protocol |
| [Data model](docs/data-model-en.md) | Nine tables, fields, indexes, file storage |
| [Test plan](docs/test-plan-en.md) | Test levels, dataset splitting, metrics and acceptance |
| [Glossary](docs/glossary-en-zh.md) | English ↔ Chinese, the single word list shared by code and docs |
| [Decisions](docs/adr/) | Four accepted architecture decisions and their reasoning |

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
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL 14 |
| Frontend | HTML5, Bootstrap 5, ECharts 5 |

Targets: mAP@0.5 ≥ 0.75 on the four species, ≥ 0.60 on debris, +0.03 over the baseline, and
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
