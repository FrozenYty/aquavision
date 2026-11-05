# 文档索引

> 本文为 `INDEX-en.md` 的中文对照版，以英文版为准。
> 同步于：2026-11-05

> 维护人：@FrozenYty · 重审时机：文档有增删改名时

一页回答三个问题：哪份文档回答什么、两份冲突时以谁为准、改一处要连带改哪些。**先看这页，再打开别的东西。**

## 一、从哪读起

两层，各一条规则：

| 层 | 放什么 | 规则 |
|---|---|---|
| 仓库根目录 | `README`、`README-zh`、`AGENTS`、`CONTRIBUTING`、`LICENSE` | 第一次接触这个仓库要看的东西 |
| `docs/` | 其余全部 | 干活时要查的东西 |

项目内容不放在根目录；新人第一眼要看的，不在 `docs/` 里孤零零躺着。进入 `docs/` 之后，最快的路径是这张表：

| 你想做的事 | 读这份 |
|---|---|
| 第一次进这个仓库 | `README.md`，然后 `CONTRIBUTING.md` |
| 知道要做什么、怎么算过 | `srs-v1.4.docx`——第 3 章需求、第 8 章验收 |
| 领一个任务 | `tasks.md` 是契约，`progress.md` 说明它为什么动 |
| 理解系统怎么分层 | `architecture-zh.md`，再看相关那篇 ADR |
| 调接口或写接口 | `api-contract-zh.md` |
| 加表加字段 | `data-model-zh.md` |
| 买硬件、接线 | `procurement-zh.md` |
| 知道原型展示什么 | `prototype-zh.md` |
| 某个词该叫什么 | `glossary-en-zh.md` |
| 为什么当初这么定 | `adr/` |

## 二、文档地图

| 文档 | 回答什么 | 什么时候会变 | 维护人 |
|---|---|---|---|
| `srs-v1.4.docx` | 系统做什么、怎么验收 | 需求条目或验收项变化 | @FrozenYty |
| `architecture-en/zh.md` | 分层、依赖方向、运行时模型 | 形状变化时，不是改代码时 | @FrozenYty |
| `api-contract-en/zh.md` | 路径、封装、错误码、WebSocket | 接口或字段变化 | @Gtechson |
| `data-model-en/zh.md` | 表、字段、索引、文件落盘 | 加表或加字段 | @Gtechson |
| `test-plan-en/zh.md` | 测试分层、数据集、指标、缺陷分级 | 指标或验收项变化 | @IkeaFyj |
| `prototype-en/zh.md` | 11-06 走查展示什么，逐屏说明 | 原型被正式切片取代 | @chemflowers |
| `procurement-en/zh.md` | 买什么、为什么买这些、怎么验收 | 换硬件 | @FrozenYty |
| `glossary-en-zh.md` | 每个概念的唯一叫法 | 出现新概念 | @FrozenYty |
| `adr/01-06` | 为什么这样定、什么时候该重审 | 不改写，只被新 ADR 取代 | 该篇作者 |
| `tasks.md` | 阶段、任务、门禁 | 任务交付或重新划范围 | 全员 |
| `progress.md` | 发生了什么、为什么动 | 持续追加，只追加 | 干活的人 |

## 三、两份文档冲突时

每份文档只在**自己的范围**内权威，没有哪一份在所有事上说了算：

- **验收标准**——以 SRS 为准；
- **接口形状**——以 `api-contract` 为准，即使 SRS 用叙述提过同一个调用；
- **表结构**——以 `data-model` 为准；
- **分层与依赖方向**——以 `architecture` 为准；
- **历史**——以 `PROGRESS` 为准，但它从不描述现状。

冲突如果来自「决定变了但文档没跟上」，改文档，不要改记忆。如果来自「这个决定还没人做过」，那就做决定、记进 `PROGRESS`，难改的补一篇 ADR。

## 四、改一处要连带改哪些

改动很少是局部的。下面这张表让 `grep` 不再是唯一的防线：

| 你改了什么 | 还要同步改 |
|---|---|
| 字段名或类型 | `data-model`、`api-contract`、mock 数据、SRS 字段表 |
| 一个接口 | `api-contract`、`api.js`、mock server、SRS 模块表 |
| 指标或验收项 | SRS 3.5 与 8、`test-plan`、`tasks.md` 的 P4 |
| 类别或类别顺序 | `glossary`、`species_dict` 种子、`prepare_dataset.CLASS_CODES`、前端配色变量 |
| 硬件 | `procurement`、SRS 表 2-3、`tasks.md` 的 P1-06 |
| 阶段边界 | `tasks.md`、`progress.md`；若增减了文档，还有本页 |
| 任何成对的文档 | 两种语言，同一次提交 |

## 五、还不存在的文档

有意留白，到该出现的阶段再写：

| 文档 | 出现阶段 |
|---|---|
| 建表说明 | P1-01 |
| 测试用例表 | P1-05 |
| 演示脚本与截图 | P4-06 |
| 指标报告 | P4-04 |

早写等于写两遍。

## 六、让这页保持诚实

上表中成对的文档写成 
ame-en/zh.md，两个文件都存在，并由 CI 保证同步。

**不在地图里的文档，对团队来说就不存在。** 新增、改名、删除文档，都要在同一次提交里改这页；PR 模板里有对应的勾选项。
