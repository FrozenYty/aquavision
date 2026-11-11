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
| `400xx` | Invalid request | `40001` missing parameter; `40002` invalid parameter |
| `401xx` | Not authenticated | `40101` token expired; `40102` not signed in |
| `403xx` | Not permitted | `40301` role cannot access |
| `404xx` | Not found | `40401` frame does not exist |
| `409xx` | State conflict | `40901` task already running |
| `500xx` | Server error | `50001` internal error |
| `501xx` | Mounted but not implemented | `50100` route not implemented |

Never return a bare HTTP 500 with a stack trace. Wrap it as `50001` and log the detail.

## 4. Authentication

`POST /api/auth/login` returns a JWT. Send it as `Authorization: Bearer <token>`.

- Token lifetime: 8 hours; no refresh token for this project.
- Roles: `observer`, `analyst`, `algo`, `admin`.
- Permissions are enforced server-side; hiding a menu item is presentation only.

## 5. Pagination and time

```
GET /api/frames?page=1&size=24&site=A3&start=2026-11-01&end=2026-11-03
```

```json
{ "items": [], "total": 412, "page": 1, "size": 24 }
```

- `size` defaults to 24, maximum 100.
- All timestamps are ISO 8601 with offset, stored in UTC, rendered in the local zone.
- Date filters are `start` and `end`, inclusive on both ends, interpreted in the server time zone. They are not named `from`/`to` because `from` is a reserved word in Python, and the parameter name is what appears in the generated OpenAPI document.

## 6. REST endpoints

Every route names the requirement it serves, and inherits that requirement's priority from SRS
Table 3-1. Scope questions are therefore answered by reading the SRS, not by counting rows here:
the number of routes is a consequence, not a target.

| Method | Path | Purpose | Requirement | Priority |
|---|---|---|---|---|
| POST | `/api/auth/login` | Obtain a token | FR-M1-01 | P0 |
| GET | `/api/auth/me` | Current user and role | FR-M1-01 | P0 |
| GET | `/api/users` | Accounts | FR-M1-03 | P1 |
| POST | `/api/users/{id}/status` | Disable or restore an account | FR-M1-03 | P1 |
| POST | `/api/users/{id}/reset-password` | Reset a password | FR-M1-03 | P1 |
| GET | `/api/logs` | Operation log | FR-M1-04 | P1 |
| GET | `/api/cameras` | Enumerate usable cameras | FR-M2-01 | P0 |
| POST | `/api/capture/sessions` | Open a capture session | FR-M2-01 | P0 |
| GET | `/api/capture/sessions` | List capture sessions | FR-M2-04 | P1 |
| POST | `/api/capture/sessions/{id}/frames` | Grab one frame | FR-M2-01 | P0 |
| POST | `/api/capture/sessions/{id}/close` | Close the session | FR-M2-01 | P0 |
| GET | `/api/frames` | Query frames | FR-M2-04 | P1 |
| GET | `/api/stats/quality` | Quality rejection rate | FR-M2-03 | P0 |
| POST | `/api/detect/frames/{frame_id}` | Detect on one frame | FR-M3-01 | P0 |
| POST | `/api/detect/batches` | Start a batch task | FR-M3-02 | P0 |
| GET | `/api/tasks` | List detection tasks | FR-M3-02 | P0 |
| GET | `/api/tasks/{task_id}` | Task progress | FR-M3-02 | P0 |
| POST | `/api/tasks/{id}/cancel` | Cancel a task | FR-M3-02 | P0 |
| POST | `/api/tasks/{id}/retry` | Retry a failed task | FR-M3-02 | P0 |
| GET | `/api/frames/{frame_id}` | Frame detail | FR-M3-04 | P0 |
| GET | `/api/frames/{frame_id}/objects` | Detection boxes | FR-M3-04 | P0 |
| POST | `/api/review/frames/{frame_id}` | Submit a review | FR-M4-01 | P0 |
| GET | `/api/review/frames/{frame_id}/versions` | Review version history | FR-M4-02 | P1 |
| POST | `/api/review/frames/{frame_id}/rollback` | Roll back to a review version | FR-M4-02 | P1 |
| GET | `/api/hard-samples` | Hard-example pool | FR-M4-03 | P1 |
| DELETE | `/api/hard-samples/{frame_id}` | Remove a hard example | FR-M4-03 | P1 |
| GET | `/api/datasets` | Dataset snapshots | FR-M4-04 | P1 |
| POST | `/api/datasets` | Export a dataset snapshot | FR-M4-04 | P1 |
| GET | `/api/stats/corrections` | Review correction distribution | FR-M4-02 | P1 |
| GET | `/api/stats/species` | Species composition | FR-M5-01 | P1 |
| GET | `/api/stats/trend` | Daily capture volume | FR-M5-03 | P2 |
| GET | `/api/reports` | Report history | FR-M5-04 | P1 |
| POST | `/api/reports` | Generate a report | FR-M5-04 | P1 |
| GET | `/api/models` | Model versions | FR-M6-01 | P0 |
| POST | `/api/models/{id}/activate` | Switch the online model | FR-M6-02 | P1 |
| GET | `/api/experiments` | Training experiments | FR-M6-03 | P0 |
| POST | `/api/compare/frames/{frame_id}` | Baseline vs improved, same frame | FR-M6-03 | P0 |
| GET | `/api/species` | Species dictionary and thresholds | FR-M6-04 | P0 |
| PATCH | `/api/species/{class_code}` | Update a species threshold | FR-M6-04 | P0 |
| GET | `/api/params` | System parameters | FR-M7-01 | P1 |
| PATCH | `/api/params` | Update system parameters | FR-M7-01 | P1 |
| POST | `/api/demo/reset` | Reset business data for a rehearsal | FR-M7-01 | P1 |
| GET | `/api/monitor` | Runtime monitoring | FR-M8-01 | P1 |
| GET | `/api/messages` | In-app messages | FR-M8-02 | P2 |
| POST | `/api/messages/{id}/read` | Mark a message read | FR-M8-02 | P2 |

### Frame object

```json
{
  "frame_id": "20261103T193012-0042",
  "session_id": "s-a3-001",
  "point_code": "A3",
  "captured_at": "2026-11-03T19:30:12.418+08:00",
  "quality": { "score": 66, "verdict": "ok" },
  "is_retake": false,
  "env": { "turbidity_rel": 12 },
  "width": 1920, "height": 1080
}
```

The three components behind the score — sharpness, brightness, colour cast — are returned by
`POST /api/capture/sessions/{id}/frames` in `quality_components` and are **not stored**: the frame table
keeps the score and the verdict, which is what every later decision reads. They are a diagnostic of the
moment, not a property of the image.

### Detection box

```json
{
  "object_id": 10231,
  "class_code": "holothurian",
  "confidence": 0.87,
  "x": 0.41, "y": 0.52, "w": 0.12, "h": 0.09,
  "is_manual": 0,
  "review_status": 0
}
```

- `object_id` — primary key of `detect_object`; the review page needs a stable handle to edit a box.
- `is_manual` — `0` detected, `1` drawn by a reviewer.
- `review_status` — `0` pending, `1` confirmed, `2` modified, `3` rejected.

### Review submission

```
POST /api/review/frames/{frame_id}
{ "objects": [ <Detection box> ], "note": "rock read as a sea cucumber, removed" }

→ { "version_no": 2, "object_count": 11, "hard_sample": true }
```

The request carries the full corrected set, not a diff: the reviewer's canvas is the authority, and a
diff would have to be merged against a version that may have moved on. `hard_sample` says whether the
frame entered the hard-example pool (FR-M4-03).

Each object in `objects` carries `object_id` (optional; omit it for a box drawn in review),
`class_code`, `confidence`, `x`, `y`, `w` and `h`; `is_manual` and `review_status` are set by the
server and are not read from the request. The response also reports `frame_id`, `rejected` (boxes
removed by this review), `added` (boxes drawn by hand) and the submitted `note`.

Coordinates are normalised to `0..1`, relative to the image, origin at the top-left corner.

### Review versions and rollback

```
GET /api/review/frames/{frame_id}/versions

→ {
  "frame_id": "20261103T193012-0042",
  "items": [
    {
      "log_id": 87,
      "action": "submit",
      "created_at": "2026-11-03T19:34:10+00:00",
      "author": "Gao Tianxiang",
      "before_count": 12,
      "after_count": 11
    }
  ]
}
```

`items` is newest first, one entry per `submit` or `rollback`. `before_count` and `after_count` are
parsed from the box lists stored with the entry, not recomputed from the frame's current boxes:
`before_count` counts every box stored at that moment (boxes already rejected earlier included), and
`after_count` counts the accepted set after the action. `author` is the display name, and is `null`
only for a row written by an automated action. A frame with no reviews answers an empty `items`; a
frame that does not exist answers `40401`.

```
POST /api/review/frames/{frame_id}/rollback
{ "log_id": 87 }

→ { "log_id": 87, "frame_id": "20261103T193012-0042", "version_no": 4, "object_count": 11,
    "hard_sample": true, "rejected": 2, "added": 1 }
```

Rollback restores the box set recorded as that entry's `after_value` as a **new** version; history is
never deleted or rewritten. Boxes in the frame but not in the target set are marked
`review_status = 3` (rejected) rather than removed; boxes in the target set with no current row are
added as manual boxes with `review_status = 2`. The action appends a `rollback` entry to the timeline
with its own before and after lists, and the response mirrors a review submission plus the `log_id`
it replayed. The roles are the same as a submission (`analyst`, `algo`, `admin`); reading the timeline
is open to every signed-in user. A `log_id` that does not exist answers `40401`; one that belongs to
another frame, or a target set equal to the current set, answers `40901` without writing anything.

### Dataset snapshot

```json
{
  "dataset_id": 3,
  "snapshot_name": "DS-V3",
  "split_ratio": "7:2:1",
  "seed": 42,
  "frame_count": 7782,
  "status": "ready",
  "created_at": "2026-11-06T15:40:00+00:00"
}
```

`status` is `building`, `ready` or `archived`. The per-frame membership lives in `dataset_item`, not in
the response: a snapshot with seven thousand frames is not a payload. The list and the export response
also carry `splits` with the per-split frame counts; the export response adds `groups` and
`manifest_path`.

### Report

```json
{
  "report_id": 12,
  "report_code": "RP261106-001",
  "period_start": "2026-11-01T00:00:00+00:00",
  "period_end": "2026-11-30T23:59:59+00:00",
  "template": "standard",
  "basis": "reviewed",
  "model_version_id": 3,
  "status": "ready",
  "error_msg": null,
  "file_path": "reports/RP261106-001.md",
  "created_at": "2026-11-06T15:41:00+00:00"
}
```

### Parameters

```json
{
  "retention_days": 30,
  "max_concurrency": 2,
  "detect_interval_ms": 300,
  "quality_threshold": 60,
  "camera_index": 0
}
```

`PATCH` takes any subset of these keys and returns `{ "params": { ... }, "changed": { ... } }`:
`params` is the full set, and `changed` names each key that changed with its before and after value.
Every change is also written to the audit log (AC-27).

### Demo reset

```
POST /api/demo/reset        (administrator only; the deployment must set AV_DEMO_ENABLED=1)

→ {
  "deleted": {
    "detect_object": 34, "detect_task_item": 20, "detect_task": 2, "report": 1,
    "dataset_item": 12, "dataset": 1, "train_experiment": 3, "sys_message": 4,
    "sys_log": 57, "media_asset": 12
  },
  "frame_files_removed": 12,
  "model_online": "v8n-E0-exploratory"
}
```

One call returns the system to the state a rehearsal starts from. The business rows are deleted in
foreign-key-safe order and the files under `<AV_DATA_DIR>/frames/` are removed with them; every table
touched reports its count, so an operator can see the reset instead of trusting a boolean. Two things
are deliberately kept: `model_version` (a rehearsal with no online model would answer "model weights
not registered" on its first capture) and `species_dict` (detection checks the model's class order
against it). `sys_user` and `sys_param` stay as well - deleting the caller's account mid-request would
be a lockout, not a reset.

The route is administrator-only. When `AV_DEMO_ENABLED` is off it answers `40401` with the message
"demo mode is not enabled", not `403`: a data-destroying endpoint does not need to be discoverable.
`model_online` is the version name left online, or `null` when no model is registered.

## 7. WebSocket protocol

`/ws/capture` — one connection per browser tab.

**Authentication.** The first message on every connection must be
`{"type": "auth", "token": "<JWT>"}`. The server answers `{"type": "auth_ok"}`. A missing, invalid or
expired token closes the socket with `4401`; no `auth` message within five seconds closes it with
`4408`. The token never travels in the query string — query strings leak into access logs and
referrers.

| Direction | Type | Payload |
|---|---|---|
| client → server | `auth` | `{ "token": "<JWT>" }` — must be the first message |
| server → client | `auth_ok` | `{}` |
| client → server | `start` | `{ "session_id": "...", "fps": 10, "detect_interval_ms": 300 }` |
| server → client | `frame` | `{ "frame_id": "...", "captured_at": "...", "quality": { "score": 66, "verdict": "ok" } }` |
| server → client | *binary* | one JPEG per message, the image of the `frame` message immediately before it |
| server → client | `detect` | `{ "frame_id": "...", "boxes": [], "latency_ms": 128, "model_version": "...", "conf_threshold": 0.4 }` |
| server → client | `status` | `{ "fps": 9.8, "queue": 0, "model": "v8n-e3" }` |
| client → server | `stop` | `{}` |

**Frame correlation.** A binary message and the `frame` message immediately before it form one frame
unit; the binary carries no id of its own. Results are correlated to frames by `frame_id`, never by
the order in which frames or results arrive. The quality score rides on the `frame` message, in the
same shape as the frame object in §6.

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
- Every detection response names the model version behind it — `model_version_id` on a task,
  `model_version` on the socket's `detect` message — so a result can be reproduced later.
