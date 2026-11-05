# 数据模型

> 本文为 `data-model-en.md` 的中文对照版，以英文版为准。
> 同步于：2026-11-03

> 维护人：@Gtechson · 重审时机：加表或加字段时

## 一、实体

九张表。三张承载业务主干，其余是支撑。

| 表 | 作用 | 关键列 |
|---|---|---|
| `sys_user` | 账号、角色、登录状态 | `user_id`、`role_code`、`status` |
| `sys_log` | 关键操作的审计记录 | `log_id`、`action`、`before_value`、`after_value` |
| `media_asset` | 一帧影像及其元数据 | `asset_id`、`frame_id`、`session_id`、`quality_score` |
| `detect_task` | 一次识别的模型、参数与进度 | `task_id`、`model_version_id`、`status` |
| `detect_object` | 一个检测框 | `object_id`、`task_id`、`class_code`、`confidence` |
| `species_dict` | 类别定义与分类别阈值 | `class_code`、`cn_name`、`category` |
| `model_version` | 权重、指标与上线状态 | `model_id`、`version_name`、`is_online` |
| `train_experiment` | 数据集快照、超参与指标 | `exp_id`、`dataset_snapshot`、`seed` |
| `sys_message` | 站内消息 | `msg_id`、`msg_type`、`is_read` |

## 二、命名与类型

- 表名 `snake_case`，按业务域加前缀（`sys_`、`media_`、`detect_`）。
- 主键统一 `BIGINT AUTO_INCREMENT`，命名为 `<实体>_id`。
- 外键与被引用键同名，必须建索引。
- 时间统一 `TIMESTAMP`，存 UTC，命名为 `*_at`。
- 布尔用 `SMALLINT` 的 `0/1`，命名 `is_*` 或 `*_flag`。
- 枚举用 `SMALLINT` 加文档化的取值表，**不用**数据库 `ENUM` 类型。
- 金额 `NUMERIC(10,2)`；比率与坐标 `NUMERIC(5,4)` 或 `NUMERIC(8,5)`。

禁止在列里存逗号分隔的列表。一个值要重复出现，就该有自己的一张表。

## 三、核心表

### media_asset

| 列 | 类型 | 说明 |
|---|---|---|
| `asset_id` | BIGINT | 主键 |
| `frame_id` | VARCHAR(32) | 唯一，格式 `YYYYMMDDTHHMMSS-mmmm` |
| `session_id` | VARCHAR(32) | 一次连续采集 |
| `file_path` | VARCHAR(512) | 相对 `data/` 的路径 |
| `captured_at` | TIMESTAMP | UTC，毫秒精度 |
| `width`、`height` | INT | 像素 |
| `exposure_us`、`gain_db` | INT / NUMERIC(5,2) | 采集参数，用于复现 |
| `quality_score` | SMALLINT | 0–100 |
| `quality_flag` | SMALLINT | 0 合格，1 需重拍 |
| `turbidity_rel` | SMALLINT | 0–100，0 为清澈；无传感器时为空 |

### detect_object

| 列 | 类型 | 说明 |
|---|---|---|
| `object_id` | BIGINT | 主键 |
| `task_id` | BIGINT | 外键，指向 `detect_task` |
| `frame_id` | VARCHAR(32) | 冗余存放，便于快查 |
| `class_code` | VARCHAR(32) | 外键，指向 `species_dict` |
| `confidence` | NUMERIC(5,4) | 0–1 |
| `x`、`y`、`w`、`h` | NUMERIC(8,5) | 归一化框，原点左上 |
| `is_manual` | SMALLINT | 0 自动，1 人工补画 |
| `review_status` | SMALLINT | 0 待复核，1 已确认，2 已修改，3 已驳回 |
| `hard_flag` | SMALLINT | 是否进难例池 |

### species_dict

上线时四行：`holothurian`、`strongylocentrotus`、`chlamys`、`asterias`。

| 列 | 类型 | 说明 |
|---|---|---|
| `class_code` | VARCHAR(32) | 必须与模型 `labels.txt` **完全一致且顺序相同** |
| `cn_name` | VARCHAR(32) | 展示名 |
| `category` | SMALLINT | 1 经济种，2 敌害种，3 环境物 |
| `conf_thr` | NUMERIC(4,2) | 分类别阈值，默认 0.50 |
| `in_stat` | SMALLINT | 是否计入统计 |

**`class_code` 的顺序是契约。** 若 `labels.txt` 与 `species_dict` 顺序不一致，所有结果整体错位；
程序启动时必须校验两处一致，不一致直接拒绝启动。

## 四、索引

| 表 | 索引 | 原因 |
|---|---|---|
| `media_asset` | `(session_id, captured_at)` | 按会话列帧 |
| `media_asset` | `(captured_at)` | 按日期范围查询 |
| `detect_object` | `(frame_id)` | 取单帧的框 |
| `detect_object` | `(task_id, class_code)` | 按任务统计类别 |
| `sys_log` | `(created_at)` | 按日期查审计 |

## 五、文件存储

```
data/
  frames/年/月/日/<session_id>/<frame_id>.jpg
  thumbs/年/月/日/<frame_id>.jpg
  results/<frame_id>.json
  models/<version_name>/{best.pt,labels.txt,metrics.json}
  exports/
```

数据库只存相对路径。换数据根目录是改配置，不是做迁移。

## 六、生命周期

- 原始帧长期保留；缩略图与中间文件 90 天后过期。
- 删帧先软删，7 天后物理删除。
- 模型版本一旦上线就不再删除，只标记为离线。
- 日志保留 180 天，之后导出归档。
