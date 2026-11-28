# 演示脚本——八分钟、十个问题

> 本文为 `demo-script-en.md` 的中文对照版，以英文版为准。
> 维护人：@IkeaFyj · 重审时机：彩排改动了某个步骤、某个页面、某个问题或某张幻灯片时

一次受评演示，八分钟，一次故障注入，十个答案。第 4 节的时间是累计时间：彩排对着它计时，某一步晚了，算这份脚本或系统的缺陷，不算现场的问题。三次彩排由 `PLAN.md` P4-07 负责；现场用品与房间布置看 `docs/demo-kit-card-zh.md`；命令看 `docs/runbook-zh.md`；演示之后能声明什么看 `docs/test-cases-zh.md`。本页不新增任何命令、不新增任何用品——它只说用这些东西时该说什么。

## 一、唯一一条规则

八分钟是上限，七分五十秒是目标：最后十秒是留出来的，不是花掉的。如果比某一步的刻度晚了十秒以上，砍掉那句话，不要砍掉画面：第 4 节里的每一页都是评委来看的页面。真正重要的是第三次彩排，也就是它与上一次之间不需要再做任何修复的那一次（`PLAN.md` P4-07）。

## 二、进房间之前

| 时刻 | 做什么 | 依据 |
|---|---|---|
| −10:00 | 拿笔按清单逐行打勾，不凭记忆 | `docs/demo-kit-card-zh.md` 第一至三节 |
| −8:00 | 离线数据库副本恢复完毕，能打开一帧 | 用品卡第三节；`docs/runbook-zh.md` 第五节 |
| −7:00 | 摄像头在 1 号位可用，镜头侧偏振片已装好 | `python scripts/test_exposure.py --index 1` |
| −6:00 | 在仓库根目录启动服务 | `docs/runbook-zh.md` 第三节 |
| −5:00 | 关无线、100 % 缩放、演示分辨率、控制台无报错 | `PLAN.md` P4-19 |
| −4:00 | 演示要用的每一页都打开过一次并已登录 | `PLAN.md` P4-14 |
| −3:00 | 台灯走 USB，留一个空插座，备用线贴在桌边 | `docs/demo-kit-card-zh.md` 第二节 |
| −1:00 | 手机收起来；脚本和用品卡放在桌上；计时开始 | 本页 |

## 三、分钟预算

| 段落 | 从 | 到 | 时长 |
|---|---|---|---|
| 进房间之前 | −10:00 | 0:00 | 10:00 |
| 开场 | 0:00 | 0:50 | 0:50 |
| 主链 | 0:50 | 6:20 | 5:30 |
| 故障注入 | 6:20 | 6:50 | 0:30 |
| 收尾 | 6:50 | 7:50 | 1:00 |
| 预留 | 7:50 | 8:00 | 0:10 |

场内各段合计 8:00，实际讲完在 7:50；预留的十秒是让上限被满足，而不是被逼近。主链的五页就是 `P4-14` 要练的那五页（采集、结果详情、复核、统计、报告）；登录和总览是进出的门，不是另外两页。

## 四、逐页走一遍

| 时刻 | 页面 | 点击 | 出现什么 | 只说一句 |
|---|---|---|---|---|
| 0:00 | 登录页（`login.html`），已打开 | 站在缸边，不点 | 一个未登录的表单 | “AquaVision 把一张缸内照片，变成一份数过、改过、可下载的巡检记录，用不到一分钟。” |
| 0:50 | 登录页（`login.html`） | 输入演示账号，提交 | 总览页载入，四张指标卡 | “一次登录，系统已经知道今天：帧数、待复核、拦截率、在线模型。” |
| 1:10 | 总览（`home.html`） | 指 `#kpis`，再指 `#trend` | 四张卡和一条七日折线 | “这些就是报告要用的数字，不是另一套。” |
| 1:35 | 采集控制（`capture.html`） | 选点位 A3，点 `#btn-open` | 实时画面带框、质量分 86、分类计数、时延 | “每一帧先打分再计数：86 高于 60，所以这一帧进了队列。” |
| 2:50 | 结果详情（`result-detail.html`） | 点 `#strip` 里最新的一张缩略图 | 大图带框、目标列表、分类计数 | “识别写出这些框和这条记录，报告数的就是这条记录。” |
| 3:30 | 人工复核（`review.html`） | 点 `#btn-review`；选中误检框，点 `#tool-delete`；点 `#btn-add` 画出漏检框；用 `#class-select` 改类别；点 `#btn-submit` | 计数变化、新的版本行、一条提示 | “人纠正模型；纠正是新版本，不是覆盖，这一帧同时进入难例池。” |
| 4:40 | 统计分析（`stats.html`） | 从侧栏进入；把 `#basis` 在复核后与原始之间切换 | 四张图，标题和总数随口径一起变 | “口径印在数字旁边，所以「复核后」和「原始」永远不会被读成同一个总数。” |
| 5:25 | 巡检报告（`reports.html`） | 选本周、复核后口径，点 `#btn-generate`；就绪后点 `#history` 里的下载 | 先出现带数字的预览，随后一条就绪记录和一份下载文件 | “报告就是总览的数字，页脚写着模型版本和口径；它被存下来，也能下载为 Markdown。” |
| 6:20 | 采集控制（`capture.html`） | 拔掉摄像头 USB 线 | `#feed-mode` 显示实时连接已断开，计数停止变化 | “没有新帧了：摄像头被拔掉，页面如实说出来，而不是编一个数。” |
| 6:50 | 巡检报告（`reports.html`） | 回到报告，指页脚和历史记录行 | 同一组数字、模型版本、口径、已存记录 | “这就是整条环——采集、识别、纠正、统计、报告——而模型自己的环，从数据到实验到激活，就在它后面一页。” |

上面五页就是正式流程。模型迭代环不在其中，也不计时：如果评委问起，从侧栏打开 `models.html`，实验对比页签显示每次运行相对基线的差值，版本列表页签显示激活，`dataset-export.html` 是最初的数据快照。第 10 张幻灯片画的就是这三步。

## 五、故障注入

三次彩排里有一次注入这个故障，并且照这里写的演（`PLAN.md` P4-07）。选摄像头，是因为页面为它准备了明确的表情；拔掉在线模型版本则要等进程重新加载检测器才会显形，而死机重启不算三十秒恢复。当天不要临时换一种故障。

在第 0 秒、手里拿着线的时候，说这一句：

> 没有新帧了：摄像头被拔掉，页面如实说出来，而不是编一个数。

| 秒 | 动作 | 现场看到什么 |
|---|---|---|
| 0 | 拔掉摄像头并说出那句话 | `#feed-mode` 变为断开提示；最后一帧留在屏上 |
| 5–12 | 插回同一根线，继续说话 | 暂时没有变化 |
| 12–18 | 点 `#btn-close`，再点 `#btn-open` | 出现新的采集会话；连接恢复 |
| 18–25 | 等第一帧 | 框和质量分回来 |
| 25–30 | 说出恢复那句，停下动作 | 一个恢复的页面，而不是转圈 |

恢复那句是：“二十五秒回来——会话重启了，报告一行没丢。”如果第 20 秒还没有帧，改说：“摄像头没回来，我用这次彩排覆盖过的录制帧路径”，并使用 `conda run -n aquavision python scripts/demo.py`，它的输出会说明这一帧来自摄像头还是录制文件（`PLAN.md` 风险表；P4-12）。三十秒的界，是屏幕上出现一个数字，不是一台活着的摄像头。

## 六、十个问题

### 问题一——为什么用 BLE 而不是 Wi-Fi？

现场能拿到的网络是校园网，要么 WPA2-Enterprise，要么网页认证，ESP32 两种都进不去：前者要 802.1X 客户端、身份、证书和对时的时钟，后者要浏览器。BLE 不要网络、不要 SSID、不要密码，串口版本又保留为退路，所以射频坏了只损失一根线，不损失演示。依据：`docs/adr/16-rig-cable-free-over-ble.md` 的 Context 与 Decision 两节；`docs/adr/17-drop-storm-and-err0-retired.md`；`docs/rig-transport-zh.md`；`tests/test_rig_ble.py`、`tests/test_rig_link.py`。

### 问题二——为什么用 Markdown 而不是 Word 或 PDF？

仓库里的文档和系统生成的巡检报告都是 Markdown；SRS 第 7.3 节里的 Word、PDF、Excel 是交给指导教师时的转换目标，没被要求就不转换，所以只保留一份，而不是两份互相过期（SRS 第 7.3 节与变更记录 V1.6）。下载接口返回的就是已存储的 Markdown，评委打开的那份，正是核对过数字的那份。依据：`docs/srs-zh.md` 第 7.3 节；`docs/api-contract-zh.md` 的 `GET /api/reports/{report_code}/file`；`tests/test_reports_route.py`。

### 问题三——为什么 SQLite 和 PostgreSQL 都要？

SRS 第 2.5 节给单台 Linux 部署服务器定的是 PostgreSQL 14；SQLite 是零安装的默认值，让一次克隆和 CI 不需要数据库服务也能跑，两者之间只由 `DB_DSN` 一个开关切换（`docs/architecture-zh.md` 第七、八节）。表只有一份 SQLAlchemy 声明，schema 不写两遍；方言的代价记在它真正咬人的地方——SQLite 没有行锁，所以任务的帧在 `detect_task_item` 里分配（ADR 12）。依据：`docs/architecture-zh.md` 第七、八节；`docs/runbook-zh.md` 第三、五节；`docs/adr/12-detect-task-items.md`；`docs/test-plan-zh.md` 第四节。

### 问题四——一帧的“哪一天”怎么定？

所有日历问题——帧号里的日期、`frames/<site>/<YYYYMMDD>/` 目录、日期筛选、统计分桶、报告周期、留存年龄——都由同一个配置时区回答：`AV_TIMEZONE`，默认 `Asia/Shanghai`；数据库存 UTC（ADR 14）。北京时间凌晨 3 点的一帧，在 UTC 里属于前一天，在本地属于它自己那天；算术只由 `server/app/timebase.py` 一个模块负责。它替掉的边界 bug 和两条互相矛盾的查询都写在 ADR 里。依据：`docs/adr/14-the-time-basis.md`；`docs/runbook-zh.md` 第十节；`tests/test_time_basis.py`、`tests/test_stats_windows.py`、`tests/test_report_dashboard_agree.py`。

### 问题五——模型加载不了会怎样？

服务照样启动，不需要推理的页面照样能用。检测器在启动时只加载一次；没有它时，单帧接口用加载器自己的那句话返回 `501`，不编造任何框；批量任务记为失败，错误信息是同一句话，目标数为零。演示驱动会打印 `no model loaded`，并说明检测未测量，而不是猜一个数。依据：`server/app/routers/detect.py`；`tests/test_api_skeleton.py::test_detection_without_weights_says_why`；`tests/test_worker.py::test_a_missing_model_uses_the_loaders_reason`；`scripts/demo.py`。

### 问题六——为什么是四个类别？

海参、海胆、扇贝是海洋牧场的经济物种，海星是扇贝的主要敌害；四类在 DUO 里都有标注，所以标签可以直接复用（SRS 第 3.5 节）。海洋垃圾类在 V1.3 中被删掉：没有公开标签，自有数据也支撑不起一条独立的指标。依据：`docs/srs-zh.md` 第 2.6 与 3.5 节、变更记录 V1.3；`scripts/prepare_dataset.py`；`tests/test_detect_real.py::test_the_loader_refuses_a_model_whose_class_order_disagrees`。

### 问题七——质量分怎么算，为什么是 60？

清晰度（拉普拉斯方差）、亮度（均值）、色偏（通道均值差）按 0.5、0.3、0.2 加权成 0–100 分；低于及格线就只入库、不进队列，采集页把三项分量都画出来（SRS FR-M2-03 表 3-8）。60 是 SRS 定的策略数字，不是调出来的：它是 `server/app/config.py` 里的默认值，以 `quality_threshold` 暴露，范围 0–100，在采一帧时读取，所以运维改了，下一帧就生效（`docs/runbook-zh.md` 第十节）。依据：`server/app/vision/quality.py`；`docs/srs-zh.md` 表 3-8；`tests/test_capture.py::test_flat_frame_is_a_retake`；`tests/test_params_live.py::test_the_capture_verdict_uses_the_threshold_in_force`。

### 问题八——有什么没做？

直接说，并指到行：点位热力图与排名（AC-20）、定时采集及其失败记录（AC-06）、重拍标记（AC-07）、同帧基线与改进模型对比（P4-10，接口返回 `501`）；七项指标和大规模 GPU 数字还没记录（P4-04），交付的 MySQL 脚本还没实际执行（P4-13）。每一条都在 `docs/acceptance-checklist-zh.md` 第四节有一行；同帧对比那个诚实的 `501` 有测试钉住。依据：`docs/acceptance-checklist-zh.md` 第三、四节；`docs/traceability-zh.md` TM-089；`PLAN.md` P3-13、P4-10、P4-13；`docs/test-cases-zh.md` TC-STA-02；`tests/test_api_skeleton.py::test_compare_answers_not_built`。

### 问题九——48 条路由和 ADR 怎么核？

契约列出 48 个操作，有一个测试把这张表和实际挂载的操作双向比对：少一条会失败，多一条没报备也会失败；`/api/health` 还会报告挂载数，以及 `contract_routes: 48`（`server/app/main.py`）。决策记录现在是 17 篇——ADR 17 在 11-27 取代了 ADR 16 的两条规则，所以评委可能读到的是 16——`scripts/check-adr-index.py` 检查每篇都出现在两份架构文档的表里、表里每条都真有文件、索引里的 `adr/01-NN` 范围等于最新一篇。依据：`tests/test_api_skeleton.py::test_every_contract_route_is_mounted`；`tests/test_permission_matrix.py::test_the_matrix_covers_every_mounted_route`；`scripts/check-adr-index.py`；`docs/INDEX-zh.md` 文档地图里的 `adr/01-17`。

### 问题十——现场摄像头或装置坏了怎么办？

和第 5 节是同一个预案：页面说明实时连接已断开，线插回去，会话重启；摄像头若没有重新枚举，就用录制帧路径 `scripts/demo.py` 打印同一条切片。装置保留了 `rig-serial` 版本，只要一根线、不要射频，所以 BLE 出问题损失三十秒和一根备用线，不损失演示（ADR 16、ADR 17）。不成立的是“自动回退”：采集页在 socket 断开后不会自己改轮询，这是 `P3-12` 尚未关闭的限制，所以恢复靠主持人点两下，并且要彩排过。依据：`PLAN.md` 的 P4 风险表和 P3-12；`docs/runbook-zh.md` 第九节；`scripts/demo.py`；`docs/adr/16-rig-cable-free-over-ble.md`；`tests/test_rig_link.py`。

## 七、幻灯片提纲

| # | 幻灯片 | 一句话信息 | 展示的证据或截图 |
|---|---|---|---|
| 1 | 封面 | 一张缸内照片，变成可复核、可计数、可下载的报告 | `docs/images/traceability/p02-home.png` |
| 2 | 问题 | 人眼计数无法审计，只靠检测器又不可信 | SRS 第 1.2 与 2.3 节 |
| 3 | 四个类别 | 三种经济物种和它们的敌害，DUO 里已有标注 | `docs/srs-zh.md` 第 3.5 节 |
| 4 | 架构 | 浏览器、FastAPI、一个 worker、SQLite 或 PostgreSQL、USB 摄像头、可选 BLE 装置 | `docs/architecture-zh.md` 第 2 节图 |
| 5 | 采集 | 先打分再计数；低于 60 只入库、不进队列 | `docs/images/traceability/p03-capture.png`；演示 1:35 |
| 6 | 识别 | 模型画框；没有模型就是 501，绝不编框 | `p06-result-detail.png`；`test_detection_without_weights_says_why` |
| 7 | 复核 | 纠正是带前后值日志的新版本，不是覆盖 | `p07-review.png`；`tests/test_review_versions.py` |
| 8 | 统计 | 口径印在数字旁边，复核后与原始不会混 | `p10-stats.png`；`tests/test_stats_view.py` |
| 9 | 报告 | 文档带总览的数字、模型版本和口径 | `p11-reports.png`；`tests/test_report_dashboard_agree.py` |
| 10 | 模型迭代 | 数据快照、带差值的实验表、按任务记录的激活 | `p12-models.png`；`tests/test_model_activation.py` |
| 11 | 证明了什么 | 每条验收项都有状态，证据就在旁边 | `docs/acceptance-checklist-zh.md` 第三节 |
| 12 | 没做什么 | 热力图、同帧对比、定时采集、GPU 数字，点名、有主、已披露 | `docs/acceptance-checklist-zh.md` 第四节 |

截图用的是 `docs/images/traceability/` 下已入库的那些，`p06`、`p07` 等都在同一目录。幻灯片不是设计文档的第二份：每张都指向页面或测试，而页面就是演示里已经打开过的页面。

## 八、这份脚本不负责什么

- 用品清单、房间布置顺序、到场检查：`docs/demo-kit-card-zh.md`。
- 命令与恢复步骤：`docs/runbook-zh.md`。
- 证明了什么、一条用例怎么跑：`docs/test-cases-zh.md`。
- 三次彩排、八分钟上限、注入故障：`PLAN.md` P4-07。
- 五页的练法、浏览器配置、离线检查：`PLAN.md` P4-14 与 P4-19。

彩排发现某一步不对，当天就改这一页；演示之后才改的脚本，只是一个故事。
