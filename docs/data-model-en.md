# Data model

> Chinese version: [data-model-zh.md](data-model-zh.md). This file is the source of truth.
> Synced: 2026-11-06

> Owner: @Gtechson · Revisit when: a table or a column changes

## 1. Entities

Fourteen tables. Three of them carry the business core, the rest support it. Four were added after
the skeleton proved the original nine could not hold what the requirements ask for — see ADR 08 for
why, and `srs-en.md` §4.1 for the revised decision — and `detect_task_item` followed when a task's
frame list moved from a query every worker re-ran to a set the task owns (ADR 12).

| Table | Purpose | Columns |
|---|---|---|
| `sys_user` | Accounts, roles, login state | 14 |
| `sys_log` | Audit trail of key actions | 10 |
| `media_asset` | One captured frame and its metadata | 18 |
| `detect_task` | One detection run: model, parameters, progress | 16 |
| `detect_object` | One detection box | 19 |
| `species_dict` | Class definitions and per-class thresholds | 10 |
| `model_version` | Weight file, metrics, online state | 14 |
| `train_experiment` | Dataset snapshot, hyper-parameters, metrics | 18 |
| `sys_message` | In-app notifications | 10 |
| `sys_param` | Runtime configuration, key/value, audited | 7 |
| `dataset` | An exported dataset snapshot | 9 |
| `dataset_item` | One frame in one snapshot, and its split | 5 |
| `report` | A generated inspection report and its file | 12 |
| `detect_task_item` | One frame assigned to one detection task, with its state and box count | 7 |

## 2. Naming and types

- Table names: `snake_case`, singular concept, prefixed by domain (`sys_`, `media_`, `detect_`).
- Primary keys: `BIGINT AUTO_INCREMENT`, named `<entity>_id`.
- Foreign keys: same name as the referenced key, always indexed.
- Timestamps: `TIMESTAMP`, stored in UTC, named `*_at`.
- Booleans: `SMALLINT` with `0/1`, named `is_*` or `*_flag`.
- Enumerations: `SMALLINT` with a documented value map, never a database `ENUM` type.
- Money: `NUMERIC(10,2)`; ratios and coordinates: `NUMERIC(5,4)` or `NUMERIC(8,5)`.
- Column names are always lower case: the SRS writes `mAP50`/`mAP5095`, the columns are
  `map50`/`map50_95` (PostgreSQL folds unquoted identifiers to lower case).

Never store a comma-separated list in a column. If a value repeats, it belongs in its own table.
The single exception is `detect_task.class_filter`: it holds a **JSON array** such as
`["holothurian","chlamys"]`, NULL meaning all classes — it is configuration, not an entity, and
does not justify a table of its own.

## 3. Table structure

One column per row; types and constraints are ready for DDL. Enumerations are integer codes in
storage, rendered as Chinese text in the UI.

### 3.1 sys_user

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `user_id` | BIGINT | PK, auto increment | Primary key |
| `username` | VARCHAR(64) | UNIQUE, NOT NULL | Login name |
| `phone` | VARCHAR(20) | UNIQUE, NULL | Phone, masked on display |
| `email` | VARCHAR(128) | UNIQUE, NULL | Email; phone or email, at least one |
| `password_hash` | VARCHAR(128) | NOT NULL | Salted password hash |
| `salt` | VARCHAR(32) | NOT NULL | Password salt |
| `role_code` | VARCHAR(16) | NOT NULL | observer／analyst／algo／admin |
| `real_name` | VARCHAR(64) | NOT NULL | Real name |
| `status` | SMALLINT | DEFAULT 1 | 1 active, 0 disabled |
| `fail_count` | SMALLINT | DEFAULT 0 | Consecutive login failures |
| `locked_until` | TIMESTAMP | NULL | Lock expiry |
| `last_login_at` | TIMESTAMP | NULL | Last login time |
| `token_epoch` | INT | DEFAULT 0 | Bumped on a password change; a token carries the value it was issued under and an older one is refused (NFR-S-05) |
| `created_at` | TIMESTAMP | DEFAULT now() | Creation time |

### 3.2 sys_log

Append only; never updated or deleted in place (archival is an export).

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `log_id` | BIGINT | PK, auto increment | Primary key |
| `user_id` | BIGINT | FK→sys_user, NULL | Actor; NULL for automated actions |
| `module` | VARCHAR(32) | NOT NULL | Module tag |
| `action` | VARCHAR(32) | NOT NULL | login / review / deploy / config |
| `target_type` | VARCHAR(32) | NULL | Object type |
| `target_id` | VARCHAR(64) | NULL | Object id |
| `before_value` | TEXT | NULL | Value before (JSON) |
| `after_value` | TEXT | NULL | Value after (JSON) |
| `ip` | VARCHAR(64) | NULL | Source IP |
| `created_at` | TIMESTAMP | DEFAULT now() | Time of action |

### 3.3 media_asset

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `asset_id` | BIGINT | PK, auto increment | Primary key |
| `frame_id` | VARCHAR(32) | UNIQUE, NOT NULL | Frame id, `YYYYMMDDTHHMMSS-mmmm` |
| `session_id` | VARCHAR(32) | NOT NULL | Same value across one continuous capture |
| `point_code` | VARCHAR(32) | NOT NULL | Monitoring point |
| `file_path` | VARCHAR(512) | NOT NULL | Frame path relative to `data/` |
| `thumb_path` | VARCHAR(512) | NULL | Thumbnail path |
| `file_size` | BIGINT | NOT NULL | Bytes |
| `file_hash` | CHAR(64) | NOT NULL | SHA-256, for dedup |
| `captured_at` | TIMESTAMP | NOT NULL | Capture time, UTC, millisecond precision |
| `width` | INT | NOT NULL | Pixels |
| `height` | INT | NOT NULL | Pixels |
| `exposure_us` | INT | NULL | Exposure (µs), kept for reproducibility |
| `gain_db` | NUMERIC(5,2) | NULL | Gain (dB), kept for reproducibility |
| `quality_score` | SMALLINT | DEFAULT 0 | Quality score 0–100 |
| `quality_flag` | SMALLINT | DEFAULT 0 | 0 ok, 1 needs retake |
| `is_retake` | SMALLINT | DEFAULT 0 | Is a retaken frame |
| `created_at` | TIMESTAMP | DEFAULT now() | Ingestion time |

### 3.4 detect_task

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `task_id` | BIGINT | PK, auto increment | Primary key |
| `task_code` | VARCHAR(32) | UNIQUE, NOT NULL | Task code, `DTyyMMdd-serial` |
| `task_type` | SMALLINT | NOT NULL | 1 live, 2 batch |
| `model_version_id` | BIGINT | FK→model_version, NULL | Model version used |
| `asset_count` | INT | NOT NULL | Frame count |
| `conf_thr` | NUMERIC(4,2) | DEFAULT 0.50 | Confidence threshold |
| `iou_thr` | NUMERIC(4,2) | DEFAULT 0.45 | IoU threshold |
| `max_det` | INT | DEFAULT 100 | Max detections per image |
| `class_filter` | VARCHAR(256) | NULL | Class codes as a **JSON array**; NULL = all classes |
| `status` | SMALLINT | DEFAULT 0 | 0 queued / 1 running / 2 done / 3 failed / 4 cancelled |
| `progress` | SMALLINT | DEFAULT 0 | Progress percent |
| `obj_count` | INT | DEFAULT 0 | Total objects |
| `error_msg` | VARCHAR(512) | NULL | Failure reason |
| `created_by` | BIGINT | FK→sys_user, NULL | Creator |
| `created_at` | TIMESTAMP | DEFAULT now() | Creation time |
| `finished_at` | TIMESTAMP | NULL | Finish time |

### 3.5 detect_object

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `object_id` | BIGINT | PK, auto increment | Primary key |
| `task_id` | BIGINT | FK→detect_task, NOT NULL | Owning task |
| `asset_id` | BIGINT | FK→media_asset, NOT NULL | Frame |
| `frame_id` | VARCHAR(32) | NOT NULL | Frame id, denormalised for fast lookup |
| `class_code` | VARCHAR(32) | FK→species_dict, NOT NULL | Class code |
| `confidence` | NUMERIC(5,4) | NOT NULL | Confidence 0–1 |
| `x` | NUMERIC(8,5) | NOT NULL | Normalised box, left edge |
| `y` | NUMERIC(8,5) | NOT NULL | Normalised box, top edge |
| `w` | NUMERIC(8,5) | NOT NULL | Normalised box width |
| `h` | NUMERIC(8,5) | NOT NULL | Normalised box height |
| `track_id` | BIGINT | NULL | Tracking id for in-frame dedup |
| `is_manual` | SMALLINT | DEFAULT 0 | 0 auto, 1 drawn by a reviewer |
| `review_status` | SMALLINT | DEFAULT 0 | 0 pending / 1 confirmed / 2 modified / 3 rejected |
| `version_no` | INT | DEFAULT 1 | Result version, +1 per review |
| `hard_flag` | SMALLINT | DEFAULT 0 | Candidate for the hard-sample pool |
| `hard_reason` | VARCHAR(32) | NULL | low_conf / modified / inconsistent |
| `reviewed_by` | BIGINT | FK→sys_user, NULL | Reviewer |
| `reviewed_at` | TIMESTAMP | NULL | Review time |
| `created_at` | TIMESTAMP | DEFAULT now() | Creation time |

**One automatic result per frame.** Re-running detection replaces the rows where `is_manual = 0`
rather than appending a second set, which every count would multiply; boxes a reviewer drew are kept,
because the model cannot reproduce them. A set that a review already recorded is not lost: it stays
in that review's `sys_log` row, with the before and after values.

### 3.6 species_dict

Four seed rows at launch: `holothurian`, `strongylocentrotus`, `chlamys`, `asterias`.

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `species_id` | BIGINT | PK, auto increment | Primary key |
| `class_code` | VARCHAR(32) | UNIQUE, NOT NULL | Must match `labels.txt` of the model, exactly and in order |
| `cn_name` | VARCHAR(32) | NOT NULL | Display name |
| `latin_name` | VARCHAR(64) | NULL | Latin name |
| `category` | SMALLINT | NOT NULL | 1 economic / 2 pest / 3 environment |
| `conf_thr` | NUMERIC(4,2) | DEFAULT 0.50 | Per-class confidence threshold |
| `in_stat` | SMALLINT | DEFAULT 1 | Counts toward statistics |
| `status` | SMALLINT | DEFAULT 1 | 1 active, 0 disabled |
| `remark` | VARCHAR(255) | NULL | Morphology and hazard notes |
| `created_at` | TIMESTAMP | DEFAULT now() | Creation time |

**`class_code` order is a contract.** If the order in `labels.txt` and `species_dict` diverges,
every result is mislabelled; the loader must verify both at startup and refuse to run otherwise.

### 3.7 model_version

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `model_id` | BIGINT | PK, auto increment | Primary key |
| `version_name` | VARCHAR(64) | UNIQUE, NOT NULL | Version name, e.g. `v8n-E3-001` |
| `weight_path` | VARCHAR(512) | NOT NULL | Path to the `.pt` weights |
| `onnx_path` | VARCHAR(512) | NULL | ONNX path |
| `labels_path` | VARCHAR(512) | NOT NULL | Path to the class-order file |
| `dataset_ref` | VARCHAR(128) | NULL | Dataset snapshot id |
| `map50` | NUMERIC(5,4) | NULL | mAP@0.5 |
| `map50_95` | NUMERIC(5,4) | NULL | mAP@0.5:0.95 |
| `recall_avg` | NUMERIC(5,4) | NULL | Average recall |
| `fps` | NUMERIC(6,2) | NULL | Inference FPS |
| `params_m` | NUMERIC(6,2) | NULL | Parameters, millions |
| `status` | SMALLINT | DEFAULT 0 | 0 candidate / 1 online / 2 offline |
| `is_online` | SMALLINT | DEFAULT 0 | Currently the online model |
| `created_at` | TIMESTAMP | DEFAULT now() | Registration time |

### 3.8 train_experiment

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `exp_id` | BIGINT | PK, auto increment | Primary key |
| `exp_name` | VARCHAR(64) | NOT NULL | Experiment name, e.g. `E3` |
| `model_version_id` | BIGINT | FK→model_version, NULL | Produced model |
| `dataset_snapshot` | VARCHAR(128) | NOT NULL | Dataset snapshot id |
| `split_ratio` | VARCHAR(16) | NOT NULL | Split, e.g. `7:2:1` |
| `seed` | INT | NOT NULL | Random seed |
| `epochs` | INT | NOT NULL | Training epochs |
| `batch_size` | INT | NOT NULL | Batch size |
| `lr` | NUMERIC(8,6) | NOT NULL | Initial learning rate |
| `augment_json` | TEXT | NULL | Augmentation config (JSON) |
| `map50` | NUMERIC(5,4) | NULL | mAP@0.5 |
| `map50_95` | NUMERIC(5,4) | NULL | mAP@0.5:0.95 |
| `recall_avg` | NUMERIC(5,4) | NULL | Average recall |
| `fps` | NUMERIC(6,2) | NULL | Inference FPS |
| `params_m` | NUMERIC(6,2) | NULL | Parameters, millions |
| `is_baseline` | SMALLINT | DEFAULT 0 | Baseline experiment |
| `note` | VARCHAR(255) | NULL | What was changed |
| `created_at` | TIMESTAMP | DEFAULT now() | Record time |

### 3.9 sys_message

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `msg_id` | BIGINT | PK, auto increment | Primary key |
| `msg_type` | VARCHAR(32) | NOT NULL | capture_failed / task_failed / report_done |
| `level` | SMALLINT | DEFAULT 1 | 1 info / 2 warning / 3 critical |
| `title` | VARCHAR(128) | NOT NULL | Title |
| `content` | VARCHAR(512) | NULL | Body |
| `target_role` | VARCHAR(16) | NULL | Target role, NULL = everyone |
| `ref_type` | VARCHAR(32) | NULL | Referenced object type |
| `ref_id` | VARCHAR(64) | NULL | Referenced object id |
| `is_read` | SMALLINT | DEFAULT 0 | 0 unread, 1 read |
| `created_at` | TIMESTAMP | DEFAULT now() | Creation time |

### 3.10 sys_param

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `param_id` | BIGINT | PK, auto increment | Primary key |
| `param_key` | VARCHAR(64) | NOT NULL, unique | `retention_days`, `max_concurrency`, ... |
| `param_value` | VARCHAR(255) | NOT NULL | Stored as text |
| `value_type` | VARCHAR(16) | NOT NULL | int / float / bool / str — how to cast it back |
| `remark` | VARCHAR(255) | NULL | What the parameter does |
| `updated_by` | BIGINT | FK sys_user, NULL | Who changed it last |
| `updated_at` | TIMESTAMP | DEFAULT now() | When |

Key/value rather than one column per setting: adding a parameter must not require a migration.

### 3.11 dataset

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `dataset_id` | BIGINT | PK, auto increment | Primary key |
| `snapshot_name` | VARCHAR(64) | NOT NULL, unique | `DS-V3` |
| `manifest_path` | VARCHAR(512) | NOT NULL | Human-readable copy of the list |
| `split_ratio` | VARCHAR(16) | NOT NULL | `7:2:1` |
| `seed` | INT | NOT NULL | Split seed; same seed, same splits (AC-18) |
| `frame_count` | INT | NOT NULL | Size of the snapshot |
| `status` | SMALLINT | DEFAULT 1 | 0 building / 1 ready / 2 archived |
| `created_by` | BIGINT | FK sys_user, NULL | Who exported it |
| `created_at` | TIMESTAMP | DEFAULT now() | When |

A snapshot exists before any experiment references it: export happens now, training happens later.

### 3.12 dataset_item

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `item_id` | BIGINT | PK, auto increment | Primary key |
| `dataset_id` | BIGINT | FK dataset, NOT NULL | Owning snapshot |
| `asset_id` | BIGINT | FK media_asset, NOT NULL | Frame in it |
| `split` | SMALLINT | NOT NULL | 1 train / 2 val / 3 test |
| `group_key` | VARCHAR(64) | NULL | Similarity group; never crosses splits |

Unique on (`dataset_id`, `asset_id`); indexed on (`dataset_id`, `split`).

### 3.13 report

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `report_id` | BIGINT | PK, auto increment | Primary key |
| `report_code` | VARCHAR(32) | NOT NULL, unique | `RPyyMMdd-serial` |
| `period_start` | TIMESTAMP | NOT NULL | Statistics period, inclusive |
| `period_end` | TIMESTAMP | NOT NULL | Statistics period, inclusive |
| `template` | VARCHAR(16) | NOT NULL | standard / brief |
| `basis` | VARCHAR(16) | NOT NULL | reviewed / raw |
| `model_version_id` | BIGINT | FK model_version, NULL | Version in force when generated |
| `file_path` | VARCHAR(512) | NULL | The document itself |
| `status` | SMALLINT | DEFAULT 0 | 0 generating / 1 ready / 2 failed |
| `error_msg` | VARCHAR(255) | NULL | Why it failed |
| `created_by` | BIGINT | FK sys_user, NULL | Who asked for it |
| `created_at` | TIMESTAMP | DEFAULT now() | When |

The document is a file; this row is what makes the history queryable by period, template and basis.

### 3.14 detect_task_item

A task's work list, written when the task is created. Each row is one frame the task owns.

| Column | Type | Constraint / default | Notes |
|---|---|---|---|
| `item_id` | BIGINT | PK, auto increment | Primary key |
| `task_id` | BIGINT | FK→detect_task, NOT NULL | Owning task |
| `asset_id` | BIGINT | FK→media_asset, NOT NULL | Frame assigned to it |
| `state` | SMALLINT | DEFAULT 0 | 0 pending / 1 running / 2 done / 3 failed |
| `box_count` | INT | DEFAULT 0 | Objects found; 0 is a result, not an absence |
| `claimed_at` | TIMESTAMP | NULL | When a worker claimed it |
| `finished_at` | TIMESTAMP | NULL | When detection finished for it |

Unique on (`task_id`, `asset_id`); indexed on (`task_id`, `state`) to claim the next pending item.

A frame with no objects is recorded as `done` with `box_count = 0`: zero is a result, not the absence
of one, so no later task picks the frame up again.

## 4. Indices

Foreign-key columns are always indexed (rule in §2); this table lists composite and
high-traffic single-column indices only:

| Table | Index | Reason |
|---|---|---|
| `media_asset` | `(session_id, captured_at)` | Frame list per session |
| `media_asset` | `(captured_at)` | Date-range queries |
| `media_asset` | `(file_hash)` | Dedup on ingest |
| `detect_object` | `(frame_id)` | Fetch boxes for one frame |
| `detect_object` | `(task_id, class_code)` | Per-task class counts |
| `detect_object` | `(review_status)` | Review queue |
| `sys_log` | `(created_at)` | Audit queries by date |
| `detect_task_item` | `(task_id, asset_id)` | Unique: one item per frame per task |
| `detect_task_item` | `(task_id, state)` | Claim the next pending item of a task |

## 5. File storage

Two roots, and the split matters: one is delivered with the code, the other is produced at run time.

```
models/<version_name>/        delivered, tracked in the repository (ADR 13)
  best.pt  labels.txt  metrics.json

data/                         runtime, ignored by git, moves with AV_DATA_DIR
  app.db                      the SQLite file, unless DB_DSN names another database
  frames/<site>/<YYYYMMDD>/<session>/<digest[:16]>.jpg
  datasets/<snapshot_name>/manifest.json
  reports/<report_code>.md
```

The frame filename is the content-hash prefix deduplication already computed (AC-05), not `frame_id`;
that id lives in the `media_asset` row. The code writes only `frames/`, `datasets/` and `reports/`
under the data root, beside the SQLite file: there are no `thumbs/`, `results/` or `exports/`
directories, because nothing generates them.

The delivered model sits at the repository root rather than under `data/` on purpose: a tracked
artefact must not live under a directory whose location is a configuration value.

The database stores relative paths only. A delivered weight's path resolves against the repository root,
so a registration made on one machine is valid on another. Moving the data root is a configuration
change, never a migration.

## 6. Lifecycle

- Frames are kept indefinitely; thumbnails and intermediate files are cleanup candidates after `retention_days` (30 by default, `AV_RETENTION_DAYS`).
- Deleting a frame is a soft delete first, physical removal after 7 days.
- Model versions are never deleted once online; they are marked offline.
- A detection task writes its item rows when it is created; a restart returns `running` items to
  pending and leaves finished ones finished, so a resumed batch does not reprocess frames it already
  has results for.
- Logs are kept 180 days, then exported and dropped.
