# 测试报告

> 本文为 `test-report-en.md` 的中文对照版，以英文版为准。

> 维护人：@IkeaFyj · 重审时机：再次跑测试套件，或某条验收用例发生变化时

## 一、这份报告回答什么

四个问题，每一个都由下面的一条命令回答，而不是由回忆回答：测试计划要求什么、在同一个提交上实际执行了什么、通过了什么、还有什么被跳过以及为什么。本轮工作发现的缺陷列在第六节，每条都带级别，以及一旦复发就会失败的检查。

本报告遵循 `P4-11` 定的规则：读者能复现这个数字，而不必相信它。下面每个数字都是第七节里某条命令打印出来的计数，取自同一个提交，没有一个数字是估计值。

## 二、测试计划

`docs/test-plan-zh.md` 第一节固定了层级，第六节固定了缺陷级别；`docs/test-cases-zh.md` 为 SRS 表 8-1 的每条验收项各写一条用例，并给出判定。下表是计划本身，不是本次运行的总结：

| 层级 | 覆盖什么 | 所属文档 | 怎么跑 |
|---|---|---|---|
| 单元 | 质量评分、坐标换算、阈值逻辑、去重、统计 | `docs/test-plan-zh.md` 第一节 | `pytest`，`tests/` 下 74 个文件 |
| 接口 | 封装、错误码、权限、分页、真实路由 | `docs/test-plan-zh.md` 第一节与 `docs/api-contract-zh.md` | `pytest`，用 starlette 的测试客户端 |
| 文档 | 双语成对文档、计划的规则、进度日志、可移植路径、ADR 索引、验收覆盖、缺陷证据、前端体积预算 | `docs/test-plan-zh.md` 第五节与 `CONTRIBUTING.md` | 十个 `scripts/check-*.py`，全部接进 CI |
| Node 页面套件 | 纯页面函数：画布撤销、CSV、统计视图、报告预览、页面故障、键盘、选点、运行时长 | `docs/test-plan-zh.md` 第一节与 `docs/design-zh.md` | `node tests/*.mjs`，由 pytest 唤起 |
| 人工 | 需要硬件、工作台、部署机、训练运行或彩排装置的用例 | `docs/test-cases-zh.md` 第三节 | 由人对着已播种的数据库执行 |

## 三、实际执行了什么

### 3.1 测试套件的一次运行

| 项目 | 值 |
|---|---|
| 提交 | `3259dfb` —— `chore(checks): every closed defect names the check that guards it (P3-35)` |
| 代码树 | 该提交的一次 `git clone`，加上被 git 忽略的 `data/`（开发数据库与其中的录像帧）；未改动任何受跟踪文件 |
| 解释器 | `aquavision` conda 环境：CPython 3.11.18、pytest 9.2.0、torch 2.15.0+cpu |
| 命令 | 在克隆根目录执行 `python -m pytest -v -p no:cacheprovider -o addopts=""` |
| 收集 | 74 个文件共 563 个测试 |
| 结果 | 563 条通过、0 条失败、0 条跳过（116 条警告） |
| 耗时 | 432.21 秒（7 分 12 秒） |

与直接 `pytest -q` 的唯一差别是 `-v`：它每个测试打印一行，日志里因此能按名字逐条核对用例，计数不受影响。
本报告落到 `f3e02e9`（P4-06 的纯文档合并）之后；两者的 `tests/` 与 `server/` 完全相同，所以在合并后的代码树上跑同一条命令会得到同样的计数。

这个数字来自一次跑完的运行，就在上面的提交上、在代码树的一份副本里；本报告不会把多次运行拼成一个数字。跑的是完整套件，不是子集：需要 torch 与开发数据库的三条用例在这里执行了，因为本机两者都有；需要 conda 环境的两条也执行了，原因相同。CI 环境改变了什么，见 3.2 节。

### 3.2 CI 跑什么，跳过什么

`check` 作业安装的是 `requirements-server.txt`，因此它没有 torch、没有 `ultralytics`、也没有 `aquavision` 这个 conda 环境；它同样没有 `data/` 目录，因为这个根目录被 git 忽略。它的步骤是仓库固定的检查，不是为这份报告挑选的：

| 步骤 | 命令 | 需要什么 |
|---|---|---|
| 依赖 | `python -m pip install -r requirements-server.txt` | 不需要别的；后续每一步跑的都是这份固定版本 |
| 风格 | `ruff check .` 与 `ruff format --check .` | 同一个文件 |
| 文档检查 | 十个 `python scripts/check-*.py`——双语、语言、进度、路径、ADR 索引、计划、Mermaid、验收覆盖、缺陷证据、前端体积预算 | 除服务器依赖之外不需要别的 |
| 提交信息 | `python scripts/check-commit-messages.py --range origin/<base>..HEAD` | 完整检出（`fetch-depth: 0`）；只在拉取请求上跑 |
| 测试 | `pytest -q` | GitHub 托管的 Ubuntu 镜像，Python 3.11，Node 与 `g++` 已装 |
| 固件 | 在 `firmware/main` 执行 `pio run` | PlatformIO 与缓存的 ESP32 工具链，在第二个作业里 |

563 条用例中有六条在该环境下跑不了。跳过条件写在测试里，每条都点名自己缺什么：

| 用例 | 跳过条件在代码里的位置 | 什么能让它变成一次运行 |
|---|---|---|
| `tests/test_detect_real.py` —— 3 条 | `real_client` 夹具在 `data/app.db` 缺失或 `import ultralytics` 失败时跳过；该文件每条测试都用这个夹具 | 一个恰好只有一行在线 `model_version` 的开发数据库、它指向的权重文件，以及带 torch 的 ultralytics |
| `tests/test_demo_driver.py` —— 2 条 | 模块级夹具在机器上没有 `aquavision` conda 环境时跳过 | 那个环境，因为驱动是用它的解释器作为子进程运行的 |
| `tests/test_delivered_weights.py` —— 1 条 | `test_the_development_database_online_version_points_at_the_delivered_weight` 在 `data/app.db` 缺失时跳过；其余四条读 `git ls-files`，任何机器都能跑 | 一个登记了交付版本的开发数据库 |

所以一次 CI 运行是收集 563 条、跳过 6 条、执行 557 条；这六条是由上面的条件推出来的，实测的运行在 3.1 节。**这六条没有一条是因为需要服务器栈而跳过**——缺的是开发数据库、torch 与 ultralytics 训练栈、以及那个 conda 环境。因此一次全绿的 CI 不等于跑了完整套件，日志里的跳过行才是说明哪一部分没跑的唯一诚实方式。

## 四、通过了什么

`docs/test-cases-zh.md` 里那 22 条 `automated` 用例，是测试断言过的声明；上面的运行包含它们点名的每一条测试。49 条用例中其余的既不是通过，也不计为通过：

| 判定 | 用例数 | 验收项 | 含义 |
|---|---|---|---|
| automated | 22 | 36 项中的 19 项 | 有测试断言该声明；22 条点名的测试都在本次通过的运行里 |
| manual | 21 | 36 项中的 17 项 | 需要人、工作台、部署机、一次训练运行或装置来执行 |
| uncovered | 6 | 36 项中的 5 项 | 测试与功能都不存在 |

三列在 AC-07 上重叠：那一项有一条人工用例、一条未覆盖用例，没有自动用例，所以三行加起来不是 36；每一项都至少被其中一类触及。

| 检查 | 命令 | 结果 |
|---|---|---|
| Python 套件 | `python -m pytest -v -p no:cacheprovider -o addopts=""` | 563 条通过 |
| 文档检查 | 十个 `scripts/check-*.py` | 十个检查，全部退出码 0 |
| Node 页面套件 | `node tests/*.mjs` | 8 个套件，全部退出码 0 |
| 验收覆盖 | `python scripts/check-ac-coverage.py` | 36 项都有人负责；每条已闭环项都点名一条存在的测试 |
| 演示驱动与测量 | `tests/test_demo_driver.py` 与 `tests/test_measure_performance.py` | 通过；数据库由测试自己播种、用完即弃 |

覆盖数字是查出来的，不是声明的：`scripts/check-ac-coverage.py` 在验收项没有归属任务、在已打勾的声明没有点名测试、在点名的文件已经移动时都会失败。满规模性能运行——10 万个资产与 500 万个目标——不属于本次套件，它的数字在 `PROGRESS.md`（2026-11-28），它发现的缺陷记在 6.1 节。

## 五、跳过了什么，为什么

`docs/test-cases-zh.md` 判为 `manual` 或 `uncovered` 的每一条用例都列在这里，因为这正是本报告不能算作通过的那些。人工用例不算通过，未覆盖用例不算通过，自动化的那一半变绿也不会让它们变成通过。下面是 21 条人工用例：

| 用例 | 验收项 | 为什么必须由人执行 | 证据会落在哪 |
|---|---|---|---|
| TC-AUTH-02 | AC-01 | 读已播种数据库的 `password_hash` 与 `salt` 两列；没有测试比较两个哈希 | 答辩用的运行记录，附查询输出 |
| TC-ACC-01 | AC-03 | 停用账号、再登录、再查历史；没有测试用 `0` 调状态接口 | 同一份运行记录 |
| TC-AUD-02 | AC-04 | 走查 `docs/api-contract-zh.md` 的 45 个操作，确认没有一条删日志行 | 接口走查记录，与验收清单一起归档 |
| TC-CAP-06 | AC-07 | 需要相机拍出一帧失焦画面；分数与判定那一半已有测试 | 工作台的采集插图，随彩排记录归档 |
| TC-DET-01 | AC-10 | 在部署机上用秒表量三秒 | 部署机的运行日志，归 `P4-04` |
| TC-DET-04 | AC-12 | 对同一帧用两个阈值各跑一次加载好的模型 | 部署机的运行日志 |
| TC-DET-05 | AC-12 | 走查接口文档，找是否有路由能改已完成任务的参数 | 接口走查记录 |
| TC-STA-04 | AC-22 | 用眼睛比较生成报告与看板的数字；`tests/test_report_dashboard_agree.py` 现已断言相等，判定可重审 | 报告页插图，以及该用例的重审结论 |
| TC-MOD-03 | AC-25 | 可复现性那一半需要两次真实训练运行 | `P4-02`、`P4-08` 的实验行 |
| TC-MOD-04 | AC-26 | 新增一个 `labels.txt` 里没有编码的物种；类别顺序那一半是上面那条只用 torch 的用例 | 部署机上的字典运行，注明日期 |
| TC-SYS-02 | AC-28 | 把磁盘填过阈值；队列那一半已有测试 | 彩排时的监控面板插图 |
| TC-ALG-01 | AC-30 | 在冻结测试集上做评测运行 | `P4-04` 的指标报告 |
| TC-ALG-02 | AC-31 | 同一次评测按类读 | `P4-04` 的指标报告 |
| TC-ALG-03 | AC-32 | 基线模型与改进模型共享数据、轮次与随机种子 | `P4-02`、`P4-04` 的实验行 |
| TC-ALG-04 | AC-33 | 对一段视频人工计数，与流水线去重后的计数比较 | `P4-04` 的指标报告 |
| TC-PERF-01 | AC-34 | 在部署机上做 100 次单帧识别，本机没有它那块 GPU | 该机器上测量脚本打印的中位数与 P90 |
| TC-PERF-02 | AC-34 | 满设计容量的列表负载；11-28 的 CPU 运行只是下界证据，不是验收运行 | 部署机上的测量运行，归 `P4-04` |
| TC-DOC-01 | AC-35 | 逐行读表 A-1，确认每条需求都有一条用例 | `docs/traceability-zh.md` 第五节与验收清单 |
| TC-DOC-02 | AC-35 | 走查 SRS 第 7.3 节的交付物清单 | `P4-09` 的提交包 |
| TC-DEMO-01 | AC-36 | 在装好的装置上跑通整条链，中途不刷新 | `P4-07` 的三次彩排 |
| TC-DEMO-02 | AC-36 | 同一套装置，按迭代故事讲一遍 | `P4-07` 的三次彩排 |

六条 `uncovered` 用例不是被跳过的运行：根本没有东西可跑。列在这里，是为了让缺口是一个数字，而不是一段沉默：

| 用例 | 验收项 | 为什么什么都没有 | 什么能补上 |
|---|---|---|---|
| TC-CAP-04 | AC-06 | 没有定时采集：`server/` 里没有路由、没有表、也没有计时器 | 一张计划表与一个计时器，再加 `P3-13` 的六批次测试 |
| TC-CAP-05 | AC-06 | 同一个缺失的计划；没有任何东西记录一次失败的触发 | 同上，并为那次触发记一行失败 |
| TC-CAP-07 | AC-07 | `is_retake` 在每次采集都写 0，没有任何路由设置它 | 一个补拍操作，今天没有任何路由提供它 |
| TC-CAP-09 | AC-09 | 没有清理操作；`retention_days` 只被存下来，删文件的路径不读它 | 一个清理路由，以及一条断言引用被置空的测试 |
| TC-STA-02 | AC-20 | 页面与接口文档里都没有热力图，也没有站点分布 | 那张图，以及一条看板一致性测试，归 `P3-02` |
| TC-STA-03 | AC-21 | 趋势图是每日采集量；没有比较两个周期，也没有算过任何比率 | 一个周期对比，以及一条算术测试 |

## 六、发现的缺陷与级别

`docs/test-plan-zh.md` 第六节固定了级别：阻塞是系统不可用、数据丢失或指标不达标；严重是核心路径被卡住或权限被绕过；轻微是观感或非关键页面。在 `3259dfb` 上，计数是**阻塞 0 条、严重 0 条未闭环、严重 15 条已闭环**，每条闭环都点名了复发时会失败的检查。`scripts/check-defect-evidence.py` 读同一份日志得到的是**21 条缺陷条目、其中 16 条已闭环**，因为若干条目合并了不止一个发现；本节数的是条目里的缺陷本身。轻微问题闭环十条、仍开放一条观感问题，在第六节允许的五条开放预算之内。

### 6.1 严重

| 级别 | 缺陷 | 修复 | 旧代码上会失败的回归检查 |
|---|---|---|---|
| 严重 | 被判需补拍的帧进入了识别批次；`create_batch` 从不过滤 `quality_flag` | 选取时过滤 `MediaAsset.quality_flag` | `tests/test_batch_quality.py` |
| 严重 | 无法用操作者勾选的帧建立批次；`BatchBody` 没有 `frame_ids`，Pydantic 把它丢掉了 | 请求体接受 `frame_ids`，按同一套入队规则全有或全无，冲突时以 `40002` 点名该帧拒绝 | `tests/test_batch_selection.py` |
| 严重 | `AV_RIG_PORT` 为空时不建立 BLE 装置链路，于是无线缆配置根本没有链路 | 链路按传输方式选择，而不是按端口 | `tests/test_rig_ble.py::test_the_application_starts_the_ble_link_with_no_port` |
| 严重 | `request_id` 出现在每个响应里却从未写进日志，与接口文档第一节相反 | 一个日志过滤器把它加到每条记录上 | `tests/test_request_id_logging.py` |
| 严重 | 所有校验失败都答 `40001`，于是「字段在但不合法」被报成「缺字段」 | 只有缺字段才是 `40001`，其余 schema 错误答 `40002` | `tests/test_api_skeleton.py::test_validation_errors_use_the_envelope` |
| 严重 | 质量阈值有两个真相：写死的及格线，与可配置的参数 | `score_frame` 接收当次生效的及格线，实时路由逐帧读取 | `tests/test_capture.py::test_the_pass_mark_is_an_argument_with_a_documented_default` |
| 严重 | `frame_id` 有两种格式，一种计数器、一种内容哈希前缀，而三份文档只描述一种 | 路由复用 `vision.capture.make_frame_id` | `tests/test_capture.py::test_frame_id_shape` |
| 严重 | `protocol.cpp` 在超长行上重置缓冲并继续读，把行尾当成新命令解析 | 一个 `discarding` 标志把整行丢弃 | `manual: firmware/README.md` 的工作台步骤——固件没有主机测试夹具 |
| 严重 | ADR 16 描述了已退役的掉线风暴规则，并把 `Err0` 当作仍然存在的失败面 | 由 ADR 17 取代，因为已接受的 ADR 只被取代、不被改写 | `docs/adr/17-drop-storm-and-err0-retired.md` |
| 严重 | 四个统计路由用三种不同的窗口算「最近七天」，于是同一个页面印出两个帧总数 | 由 `recent_days` 与 `day_bounds` 构造的唯一 `_window` | `tests/test_stats_windows.py` |
| 严重 | 报告历史按第一页的实时 `total` 分页，扫描中途新建一份报告就会重复一条、丢掉另一条 | 跟随短页并按 `report_id` 去重 | `tests/report_preview.mjs` |
| 严重 | 扫描进行中请求的历史刷新被丢弃，于是刚生成的报告永远不出现 | 刷新改为排队 | `tests/report_preview.mjs` |
| 严重 | 下拉框提供的简要模板在 `_render` 里没有实现 | 简要模板只带周期、物种与页脚 | `tests/test_report_preview.py` |
| 严重 | 干净克隆根本建不出数据库：`data/` 被忽略，`init_db.py` 不创建父目录 | 文件型 SQLite 的父目录在 `engine_from_dsn` 里创建，PostgreSQL 与 `:memory:` 不创建 | `tests/test_init_db.py` |
| 严重 | 设计容量下 `GET /api/hard-samples` 每次请求耗时 357,241 毫秒，在五百万行 `detect_object` 上逐行取数且没有覆盖索引 | `detect_object` 声明 `(hard_flag, review_status, frame_id, hard_reason)`，`ensure_indexes` 升级既有数据库，重测 P90 为 143.8 毫秒 | `tests/test_init_db.py` |

### 6.2 轻微

| 级别 | 缺陷 | 修复 | 由什么守住 |
|---|---|---|---|
| 轻微，文档 | 第五次登录失败的用例承诺剩余秒数，而锁定消息只报十五分钟 | 用例改为陈述服务器实际回答的内容 | `docs/test-cases-zh.md`，TC-AUTH-01 |
| 轻微，文档 | 某条用例说没有接口删除 `sys_log` 行，而 `POST /api/demo/reset` 按设计会清空它们 | 用例点名这次重置是例外 | `docs/test-cases-zh.md`，TC-AUD-02 |
| 轻微 | 计数轴印出小数与 `0.6000000000000001` | 轴按整数格式化 | `tests/stats_view.mjs` |
| 轻微 | 单日趋势渲染出 `NaN` | 趋势处理单日情形 | `tests/stats_view.mjs` |
| 轻微 | 统计 mock 回显了错误的 `days` 与 `cn_name` | mock 跟随路由 | `tests/stats_view.mjs` |
| 轻微 | 报告历史的 mock 行与接口文档的 Report 示例带了 UTC 偏移，而那里应当是运行时区 | 改为运行时区的时刻 | `tests/report_preview.mjs` |
| 轻微 | 历史筛选器把重叠查询写成了「周期起止」 | 改为点名重叠 | `tests/report_preview.mjs` |
| 轻微 | 空档案却声称设置了筛选 | 空状态直接说档案为空 | `tests/report_preview.mjs` |
| 轻微 | 统计的空状态没有给出下一步 | 每个空状态点名下一步 | `tests/stats_view.mjs` |
| 轻微 | TM-087、TM-088 与 TM-096 描述的是已经不存在的页面 | 按当前页重写这些行 | `docs/traceability-zh.md` |

### 6.3 仍然开放

| 级别 | 开放项 | 影响 |
|---|---|---|
| 轻微，观感 | 只有物种卡片绕过了 `loadInto` 的慢服务器提示 | 服务器慢时那一张卡不显示提示；没有任何数字是错的 |

## 七、怎么复现这些数字

下面的命令就是全部配方：一次该提交的克隆、解释器、以及打印本报告每个数字的命令。`python` 指 `aquavision` 环境；工作目录是仓库根目录。

```
# 测试套件：一次运行，数字见 3.1 与第四节
python -m pytest -v -p no:cacheprovider -o addopts=""

# 页面套件，套件里也会唤起它们
node tests/operating_time.mjs
node tests/page_failures.mjs
node tests/report_preview.mjs
node tests/review_history.mjs
node tests/review_keyboard.mjs
node tests/review_place.mjs
node tests/species_thresholds.mjs
node tests/stats_view.mjs

# CI 每次推送都跑的十个文档检查
python scripts/check-ac-coverage.py
python scripts/check-adr-index.py
python scripts/check-bilingual.py
python scripts/check-defect-evidence.py
python scripts/check-frontend-budget.py
python scripts/check-language.py
python scripts/check-mermaid.py
python scripts/check-paths.py
python scripts/check-plan.py
python scripts/check-progress.py

# 套件用小输入跑过的两个脚本；完整运行才是报告的证据
python scripts/demo.py
python scripts/measure_performance.py
python scripts/measure_performance.py --frames 45000 --objects 135000
python scripts/measure_performance.py --detect-only
```

| 数字 | 由什么产生 | 取自 |
|---|---|---|
| 收集 563 条，563 条通过 | 在克隆里执行 `python -m pytest -v …` | `3259dfb` |
| CI 环境下跳过 6 条 | 装好 `requirements-server.txt`、且没有 `data/` 之后跑同一套件 | `3259dfb` |
| 8 个页面套件、十个文档检查 | `node tests/*.mjs`、`scripts/check-*.py` | `3259dfb` |
| `/api/hard-samples` 先 357,241 毫秒、后 143.8 毫秒 | `python scripts/measure_performance.py` | 2026-11-28，记录在 `PROGRESS.md` |

解释器与命令同样重要：`datetime.UTC` 需要 Python 3.11 或更新，而 CI 验证的正是 `requirements-server.txt` 里的那组固定版本。换一个环境跑出的计数可能不同，那个差异本身就是一个发现，而不是脚注。

## 八、这份报告不声称什么

- **没有任何人工用例通过。** 21 条一条都还没跑；第五节那张表就是人还要做的事，改变它的是 `P4-07` 的彩排与部署机上的运行。
- **这里不验收任何指标。** AL-01 至 AL-07 属于 `P4-02`、`P4-04` 与冻结测试集；第四节里没有一个是指标值。
- **CI 全绿是跳过 6 条，不是 0 条。** 三条真实推理用例、两条驱动用例与一条开发数据库用例在那里不跑，而且没有一条跳过是因为服务器依赖。
- **性能数字是 CPU 下的下界。** AC-34 的验收运行在部署机的 GPU 上；本机是 `torch.cuda.is_available(): False`。
- **六条未覆盖用例是缺口。** 它们是评审暂时无法检查的清单，功能一落地就该回头先看它们。
- **截图没有重新生成。** 那由 `P3-36` 负责，本报告没有任何数字依赖截图。
