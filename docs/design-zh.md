# 概要设计总览

> 英文版本：[design-en.md](design-en.md)。本文件是英文版的对照，冲突时以英文版为准。

> 维护人：@FrozenYty · 重审时机：模块边界或表集合发生变化时

本页记录其他文档没有承载的概要设计：接口面如何划分为模块、每个设计问题由哪份文档回答，以及用一张
图表示的实体关系模型。它不重复需求（`srs-zh.md`）、分层（`architecture-zh.md`）、接口形状
（`api-contract-zh.md`）与字段（`data-model-zh.md`），只说明这些内容在哪里。

## 一、八个模块

16 个路由模块构成同一个接口面，但设计、测试计划与课程交付物都按八个业务模块表述。下表是这层映射的
唯一出处：REST 接口共 47 条，另有 `/ws/capture` 与 `/api/health`。

| 序号 | 模块 | 路由 | REST 接口数 | 职责 |
|---|---|---|---|---|
| 1 | 用户与认证 | `auth`、`users` | 6 | 登录、令牌、账号与角色；其余全部调用的入口 |
| 2 | 采集与实时预览 | `capture`、`live` | 8 + 套接字 | 相机枚举、采集会话、帧与画质结论；实时预览套接字 |
| 3 | 检测与批量任务 | `detect`、`tasks` | 6 | 单帧检测、批量任务创建、进度、取消与重试 |
| 4 | 复核与难例 | `review`、`hard_samples` | 5 | 带版本历史的检测修正、回滚、难例池 |
| 5 | 数据集与实验 | `datasets`、`experiments` | 4 | 可复现的数据集快照与训练实验记录 |
| 6 | 模型与报告 | `models`、`reports` | 5 | 模型版本与上线；报告生成与历史 |
| 7 | 统计与物种 | `stats`、`species` | 6 | 质量、物种、趋势与修正分布统计；类别字典 |
| 8 | 参数、日志与演示 | `system`、`demo` | 7 | 运行期参数、监控、消息、审计日志与演示重置 |

## 二、每个设计问题由哪份文档回答

每个问题只有一个权威文档。读者若从别处得到不同答案，说明那份文档有缺陷，而不是存在第二种意见。

| 问题 | 文档 |
|---|---|
| 系统必须做什么，如何验收？ | `srs-zh.md` |
| 代码如何分层，依赖允许朝哪个方向？ | `architecture-zh.md` |
| 接口、响应封装、错误码是什么形状？ | `api-contract-zh.md` |
| 哪个表、字段、索引与文件布局承载数据？ | `data-model-zh.md` |
| 某个决策为什么这样定，何时应重审？ | `adr/` |
| 装置在某个状态下做什么，如何连到 PC？ | `rig-state-machine-zh.md`、`rig-transport-zh.md` |

## 三、实体关系模型

十四张表、十六个外键，仅画键；字段细节见 `data-model-zh.md` §3。图用 Mermaid 书写，因为仓库规定图
以代码形式入档（CONTRIBUTING §6），表发生移动时改的就是这段代码。

```mermaid
erDiagram
  sys_user {
    bigint user_id PK
    varchar username UQ
    varchar phone UQ
    varchar email UQ
  }
  species_dict {
    bigint species_id PK
    varchar class_code UQ
  }
  model_version {
    bigint model_id PK
    varchar version_name UQ
  }
  sys_param {
    bigint param_id PK
    varchar param_key UQ
    bigint updated_by FK
  }
  media_asset {
    bigint asset_id PK
    varchar frame_id UQ
  }
  detect_task {
    bigint task_id PK
    varchar task_code UQ
    bigint model_version_id FK
    bigint created_by FK
  }
  detect_task_item {
    bigint item_id PK
    bigint task_id FK
    bigint asset_id FK
  }
  detect_object {
    bigint object_id PK
    bigint task_id FK
    bigint asset_id FK
    varchar class_code FK
    bigint reviewed_by FK
  }
  dataset {
    bigint dataset_id PK
    varchar snapshot_name UQ
    bigint created_by FK
  }
  dataset_item {
    bigint item_id PK
    bigint dataset_id FK
    bigint asset_id FK
  }
  train_experiment {
    bigint exp_id PK
    bigint model_version_id FK
  }
  report {
    bigint report_id PK
    varchar report_code UQ
    bigint model_version_id FK
    bigint created_by FK
  }
  sys_message {
    bigint msg_id PK
  }
  sys_log {
    bigint log_id PK
    bigint user_id FK
  }
  sys_param }o--|| sys_user : "updated_by"
  detect_task }o--|| model_version : "model_version_id"
  detect_task }o--|| sys_user : "created_by"
  detect_task_item }o--|| detect_task : "task_id"
  detect_task_item }o--|| media_asset : "asset_id"
  detect_object }o--|| detect_task : "task_id"
  detect_object }o--|| media_asset : "asset_id"
  detect_object }o--|| species_dict : "class_code"
  detect_object }o--|| sys_user : "reviewed_by"
  dataset }o--|| sys_user : "created_by"
  dataset_item }o--|| dataset : "dataset_id"
  dataset_item }o--|| media_asset : "asset_id"
  train_experiment }o--|| model_version : "model_version_id"
  report }o--|| model_version : "model_version_id"
  report }o--|| sys_user : "created_by"
  sys_log }o--|| sys_user : "user_id"
```

## 四、设计阶段交付的数据库脚本

设计交付物带一份 MySQL 8 脚本（十四条 `CREATE TABLE`、键与索引、四行物种种子数据）。它由
`server/app/models.py` 生成而不是手写，因为仓库里 schema 只有一个真相源：`scripts/init_db.py` 用
SQLAlchemy 元数据建表、以加列方式升级，仓库不跟踪任何 `.sql` 文件。

该脚本是课程交付物，留在仓库之外；仓库只保留模型定义。表发生变化时由模型重新生成脚本，绝不直接改脚本。
脚本的真实运行检查是 `PLAN.md` 中的 **P4-13**。

## 五、本设计与 `data-model-zh.md` 的已知不一致

设计阶段从代码重建字段清单，发现 `data-model-zh.md` 有六处没有描述已实现的 schema。记录于此以免读
者被误导；这六处交给该文档的维护人处理，设计工作不改他人文档：

1. 四十个非空列只写了 `DEFAULT x`、未写 `NOT NULL`；照文档直译的 DDL 会把这些列建成可空。
2. §4 索引表漏了 `dataset_item` 的唯一约束 `uq_dataset_item_asset` 与索引
   `ix_dataset_item_dataset_split`，而 §3.12 写了、代码也声明了。
3. 外键命名规则（"与被引用列同名"）被三处 `model_version_id → model_version.model_id` 否定；代码按
   实体命名外键。
4. "主键统一为 `BIGINT AUTO_INCREMENT`"在代码里是方言相关的：PostgreSQL 为 `BIGINT`，SQLite 为
   `INTEGER PRIMARY KEY`。
5. §6 的生命周期声明——软删除七天、保留期清理、日志保留 180 天——没有对应列，也没有代码。
6. `media_asset.thumb_path` 从未写入，`media_asset.is_retake` 只被写入 `0`。
