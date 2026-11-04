# Data model

> Chinese version: [data-model-zh.md](data-model-zh.md). This file is the source of truth.

## 1. Entities

Nine tables. Three of them carry the business core, the rest support it.

| Table | Purpose | Key columns |
|---|---|---|
| `sys_user` | Accounts, roles, login state | `user_id`, `role_code`, `status` |
| `sys_log` | Audit trail of key actions | `log_id`, `action`, `before_value`, `after_value` |
| `media_asset` | One captured frame and its metadata | `asset_id`, `frame_id`, `session_id`, `quality_score` |
| `detect_task` | One detection run: model, parameters, progress | `task_id`, `model_version_id`, `status` |
| `detect_object` | One detection box | `object_id`, `task_id`, `class_code`, `confidence` |
| `species_dict` | Class definitions and per-class thresholds | `class_code`, `cn_name`, `category` |
| `model_version` | Weight file, metrics, online state | `model_id`, `version_name`, `is_online` |
| `train_experiment` | Dataset snapshot, hyper-parameters, metrics | `exp_id`, `dataset_snapshot`, `seed` |
| `sys_message` | In-app notifications | `msg_id`, `msg_type`, `is_read` |

## 2. Naming and types

- Table names: `snake_case`, singular concept, prefixed by domain (`sys_`, `media_`, `detect_`).
- Primary keys: `BIGINT AUTO_INCREMENT`, named `<entity>_id`.
- Foreign keys: same name as the referenced key, always indexed.
- Timestamps: `TIMESTAMP`, stored in UTC, named `*_at`.
- Booleans: `SMALLINT` with `0/1`, named `is_*` or `*_flag`.
- Enumerations: `SMALLINT` with a documented value map, never a database `ENUM` type.
- Money: `NUMERIC(10,2)`; ratios and coordinates: `NUMERIC(5,4)` or `NUMERIC(8,5)`.

Never store a comma-separated list in a column. If a value repeats, it belongs in its own table.

## 3. Core tables

### media_asset

| Column | Type | Notes |
|---|---|---|
| `asset_id` | BIGINT | PK |
| `frame_id` | VARCHAR(32) | Unique, `YYYYMMDDTHHMMSS-mmmm` |
| `session_id` | VARCHAR(32) | One continuous capture session |
| `file_path` | VARCHAR(512) | Relative to `data/` |
| `captured_at` | TIMESTAMP | UTC, millisecond precision |
| `width`, `height` | INT | Pixels |
| `exposure_us`, `gain_db` | INT / NUMERIC(5,2) | Capture parameters, kept for reproducibility |
| `quality_score` | SMALLINT | 0–100 |
| `quality_flag` | SMALLINT | 0 ok, 1 needs retake |
| `water_temp_c` | NUMERIC(5,2) | Nullable, from sensor |
| `turbidity_ntu` | NUMERIC(6,2) | Nullable, from sensor |

### detect_object

| Column | Type | Notes |
|---|---|---|
| `object_id` | BIGINT | PK |
| `task_id` | BIGINT | FK to `detect_task` |
| `frame_id` | VARCHAR(32) | Denormalised for fast lookup |
| `class_code` | VARCHAR(32) | FK to `species_dict` |
| `confidence` | NUMERIC(5,4) | 0–1 |
| `x`, `y`, `w`, `h` | NUMERIC(8,5) | Normalised box, origin top-left |
| `is_manual` | SMALLINT | 0 auto, 1 drawn by a reviewer |
| `review_status` | SMALLINT | 0 pending, 1 confirmed, 2 modified, 3 rejected |
| `hard_flag` | SMALLINT | Candidate for the hard-sample pool |

### species_dict

Four rows at launch: `holothurian`, `strongylocentrotus`, `chlamys`, `asterias`.

| Column | Type | Notes |
|---|---|---|
| `class_code` | VARCHAR(32) | Must match `labels.txt` of the model, exactly and in order |
| `cn_name` | VARCHAR(32) | Display name |
| `category` | SMALLINT | 1 economic, 2 pest, 3 environment (reserved, no class yet) |
| `conf_thr` | NUMERIC(4,2) | Per-class threshold, default 0.50 |
| `in_stat` | SMALLINT | Whether the class counts toward statistics |

**`class_code` order is a contract.** If the order in `labels.txt` and `species_dict` diverges,
every result is mislabelled; the loader must verify both at startup and refuse to run otherwise.

## 4. Indices

| Table | Index | Reason |
|---|---|---|
| `media_asset` | `(session_id, captured_at)` | Frame list per session |
| `media_asset` | `(captured_at)` | Date-range queries |
| `detect_object` | `(frame_id)` | Fetch boxes for one frame |
| `detect_object` | `(task_id, class_code)` | Per-task class counts |
| `sys_log` | `(created_at)` | Audit queries by date |

## 5. File storage

```
data/
  frames/YYYY/MM/DD/<session_id>/<frame_id>.jpg
  thumbs/YYYY/MM/DD/<frame_id>.jpg
  results/<frame_id>.json
  models/<version_name>/{best.pt,labels.txt,metrics.json}
  exports/
```

The database stores relative paths only. Moving the data root is a configuration change, never a
migration.

## 6. Lifecycle

- Frames are kept indefinitely; thumbnails and intermediate files expire after 90 days.
- Deleting a frame is a soft delete first, physical removal after 7 days.
- Model versions are never deleted once online; they are marked offline.
- Logs are kept 180 days, then exported and dropped.
