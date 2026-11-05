# API contract

> Chinese version: [api-contract-zh.md](api-contract-zh.md). This file is the source of truth.

> Owner: @Gtechson · Revisit when: an endpoint or a field changes

## 1. Conventions

- Base path: `/api`. All endpoints return JSON.
- Methods follow REST: `GET` reads, `POST` creates or acts, `PATCH` updates, `DELETE` removes.
- Field names are `snake_case` in both JSON and the database.
- Identifiers are integers (`BIGINT`) unless stated otherwise.

## 2. Response envelope

Every response, success or failure:

```json
{ "code": 0, "message": "ok", "data": { }, "request_id": "req-7f3a" }
```

- `code` — `0` on success; non-zero means failure.
- `message` — human readable, Chinese, safe to show directly in the UI.
- `data` — the payload, `null` on failure.
- `request_id` — present on every response, echoed in server logs.

## 3. Error codes

| Range | Meaning | Example |
|---|---|---|
| `400xx` | Invalid request | `40001` missing parameter |
| `401xx` | Not authenticated | `40101` token expired |
| `403xx` | Not permitted | `40301` role cannot access |
| `404xx` | Not found | `40401` frame does not exist |
| `409xx` | State conflict | `40901` task already running |
| `500xx` | Server error | `50001` internal error |

Never return a bare HTTP 500 with a stack trace. Wrap it as `50001` and log the detail.

## 4. Authentication

`POST /api/auth/login` returns a JWT. Send it as `Authorization: Bearer <token>`.

- Token lifetime: 8 hours; no refresh token for this project.
- Roles: `observer`, `analyst`, `algo`, `admin`.
- Permissions are enforced server-side; hiding a menu item is presentation only.

## 5. Pagination and time

```
GET /api/frames?page=1&size=24&site=A3&from=2026-11-01&to=2026-11-03
```

```json
{ "items": [], "total": 412, "page": 1, "size": 24 }
```

- `size` defaults to 24, maximum 100.
- All timestamps are ISO 8601 with offset, stored in UTC, rendered in the local zone.
- Date filters are inclusive on both ends, interpreted in the server time zone.

## 6. REST endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/login` | Obtain a token |
| GET | `/api/auth/me` | Current user and role |
| GET | `/api/cameras` | Enumerate usable cameras |
| POST | `/api/capture/sessions` | Open a capture session |
| POST | `/api/capture/sessions/{id}/frames` | Grab one frame |
| POST | `/api/capture/sessions/{id}/close` | Close the session |
| POST | `/api/detect/frames/{frame_id}` | Detect on one frame |
| POST | `/api/detect/batches` | Start a batch task |
| GET | `/api/tasks/{task_id}` | Task progress |
| GET | `/api/frames` | Query frames |
| GET | `/api/frames/{frame_id}` | Frame detail |
| GET | `/api/frames/{frame_id}/objects` | Detection boxes |
| POST | `/api/review/frames/{frame_id}` | Submit a review |
| POST | `/api/compare/frames/{frame_id}` | Baseline vs improved, same frame |
| GET | `/api/stats/species` | Species composition |
| GET | `/api/stats/quality` | Quality rejection rate |
| GET | `/api/models` | Model versions |
| POST | `/api/models/{id}/activate` | Switch the online model |

### Frame object

```json
{
  "frame_id": "20261103T193012-0042",
  "session_id": "s-a3-001",
  "captured_at": "2026-11-03T19:30:12.418+08:00",
  "quality": { "sharpness": 71, "brightness": 64, "colorcast": 58, "score": 66, "verdict": "ok" },
  "env": { "turbidity_rel": 12 },
  "width": 1920, "height": 1080
}
```

### Detection box

```json
{ "class_code": "holothurian", "confidence": 0.87, "x": 0.41, "y": 0.52, "w": 0.12, "h": 0.09 }
```

Coordinates are normalised to `0..1`, relative to the image, origin at the top-left corner.

## 7. WebSocket protocol

`/ws/capture` — one connection per browser tab.

| Direction | Type | Payload |
|---|---|---|
| client → server | `start` | `{ "session_id": "...", "fps": 10, "detect_interval_ms": 300 }` |
| server → client | *binary* | JPEG bytes, one frame per message |
| server → client | `detect` | `{ "frame_id": "...", "boxes": [], "latency_ms": 128 }` |
| server → client | `status` | `{ "fps": 9.8, "queue": 0, "model": "v8n-e3" }` |
| client → server | `stop` | `{}` |

Images travel as binary frames; results travel as JSON. They are correlated by `frame_id`,
never by order.

## 8. Frame and result alignment

- The server assigns `frame_id` at capture time and includes it in every result.
- The client keeps a small map of `frame_id → boxes` and renders a box set only if a newer
  frame has not arrived.
- **Stale results are dropped.** A box set for a frame older than the newest displayed frame is
  discarded, not queued.
- `latency_ms` is measured from frame capture to result construction on the server.

## 9. Versioning

- Breaking changes bump the path: `/api/v2/...`. Within v1, fields may be added, never removed
  or renamed.
- Every detection response records `model_version` and `conf_threshold`, so a result can be
  reproduced later.
