# 数据模型

> 本文为 `data-model-en.md` 的中文对照版，以英文版为准。
> 同步于：2026-11-06

> 维护人：@Gtechson · 重审时机：加表或加字段时

## 一、实体

十三张表。三张承载业务主干，其余是支撑；其中四张是骨架落地后补的——原来那九张装不下需求要的东西，
原因见 ADR 08，修订后的决策见 `srs-zh.md` §4.1。

| 表 | 作用 | 字段数 |
|---|---|---|
| `sys_user` | 账号、角色、登录状态 | 13 |
| `sys_log` | 关键操作的审计记录 | 10 |
| `media_asset` | 一帧影像及其元数据 | 18 |
| `detect_task` | 一次识别的模型、参数与进度 | 16 |
| `detect_object` | 一个检测框 | 19 |
| `species_dict` | 类别定义与分类别阈值 | 10 |
| `model_version` | 权重、指标与上线状态 | 14 |
| `train_experiment` | 数据集快照、超参与指标 | 18 |
| `sys_message` | 站内消息 | 10 |
| `sys_param` | 运行参数，键值形式，带审计 | 7 |
| `dataset` | 一次导出的数据集快照 | 9 |
| `dataset_item` | 快照中的一帧及其归属集合 | 5 |
| `report` | 一份生成的巡检报告及其文件 | 12 |

## 二、命名与类型

- 表名 `snake_case`，按业务域加前缀（`sys_`、`media_`、`detect_`）。
- 主键统一 `BIGINT AUTO_INCREMENT`，命名为 `<实体>_id`。
- 外键与被引用键同名，必须建索引。
- 时间统一 `TIMESTAMP`，存 UTC，命名为 `*_at`。
- 布尔用 `SMALLINT` 的 `0/1`，命名 `is_*` 或 `*_flag`。
- 枚举用 `SMALLINT` 加文档化的取值表，**不用**数据库 `ENUM` 类型。
- 金额 `NUMERIC(10,2)`；比率与坐标 `NUMERIC(5,4)` 或 `NUMERIC(8,5)`。
- 列名一律小写：SRS 里的 `mAP50`/`mAP5095` 落库为 `map50`/`map50_95`（PostgreSQL 会把未加引号的标识符折叠为小写）。

禁止在列里存逗号分隔的列表。一个值要重复出现，就该有自己的一张表。
唯一的例外见 `detect_task.class_filter`：它存 **JSON 数组**（如 `["holothurian","chlamys"]`），空值表示全部类别——是配置不是实体，不值得为它单开一张表。

## 三、表结构

每字段一行，类型与约束可直接用于建表。凡枚举值用整数编码存储，界面显示中文。

### 3.1 sys_user 用户表

| 列 | 类型 | 约束／默认 | 说明 |
|---|---|---|---|
| `user_id` | BIGINT | PK, 自增 | 用户主键 |
| `username` | VARCHAR(64) | UNIQUE, NOT NULL | 登录名 |
| `phone` | VARCHAR(20) | UNIQUE, NULL | 手机号，展示时脱敏 |
| `email` | VARCHAR(128) | UNIQUE, NULL | 邮箱，与手机号至少填一项 |
| `password_hash` | VARCHAR(128) | NOT NULL | 加盐哈希后的密码 |
| `salt` | VARCHAR(32) | NOT NULL | 密码盐值 |
| `role_code` | VARCHAR(16) | NOT NULL | observer／analyst／algo／admin |
| `real_name` | VARCHAR(64) | NOT NULL | 真实姓名 |
| `status` | SMALLINT | DEFAULT 1 | 1 启用／0 停用 |
| `fail_count` | SMALLINT | DEFAULT 0 | 连续登录失败次数 |
| `locked_until` | TIMESTAMP | NULL | 锁定截止时间 |
| `last_login_at` | TIMESTAMP | NULL | 最近登录时间 |
| `created_at` | TIMESTAMP | DEFAULT now() | 创建时间 |

### 3.2 sys_log 操作日志表

只追加，不修改，不删除（归档走导出）。

| 列 | 类型 | 约束／默认 | 说明 |
|---|---|---|---|
| `log_id` | BIGINT | PK, 自增 | 日志主键 |
| `user_id` | BIGINT | FK→sys_user, NULL | 操作人，系统自动操作可空 |
| `module` | VARCHAR(32) | NOT NULL | 模块标识 |
| `action` | VARCHAR(32) | NOT NULL | 动作类型：登录／复核／上线／改参 |
| `target_type` | VARCHAR(32) | NULL | 对象类型 |
| `target_id` | VARCHAR(64) | NULL | 对象编号 |
| `before_value` | TEXT | NULL | 变更前值（JSON） |
| `after_value` | TEXT | NULL | 变更后值（JSON） |
| `ip` | VARCHAR(64) | NULL | 来源 IP |
| `created_at` | TIMESTAMP | DEFAULT now() | 发生时间 |

### 3.3 media_asset 影像资源表

| 列 | 类型 | 约束／默认 | 说明 |
|---|---|---|---|
| `asset_id` | BIGINT | PK, 自增 | 资源主键 |
| `frame_id` | VARCHAR(32) | UNIQUE, NOT NULL | 帧号，格式 `YYYYMMDDTHHMMSS-mmmm` |
| `session_id` | VARCHAR(32) | NOT NULL | 一次连续采集为同一值 |
| `point_code` | VARCHAR(32) | NOT NULL | 监测点位 |
| `file_path` | VARCHAR(512) | NOT NULL | 相对 `data/` 的原始帧路径 |
| `thumb_path` | VARCHAR(512) | NULL | 缩略图路径 |
| `file_size` | BIGINT | NOT NULL | 字节数 |
| `file_hash` | CHAR(64) | NOT NULL | SHA-256，用于去重 |
| `captured_at` | TIMESTAMP | NOT NULL | 采集时间，UTC，毫秒精度 |
| `width` | INT | NOT NULL | 像素宽 |
| `height` | INT | NOT NULL | 像素高 |
| `exposure_us` | INT | NULL | 曝光时间（微秒），用于复现 |
| `gain_db` | NUMERIC(5,2) | NULL | 增益（dB），用于复现 |
| `quality_score` | SMALLINT | DEFAULT 0 | 质量总分 0–100 |
| `quality_flag` | SMALLINT | DEFAULT 0 | 0 合格／1 需重拍 |
| `is_retake` | SMALLINT | DEFAULT 0 | 是否为重拍帧 |
| `turbidity_rel` | SMALLINT | NULL | 浊度相对值 0–100，0 为清澈；无传感器时为空 |
| `created_at` | TIMESTAMP | DEFAULT now() | 入库时间 |

### 3.4 detect_task 识别任务表

| 列 | 类型 | 约束／默认 | 说明 |
|---|---|---|---|
| `task_id` | BIGINT | PK, 自增 | 任务主键 |
| `task_code` | VARCHAR(32) | UNIQUE, NOT NULL | 任务编号，规则 `DTyyMMdd-序号` |
| `task_type` | SMALLINT | NOT NULL | 1 即时／2 批量 |
| `model_version_id` | BIGINT | FK→model_version, NULL | 所用模型版本 |
| `asset_count` | INT | NOT NULL | 帧数 |
| `conf_thr` | NUMERIC(4,2) | DEFAULT 0.50 | 置信度阈值 |
| `iou_thr` | NUMERIC(4,2) | DEFAULT 0.45 | IoU 阈值 |
| `max_det` | INT | DEFAULT 100 | 单图最大检测数 |
| `class_filter` | VARCHAR(256) | NULL | 参与检测的类别码，**JSON 数组**；空为全部 |
| `status` | SMALLINT | DEFAULT 0 | 0 排队／1 运行／2 完成／3 失败／4 取消 |
| `progress` | SMALLINT | DEFAULT 0 | 进度百分比 |
| `obj_count` | INT | DEFAULT 0 | 目标总数 |
| `error_msg` | VARCHAR(512) | NULL | 失败原因 |
| `created_by` | BIGINT | FK→sys_user, NULL | 创建人 |
| `created_at` | TIMESTAMP | DEFAULT now() | 创建时间 |
| `finished_at` | TIMESTAMP | NULL | 完成时间 |

### 3.5 detect_object 检测目标表

| 列 | 类型 | 约束／默认 | 说明 |
|---|---|---|---|
| `object_id` | BIGINT | PK, 自增 | 目标主键 |
| `task_id` | BIGINT | FK→detect_task, NOT NULL | 所属任务 |
| `asset_id` | BIGINT | FK→media_asset, NOT NULL | 所在帧 |
| `frame_id` | VARCHAR(32) | NOT NULL | 帧号冗余，便于快查 |
| `class_code` | VARCHAR(32) | FK→species_dict, NOT NULL | 类别码 |
| `confidence` | NUMERIC(5,4) | NOT NULL | 置信度 0–1 |
| `x` | NUMERIC(8,5) | NOT NULL | 归一化框左上角横坐标 |
| `y` | NUMERIC(8,5) | NOT NULL | 归一化框左上角纵坐标 |
| `w` | NUMERIC(8,5) | NOT NULL | 归一化框宽 |
| `h` | NUMERIC(8,5) | NOT NULL | 归一化框高 |
| `track_id` | BIGINT | NULL | 同帧去重用的跟踪编号 |
| `is_manual` | SMALLINT | DEFAULT 0 | 0 自动／1 人工补画 |
| `review_status` | SMALLINT | DEFAULT 0 | 0 待复核／1 已确认／2 已修改／3 已驳回 |
| `version_no` | INT | DEFAULT 1 | 结果版本号，复核一次加一 |
| `hard_flag` | SMALLINT | DEFAULT 0 | 是否进难例池 |
| `hard_reason` | VARCHAR(32) | NULL | low_conf／modified／inconsistent |
| `reviewed_by` | BIGINT | FK→sys_user, NULL | 复核人 |
| `reviewed_at` | TIMESTAMP | NULL | 复核时间 |
| `created_at` | TIMESTAMP | DEFAULT now() | 生成时间 |

### 3.6 species_dict 物种字典表

上线时四行种子：`holothurian`、`strongylocentrotus`、`chlamys`、`asterias`。

| 列 | 类型 | 约束／默认 | 说明 |
|---|---|---|---|
| `species_id` | BIGINT | PK, 自增 | 主键 |
| `class_code` | VARCHAR(32) | UNIQUE, NOT NULL | 类别码，必须与模型 `labels.txt` **完全一致且顺序相同** |
| `cn_name` | VARCHAR(32) | NOT NULL | 展示名 |
| `latin_name` | VARCHAR(64) | NULL | 拉丁名 |
| `category` | SMALLINT | NOT NULL | 1 经济种／2 敌害种／3 环境物 |
| `conf_thr` | NUMERIC(4,2) | DEFAULT 0.50 | 分类别置信度阈值 |
| `in_stat` | SMALLINT | DEFAULT 1 | 是否计入统计 |
| `status` | SMALLINT | DEFAULT 1 | 1 启用／0 停用 |
| `remark` | VARCHAR(255) | NULL | 形态与危害说明 |
| `created_at` | TIMESTAMP | DEFAULT now() | 创建时间 |

**`class_code` 的顺序是契约。** 若 `labels.txt` 与 `species_dict` 顺序不一致，所有结果整体错位；
程序启动时必须校验两处一致，不一致直接拒绝启动。

### 3.7 model_version 模型版本表

| 列 | 类型 | 约束／默认 | 说明 |
|---|---|---|---|
| `model_id` | BIGINT | PK, 自增 | 主键 |
| `version_name` | VARCHAR(64) | UNIQUE, NOT NULL | 版本名，如 `v8n-E3-001` |
| `weight_path` | VARCHAR(512) | NOT NULL | pt 权重路径 |
| `onnx_path` | VARCHAR(512) | NULL | ONNX 路径 |
| `labels_path` | VARCHAR(512) | NOT NULL | 类别顺序文件路径 |
| `dataset_ref` | VARCHAR(128) | NULL | 数据集快照编号 |
| `map50` | NUMERIC(5,4) | NULL | mAP@0.5 |
| `map50_95` | NUMERIC(5,4) | NULL | mAP@0.5:0.95 |
| `recall_avg` | NUMERIC(5,4) | NULL | 平均召回率 |
| `fps` | NUMERIC(6,2) | NULL | 推理帧率 |
| `params_m` | NUMERIC(6,2) | NULL | 参数量（百万） |
| `status` | SMALLINT | DEFAULT 0 | 0 候选／1 线上／2 已下线 |
| `is_online` | SMALLINT | DEFAULT 0 | 是否当前线上 |
| `created_at` | TIMESTAMP | DEFAULT now() | 登记时间 |

### 3.8 train_experiment 训练实验表

| 列 | 类型 | 约束／默认 | 说明 |
|---|---|---|---|
| `exp_id` | BIGINT | PK, 自增 | 主键 |
| `exp_name` | VARCHAR(64) | NOT NULL | 实验名，如 `E3` |
| `model_version_id` | BIGINT | FK→model_version, NULL | 产出模型 |
| `dataset_snapshot` | VARCHAR(128) | NOT NULL | 数据集快照编号 |
| `split_ratio` | VARCHAR(16) | NOT NULL | 划分比例，如 `7:2:1` |
| `seed` | INT | NOT NULL | 随机种子 |
| `epochs` | INT | NOT NULL | 训练轮数 |
| `batch_size` | INT | NOT NULL | 批量大小 |
| `lr` | NUMERIC(8,6) | NOT NULL | 初始学习率 |
| `augment_json` | TEXT | NULL | 数据增强配置（JSON） |
| `map50` | NUMERIC(5,4) | NULL | mAP@0.5 |
| `map50_95` | NUMERIC(5,4) | NULL | mAP@0.5:0.95 |
| `recall_avg` | NUMERIC(5,4) | NULL | 平均召回率 |
| `fps` | NUMERIC(6,2) | NULL | 推理帧率 |
| `params_m` | NUMERIC(6,2) | NULL | 参数量（百万） |
| `is_baseline` | SMALLINT | DEFAULT 0 | 是否基线实验 |
| `note` | VARCHAR(255) | NULL | 改进点说明 |
| `created_at` | TIMESTAMP | DEFAULT now() | 记录时间 |

### 3.9 sys_message 站内消息表

| 列 | 类型 | 约束／默认 | 说明 |
|---|---|---|---|
| `msg_id` | BIGINT | PK, 自增 | 主键 |
| `msg_type` | VARCHAR(32) | NOT NULL | capture_failed／task_failed／report_done |
| `level` | SMALLINT | DEFAULT 1 | 1 提示／2 警告／3 严重 |
| `title` | VARCHAR(128) | NOT NULL | 标题 |
| `content` | VARCHAR(512) | NULL | 正文 |
| `target_role` | VARCHAR(16) | NULL | 目标角色，空为全体 |
| `ref_type` | VARCHAR(32) | NULL | 关联对象类型 |
| `ref_id` | VARCHAR(64) | NULL | 关联对象编号 |
| `is_read` | SMALLINT | DEFAULT 0 | 0 未读／1 已读 |
| `created_at` | TIMESTAMP | DEFAULT now() | 生成时间 |

### 3.10 sys_param

| 列 | 类型 | 约束 / 默认 | 说明 |
|---|---|---|---|
| `param_id` | BIGINT | 主键，自增 | 主键 |
| `param_key` | VARCHAR(64) | NOT NULL，唯一 | `retention_days`、`max_concurrency` 等 |
| `param_value` | VARCHAR(255) | NOT NULL | 以文本存储 |
| `value_type` | VARCHAR(16) | NOT NULL | int / float / bool / str，用于还原类型 |
| `remark` | VARCHAR(255) | NULL | 参数用途 |
| `updated_by` | BIGINT | 外键 sys_user，NULL | 最后修改人 |
| `updated_at` | TIMESTAMP | 默认 now() | 修改时间 |

键值形式而不是一个参数一列：**加参数不该需要一次迁移。**

### 3.11 dataset

| 列 | 类型 | 约束 / 默认 | 说明 |
|---|---|---|---|
| `dataset_id` | BIGINT | 主键，自增 | 主键 |
| `snapshot_name` | VARCHAR(64) | NOT NULL，唯一 | `DS-V3` |
| `manifest_path` | VARCHAR(512) | NOT NULL | 给人看的清单副本 |
| `split_ratio` | VARCHAR(16) | NOT NULL | `7:2:1` |
| `seed` | INT | NOT NULL | 划分种子，同种子同划分（AC-18） |
| `frame_count` | INT | NOT NULL | 快照帧数 |
| `status` | SMALLINT | 默认 1 | 0 生成中 / 1 就绪 / 2 归档 |
| `created_by` | BIGINT | 外键 sys_user，NULL | 导出人 |
| `created_at` | TIMESTAMP | 默认 now() | 导出时间 |

**快照先于任何实验存在**：今天导出，几天后才训练。

### 3.12 dataset_item

| 列 | 类型 | 约束 / 默认 | 说明 |
|---|---|---|---|
| `item_id` | BIGINT | 主键，自增 | 主键 |
| `dataset_id` | BIGINT | 外键 dataset，NOT NULL | 所属快照 |
| `asset_id` | BIGINT | 外键 media_asset，NOT NULL | 快照中的帧 |
| `split` | SMALLINT | NOT NULL | 1 训练 / 2 验证 / 3 测试 |
| `group_key` | VARCHAR(64) | NULL | 相似帧分组，同组不跨集合 |

(`dataset_id`, `asset_id`) 唯一；(`dataset_id`, `split`) 建索引。

### 3.13 report

| 列 | 类型 | 约束 / 默认 | 说明 |
|---|---|---|---|
| `report_id` | BIGINT | 主键，自增 | 主键 |
| `report_code` | VARCHAR(32) | NOT NULL，唯一 | `RPyyMMdd-序号` |
| `period_start` | TIMESTAMP | NOT NULL | 统计周期，含首日 |
| `period_end` | TIMESTAMP | NOT NULL | 统计周期，含末日 |
| `template` | VARCHAR(16) | NOT NULL | standard / brief |
| `basis` | VARCHAR(16) | NOT NULL | reviewed / raw |
| `model_version_id` | BIGINT | 外键 model_version，NULL | 生成时生效的版本 |
| `file_path` | VARCHAR(512) | NULL | 文档文件本身 |
| `status` | SMALLINT | 默认 0 | 0 生成中 / 1 就绪 / 2 失败 |
| `error_msg` | VARCHAR(255) | NULL | 失败原因 |
| `created_by` | BIGINT | 外键 sys_user，NULL | 发起人 |
| `created_at` | TIMESTAMP | 默认 now() | 创建时间 |

文档是文件；**这一行才是让历史可按周期、模板、口径查询的东西。**

## 四、索引

外键列一律建索引（第二节规则），下表只列复合索引与高频单列索引：

| 表 | 索引 | 原因 |
|---|---|---|
| `media_asset` | `(session_id, captured_at)` | 按会话列帧 |
| `media_asset` | `(captured_at)` | 按日期范围查询 |
| `media_asset` | `(file_hash)` | 入库去重查重 |
| `detect_object` | `(frame_id)` | 取单帧的框 |
| `detect_object` | `(task_id, class_code)` | 按任务统计类别 |
| `detect_object` | `(review_status)` | 待复核队列 |
| `sys_log` | `(created_at)` | 按日期查审计 |

## 五、文件存储

```
data/
  frames/<站点>/<年月日>/<session_id>/<frame_id>.jpg
  thumbs/年/月/日/<frame_id>.jpg
  results/<frame_id>.json
  models/<version_name>/{best.pt,labels.txt,metrics.json}
  exports/
```

数据库只存相对路径。换数据根目录是改配置，不是做迁移。

## 六、生命周期

- 原始帧长期保留；缩略图与中间文件超过 `retention_days`（默认 30 天，`AV_RETENTION_DAYS`）即成为清理对象。
- 删帧先软删，7 天后物理删除。
- 模型版本一旦上线就不再删除，只标记为离线。
- 日志保留 180 天，之后导出归档。
