# 测试用例

> 本文为 `test-cases-en.md` 的中文对照版，以英文版为准。
> 维护人：@IkeaFyj · 重审时机：验收项变化时，或某条用例被执行后

针对 SRS 表 8-1 中 36 条验收项的用例，并写明每一条今天能拿出什么证据。**每条用例都带结论**：
`automated` 表示 `tests/` 里有测试断言了它，`manual` 表示必须由人执行步骤，`uncovered` 表示既没有
测试、也没有实现。结论是 2026-11-12 逐条读测试得出的，不是照用例标题推的：存在测试但不断言该主张的，
不算覆盖；留给人的部分写在用例的 `Where` 一行里。

## 一、目的与范围

每个验收项至少一条用例；一条验收项里藏着两个独立主张的，拆成两条。**必须成立什么由 SRS 说了算**，
用例只负责说「人怎么证明它成立」。

这些用例是需要跑起来的系统、数据库、训练好的模型，或者需要人眼看屏幕的检查，不是把单元测试重抄一遍。
`Where` 一行会指向覆盖该用例的测试：证据在那里，评审要能打开它。

## 二、用例怎么写

| 字段 | 含义 |
|---|---|
| 用例 | 稳定编号，`TC-<领域>-<序号>` |
| 验收项 | 它服务的验收项，出自 SRS 表 8-1 |
| 前置条件 | 第一步之前必须成立的事；不成立的话，结果不算失败 |
| 步骤 | 能触发该主张的最短路径 |
| 预期 | 成立时观察到什么——写到陌生人也能判断的程度 |
| 状态 | 有测试断言该主张时为 `automated`；必须由人执行时为 `manual`；测试与实现都没有时为 `uncovered` |
| 出处 | 证据所在：`文件::函数` 形式的测试，或人工步骤，或缺的是什么 |

`automated` 这个结论只值它点名的那条测试。测试必须存在、必须走真实代码路径、必须在行为回退时失败。
点名的测试没有断言的部分，写在同一行的 `Not asserted:` 之后；完全没有实现的部分，写在
`Not implemented:` 之后。两者都留着，而不是被抬进一个没人核过的自动化结论里。

## 三、用例

### 3.1 账号与权限

**TC-AUTH-01** —— 验收项 AC-01 · 登录锁定 · automated
- 前置条件：一个已启用账号，密码已知。
- 步骤：连续五次提交错误密码；然后提交正确密码。
- 预期：第五次失败返回锁定提示并给出剩余秒数；锁定期间用正确密码登录被拒，且提示同样的剩余时间。
- 出处：`tests/test_api_skeleton.py::test_wrong_password_counts_down_then_locks`——倒计数、锁定码，
  以及锁定期间正确密码被拒。未断言：之后再次尝试时那句剩余秒数；锁定本身报的是分钟数。

**TC-AUTH-02** —— 验收项 AC-01 · 密码存储 · manual
- 前置条件：TC-AUTH-01 用过的账号至少登录过一次。
- 步骤：在数据库里读 `password_hash` 与 `salt` 两列。
- 预期：两列都不含明文密码；两个同密码账号的哈希不相同。
- 出处：人工——在种子数据库上执行第 2 步。没有任何测试读这两列；各测试夹具多次哈希同一个密码，
  却从不比较两个结果。

**TC-PERM-01** —— 验收项 AC-02 · 角色边界 · automated
- 前置条件：以采集员身份登录；存在一个已登记的模型版本。
- 步骤：用采集员的令牌调用 `POST /api/models/{id}/activate`。
- 预期：标准封装返回 403；操作日志里出现一条拒绝记录。
- 出处：`tests/test_forbidden_is_logged.py::test_a_route_level_guard_logs_the_attempt_too`——403，以及
  一条写明用户与路由的 `forbidden` 记录。更大范围的矩阵见
  `tests/test_permission_matrix.py::test_the_matrix_is_honoured_in_both_directions`。

**TC-PERM-02** —— 验收项 AC-02 · 未登录访问 · automated
- 前置条件：不带令牌。
- 步骤：调用 `POST /api/capture/sessions/{id}/frames`。
- 预期：标准封装返回 401；不产生任何帧记录。
- 出处：`tests/test_capture_local_only.py::test_a_remote_call_without_a_token_is_still_a_401`——401 及
  其封装码，且在本机校验之前先回答。未断言：「不产生任何帧记录」——只核了这次拒绝，没有回头读帧列表。

**TC-ACC-01** —— 验收项 AC-03 · 停用账号 · manual
- 前置条件：一个已有识别历史的账号；一个管理员会话。
- 步骤：停用该账号；用它登录；以管理员身份查询它的历史结果。
- 预期：登录被拒；历史结果仍可查出。
- 出处：人工——照本用例三步走。`POST /api/users/{id}/status` 存在并且会翻 `status`，但没有测试用
  `status: 0` 调它、之后再登录，或查询历史。

**TC-ACC-02** —— 验收项 AC-03 · 重复手机号 · uncovered
- 前置条件：某手机号已被一个账号占用。
- 步骤：用同一号码再建一个账号。
- 预期：被拒，提示冲突字段；不新增任何记录。
- 出处：无覆盖——契约里没有「新建账号」这个操作，所以没有地方提交第二个账号，也没有唯一性规则可验。

**TC-AUD-01** —— 验收项 AC-04 · 审计内容 · automated
- 前置条件：一帧处于待复核状态。
- 步骤：删掉一个框并提交复核；在操作日志里查这一帧。
- 预期：有一条记录，带操作人、时间、以及这次变更的前后值。
- 出处：`tests/test_review_versions.py::test_two_submissions_appear_newest_first_with_their_counts_and_authors`
  ——操作人、时间戳，以及从已存日志里读回的前后框数。未断言：这些行经 `/api/logs` 呈现的样子；
  该测试走的是版本接口。

**TC-AUD-02** —— 验收项 AC-04 · 无删除入口 · manual
- 前置条件：日志里至少有一条记录。
- 步骤：遍历契约里所有可能删数据的接口。
- 预期：没有任何路由能删日志；除保留期策略外，日志行数不减少。
- 出处：人工——逐条走 `docs/api-contract-en.md` 里的 45 个操作。没有测试断言「不存在会删日志的路由」；
  而且 `/api/demo/reset` 确实会清 `sys_log`，那是演练用的，不是保留期策略。

### 3.2 采集

**TC-CAP-01** —— 验收项 AC-05 · 无摄像头即无来源 · automated
- 前置条件：采集设备断开。
- 步骤：启动系统；寻找任何能把图片送进识别队列的路径。
- 预期：不存在这样的路径；界面提示设备不可用，且不产生任何记录。
- 出处：`tests/test_ws_capture.py::test_a_server_without_a_camera_closes_with_1011`——实时套接字关闭且
  一帧都不发；`tests/test_api_skeleton.py::test_detect_frame_rejects_a_frame_that_never_came_through_capture`
  ——识别拒绝一张没走过采集的图。未断言：页面自身的不可用状态。

**TC-CAP-02** —— 验收项 AC-05 · 时间戳容差 · automated
- 前置条件：采集设备已连接。
- 步骤：提交一帧，其采集时间比服务器时间慢六秒。
- 预期：被拒，并记录原因；不写任何记录。
- 出处：`tests/test_api_skeleton.py::test_a_frame_with_a_skewed_clock_is_refused`——拒绝码与提示里的
  五秒规则。未断言：确实没写记录（拒绝发生在写入之前）。

**TC-CAP-03** —— 验收项 AC-05 · 帧幂等 · automated
- 前置条件：一个打开的采集会话。
- 步骤：用同一个标识把同一帧提交两次。
- 预期：只有一条记录；第二次调用返回成功但不产生重复。
- 出处：`tests/test_api_skeleton.py::test_capture_scores_the_frame_and_is_idempotent`——同一个
  `frame_id` 提交两次，随后列表里只有一条。

**TC-CAP-04** —— 验收项 AC-06 · 定时巡拍 · uncovered
- 前置条件：一个「10 分钟间隔、6 次」的采集计划。
- 步骤：把时钟推过整个计划；数批次。
- 预期：6 个批次，每批帧数与计划一致。
- 出处：无覆盖——没有计划这回事：`server/` 里既没有路由，也没有表，也没有定时器。

**TC-CAP-05** —— 验收项 AC-06 · 计划失败 · uncovered
- 前置条件：一个计划，其设备在第三次触发前变为不可用。
- 步骤：让计划跑到结束。
- 预期：第三次被标记失败并给出原因；之前采集的批次不受影响。
- 出处：无覆盖——同一个缺失的计划。没有任何地方记录一次失败的触发。

**TC-CAP-06** —— 验收项 AC-07 · 质量拦截 · manual
- 前置条件：设备可以按需失焦。
- 步骤：抓一帧失焦画面；再抓一帧清晰画面。
- 预期：失焦帧得分低于 60，入库、标记需重拍、不进入识别队列；清晰帧正常进入。
- 出处：人工——得分与判定已有覆盖：`tests/test_capture.py::test_flat_frame_is_a_retake` 与
  `tests/test_params_live.py::test_the_capture_verdict_uses_the_threshold_in_force`；但「不进队列」这
  一半今天是不成立的：`/api/detect/batches` 会选中所有尚未识别的帧，从不过滤 `quality_flag`，
  所以需重拍的帧照样进批次。

**TC-CAP-07** —— 验收项 AC-07 · 重拍标记 · uncovered
- 前置条件：一帧已被标记需重拍。
- 步骤：触发重拍；打开该批次。
- 预期：重拍帧在同一批次内独立成条，并带重拍标记。
- 出处：无覆盖——没有任何操作会触发重拍。每次采集都把 `is_retake` 写成 0，也没有路由改过它。

**TC-CAP-08** —— 验收项 AC-08 · 组合检索 · automated
- 前置条件：至少三个批次，跨两个点位、三个日期。
- 步骤：同时按点位、日期范围与质量筛选；再打开其中一个批次。
- 预期：只返回匹配的批次；打开后能列出帧；选中的帧能带进任务创建页。
- 出处：`tests/test_frames_filters.py::test_the_four_filters_combine_as_an_intersection` 与
  `::test_the_total_counts_the_filtered_set_not_the_page`。未实现：把选中的帧带进任务创建——批次是按
  数量创建的，不是按选中的帧。

**TC-CAP-09** —— 验收项 AC-09 · 清理 · uncovered
- 前置条件：存在超过保留期的中间文件。
- 步骤：分别在「含原图」与「不含原图」两种设置下执行清理。
- 预期：被删文件的引用置空且磁盘占用下降；默认策略下原图不被删除。
- 出处：无覆盖——没有清理这个操作。`retention_days` 只是存下来的参数，没有任何会删文件的代码读它。

### 3.3 识别

**TC-DET-01** —— 验收项 AC-10 · 即时识别 · manual
- 前置条件：一个已登记的帧；线上模型已加载。
- 步骤：触认识别，计时到画面出现检测框为止。
- 预期：3 秒内出框；耗时随结果一并记录。
- 出处：人工——「3 秒」这一半要在部署机上掐表。接口与记录的耗时有覆盖：
  `tests/test_detect_real.py::test_one_real_inference_matches_a_manual_run_of_the_same_weights`，
  但它需要 torch 与开发数据库。

**TC-DET-02** —— 验收项 AC-10 · 来源校验 · automated
- 前置条件：一张从未经过采集的本地图片。
- 步骤：用任何途径尝试把它送进识别。
- 预期：被拒，提示来源不符。
- 出处：`tests/test_api_skeleton.py::test_detect_frame_rejects_a_frame_that_never_came_through_capture`
  ——未知帧编号返回 404，且不凭空造框。

**TC-DET-03** —— 验收项 AC-11 · 批量进度 · automated
- 前置条件：一个 100 帧的批次。
- 步骤：发起识别；观察进度；在第 40 帧时取消；重试一个失败帧。
- 预期：进度逐帧推进；取消在 5 秒内生效且不再新增结果；重试只针对该帧产生新结果。
- 出处：`tests/test_worker.py::test_queue_runs_100_frames_to_done`、
  `::test_cancel_at_frame_40_stops_within_five_seconds` 与 `::test_failure_is_retryable`；任务运行期间
  从接口读进度见 `tests/test_batch_acceptance.py::test_progress_is_queryable_while_a_batch_task_runs`。

**TC-DET-04** —— 验收项 AC-12 · 阈值影响 · manual
- 前置条件：一帧里有若干置信度接近阈值的检测结果。
- 步骤：先用置信度 0.5 跑一次，再用 0.2 跑一次。
- 预期：第二次在同一帧上返回更多检测框。
- 出处：人工——照本用例在已加载模型上跑两次。没有测试在同一帧上比较两个阈值；
  `tests/test_worker.py::test_a_task_runs_with_its_own_inference_parameters` 只证明参数送到了模型。

**TC-DET-05** —— 验收项 AC-12 · 参数冻结 · manual
- 前置条件：一个已经跑完的任务。
- 步骤：用契约里的每一条途径尝试修改它的置信度阈值。
- 预期：没有任何途径可以改；记录里的参数仍与执行时一致。
- 出处：人工——逐条走契约。没有测试断言这条记录不可变。新增一个会改参数的接口会让
  `tests/test_permission_matrix.py::test_the_matrix_covers_every_mounted_route` 失败，但那守的是路由
  清单，不是这条主张。

**TC-DET-06** —— 验收项 AC-13 · 计数一致 · automated
- 前置条件：一个结果覆盖四个类别的任务。
- 步骤：读分类计数；再按单个类别筛选。
- 预期：总数等于列表条数；筛选后计数与图表同步变化。
- 出处：`tests/test_api_skeleton.py::test_boxes_come_back_by_frame_id`——计数等于返回的行数，且与识别
  写入的是同一组框。未断言：按单个类别筛选，以及图表。

**TC-DET-07** —— 验收项 AC-14 · 导出 · automated
- 前置条件：一个页面显示 N 条结果的任务。
- 步骤：导出 CSV；用 Excel 打开。
- 预期：表头之外有 N 行；中文类别名不乱码；坐标是归一化值。
- 出处：`tests/test_result_csv.py::test_comma_quote_newline_and_chinese_survive_a_round_trip`、
  `::test_the_bytes_are_utf8_so_chinese_opens_in_excel` 与 `::test_the_header_is_the_servers_field_names`。
  未断言：「坐标是归一化值」——这些列是从检测框原样抄过来的。

### 3.4 复核

**TC-REV-01** —— 验收项 AC-15 · 复核编辑 · automated
- 前置条件：一帧里同时存在一个误检和一个漏检。
- 步骤：删掉误检框；给漏检补画一个框；提交。
- 预期：计数先减一再加一；自动识别结果仍然可查看。
- 出处：`tests/test_api_skeleton.py::test_review_submission_returns_the_documented_result`——新增计数；
  `tests/test_review_versions.py::test_rollback_marks_removed_boxes_rejected_instead_of_deleting_them`
  ——被删掉的框仍是一行可查记录。未断言：同一次提交里既删又画、两个计数都核。

**TC-REV-02** —— 验收项 AC-16 · 版本与回滚 · automated
- 前置条件：TC-REV-01 用过的同一帧。
- 步骤：再提交一次复核；回滚到较早的那个版本。
- 预期：存在两个版本；回滚后结果与目标版本完全一致，且两个版本都仍在列表里。
- 出处：`tests/test_review_versions.py::test_two_submissions_appear_newest_first_with_their_counts_and_authors`
  与 `::test_rollback_restores_the_target_box_set_as_a_new_version`——还原后的集合逐框比对类别与坐标。

**TC-REV-03** —— 验收项 AC-17 · 难例池 · automated
- 前置条件：TC-REV-01 中被修正过的帧。
- 步骤：打开难例池；把其中一条移出。
- 预期：该帧在池中，来源标记为「已修正」；移出后不再出现。
- 出处：`tests/test_hard_samples.py::test_a_review_correction_enters_the_pool_with_its_origin`、
  `::test_the_pool_lists_each_frame_once_and_keeps_the_origins_filterable` 与
  `::test_removal_empties_the_pool_entry_and_keeps_the_evidence`。

**TC-REV-04** —— 验收项 AC-18 · 可复现导出 · automated
- 前置条件：一个包含未复核帧的样本范围。
- 步骤：用同一个种子导出两次；再导出包含该未复核帧的范围。
- 预期：两次导出的文件清单完全一致；第三次被拒，并点名那条未复核帧。
- 出处：`tests/test_api_skeleton.py::test_dataset_export_is_deterministic_and_keeps_groups_together` 与
  `::test_export_without_reviewed_frames_is_refused`；连拍分组规则见
  `tests/test_datasets.py::test_a_snapshot_keeps_a_burst_out_of_two_splits`。未断言：拒绝时点的是条件
  名，不是那条帧。

### 3.5 统计

**TC-STA-01** —— 验收项 AC-19 · 口径切换 · automated
- 前置条件：同时存在自动结果与复核后结果。
- 步骤：打开物种组成图；切换统计口径。
- 预期：数值随之变化，且图上标注的口径同步改变；各类占比合计 100%。
- 出处：`tests/test_api_skeleton.py::test_stats_figures_follow_the_rows_detection_and_review_wrote`
  ——两个口径、数值随口径变化、占比合计为一。

**TC-STA-02** —— 验收项 AC-20 · 分布 · uncovered
- 前置条件：至少两个点位，其中一个没有数据。
- 步骤：打开热力图；与排行表对照；选中那个空点位。
- 预期：热力图与排行一致；空点位显示空状态，而不是一张空白图。
- 出处：无覆盖——页面与契约里都没有热力图，也没有点位分布图；点位只作为筛选列出现。

**TC-STA-03** —— 验收项 AC-21 · 趋势算术 · uncovered
- 前置条件：两个周期的数据，其中较早一期缺失。
- 步骤：打开趋势图；手工核对一个变化率。
- 预期：手算结果与显示一致；基期缺失时显示横线，且不给出趋势结论。
- 出处：无覆盖——趋势图是每日采集帧数，没有任何地方比较两个周期，也没有算过任何变化率，
  自然没有算术可核。

**TC-STA-04** —— 验收项 AC-22 · 报告一致性 · manual
- 前置条件：看板上的数值非零。
- 步骤：生成报告；对照数值；读页脚。
- 预期：报告数值与看板一致；页脚写明模型版本与统计口径。
- 出处：人工——第 2 步的对照。
  `tests/test_api_skeleton.py::test_report_is_generated_from_the_same_figures_as_the_dashboard` 断言的是
  页脚标签与文件标题，不是某个数值与看板相等。

### 3.6 模型

**TC-MOD-01** —— 验收项 AC-23 · 登记校验 · automated
- 前置条件：已登记一个版本。
- 步骤：登记一个没有指标的版本；再登记一个同名版本。
- 预期：两次都被拒，各自点名缺失或冲突的字段。
- 出处：缺指标见 `tests/test_model_activation.py::test_a_version_without_metrics_cannot_go_online`；
  重名见 `tests/test_register_model.py::test_registration_is_idempotent_and_can_stay_candidate`。
  未断言：因重名而被拒——AC-23 把重名写成「只有一行，后一次更新它」，测试核的正是这个。

**TC-MOD-02** —— 验收项 AC-24 · 上线与回滚 · automated
- 前置条件：两个已登记版本，其中一个在线。
- 步骤：上线另一个；建一个任务；回滚；再建一个任务。
- 预期：两个任务各自记录了创建时生效的版本；回滚恢复了较早那个。
- 出处：`tests/test_model_activation.py::test_a_task_records_the_version_that_was_online_when_it_was_created`
  ——每个任务记录的版本，以及把回滚当作上线较早版本处理。

**TC-MOD-03** —— 验收项 AC-25 · 实验对比 · manual
- 前置条件：同一数据集上的基线实验与改进实验。
- 步骤：打开对比表；用相同种子把改进配置再跑一次。
- 预期：两次实验在同一张表里，带相对基线的差值；两次同参数实验的指标差异小于 1%。
- 出处：人工——可复现这一半要真跑两次训练。表格与差值对一行有覆盖：
  `tests/test_api_skeleton.py::test_experiments_list_reports_metrics_and_baseline`；同帧对比接口目前仍返回 501。

**TC-MOD-04** —— 验收项 AC-26 · 字典校验 · manual
- 前置条件：一个含四个类别码的 `labels.txt`。
- 步骤：新增一个不在其中的物种；然后改一个阈值并新建任务。
- 预期：新增被拒并列出差异项；新任务按新阈值生效。
- 出处：人工——类别顺序校验见
  `tests/test_detect_real.py::test_the_loader_refuses_a_model_whose_class_order_disagrees`，缺少 torch
  或复制的数据库时会跳过。阈值这一半目前不可能成立：`species_dict.conf_thr` 只被存下和改写，
  没有任何识别路径读它。

### 3.7 系统

**TC-SYS-01** —— 验收项 AC-27 · 参数生效 · automated
- 前置条件：一个可改的参数，例如并发上限。
- 步骤：改小它；持续提交任务直到上限生效；查日志。
- 预期：同时运行的任务数不超过配置值；日志里有前后值。
- 出处：`tests/test_params_live.py::test_a_limit_changed_at_the_page_binds_the_claims_that_follow`
  ——上限为 1 时同时只跑一个任务，且审计行里两个值都在。

**TC-SYS-02** —— 验收项 AC-28 · 运行监控 · manual
- 前置条件：一个可以填满的任务队列。
- 步骤：提交大批任务；盯住监控面板；把磁盘占用填过阈值。
- 预期：队列长度在一次刷新内明显上升；磁盘一项变红并给出提示。
- 出处：人工——磁盘那一半得有人去填盘。队列数字有覆盖：
  `tests/test_failure_messages.py::test_a_dead_worker_is_reported_with_the_tasks_it_is_not_advancing`。

**TC-SYS-03** —— 验收项 AC-29 · 消息去重 · uncovered
- 前置条件：采集失败可以按需触发。
- 步骤：一小时内触发两次。
- 预期：只产生一条未读消息，未读数只加一；第二次不再新增。
- 出处：无覆盖——没有任何地方创建 `sys_message` 行。接口只负责列出和标记已读，既没有采集失败事件，
  也没有去重规则。

### 3.8 算法

**TC-ALG-01** —— 验收项 AC-30 · 总体精度 · manual
- 前置条件：固定测试集与上线权重。
- 步骤：评估并记录 mAP@0.5 与 mAP@0.5:0.95。
- 预期：分别不低于 0.75 与 0.45。
- 出处：人工——跑评估。没有测试断言任何指标阈值；交付的 `metrics.json` 只被检查「是不是数字」，
  不被检查「够不够好」。

**TC-ALG-02** —— 验收项 AC-31 · 分类别精度 · manual
- 前置条件：同 TC-ALG-01。
- 步骤：产出分类别的召回率与精确率表。
- 预期：四类的召回均不低于 0.75，精确率均不低于 0.70。
- 出处：人工——同一次评估，按类别读。

**TC-ALG-03** —— 验收项 AC-32 · 改进增益 · manual
- 前置条件：基线实验与改进实验，数据、轮次、种子相同。
- 步骤：比较 mAP@0.5 与 FPS。
- 预期：mAP@0.5 至少高 0.03，FPS 不低于基线的 90%。
- 出处：人工——两次实验加一次对照，还没有人把它自动化。

**TC-ALG-04** —— 验收项 AC-33 · 计数偏差 · manual
- 前置条件：一段已人工计数的视频。
- 步骤：把去重后的计数与人工计数对照。
- 预期：偏差不超过 15%。
- 出处：人工——人工计数与流水线计数对照。

### 3.9 性能

**TC-PERF-01** —— 验收项 AC-34 · 单帧时延 · manual
- 前置条件：部署机及其 GPU。
- 步骤：对 100 次单帧识别计时，取中位数与 P90。
- 预期：中位数不超过 1.5 秒。
- 出处：人工——部署机。没有测试跑 100 次识别，也没有取过中位数。

**TC-PERF-02** —— 验收项 AC-34 · 列表时延 · manual
- 前置条件：达到设计容量的数据库。
- 步骤：对列表类接口压测，取 P90。
- 预期：P90 不超过 2 秒。
- 出处：人工——需要在达到设计容量的库上压测，这里没有这样的环境。

### 3.10 交付与演示

**TC-DOC-01** —— 验收项 AC-35 · 追踪完整 · manual
- 前置条件：当前 SRS 与追踪矩阵。
- 步骤：逐行读表 A-1；检查每条需求都有用例与验收项。
- 预期：29 条需求全部覆盖，没有空行。
- 出处：人工——读 `docs/traceability-en.md`。`scripts/check-ac-coverage.py` 检查的是每个验收项有人认领、
  已关闭的验收项点名了存在的测试；它不读矩阵。

**TC-DOC-02** —— 验收项 AC-35 · 文档齐套 · manual
- 前置条件：结项提交所在的仓库版本。
- 步骤：按 SRS §7.3 的交付物清单逐项对照。
- 预期：每一项要么存在，要么有记录在案的理由说明为什么没有。
- 出处：人工——逐项走 SRS §7.3。自动化的只有双语文档成对那一项
  （`tests/test_bilingual_structure.py::test_the_repository_pairs_are_in_sync`）。

**TC-DEMO-01** —— 验收项 AC-36 · 现场链路 · manual
- 前置条件：装置已搭好，靶标备好，数据库是干净的。
- 步骤：不刷新、不重启，依次跑采集 → 识别 → 复核 → 统计 → 报告。
- 预期：链路走完，没有卡住的环节，控制台无报错。
- 出处：人工——在装置上现场跑。没有测试在同一个会话里走完这五段。

**TC-DEMO-02** —— 验收项 AC-36 · 迭代叙事 · manual
- 前置条件：同一套装置，一帧已复核的数据。
- 步骤：导出数据集；不真的训练，但展示实验表与上线操作。
- 预期：难例池、数据集快照、实验记录、上线这四步都能当场展示，并讲清它们的先后关系。
- 出处：人工——同一套装置，把它讲成一个故事。每一步都有接口，但没有测试断言它们按这个顺序发生。

## 四、怎么跑

`automated` 的用例不需要人：`pytest -q` 会跑点名的测试，CI 在每个 PR 上也会跑。跑绿不等于每条都
执行过——需要 torch、复制的数据库或 Node 的文件会带原因跳过，跳过那一行会说明是哪一条没跑。

`manual` 的用例在种子数据库上手工执行，**按给出的顺序**——前一条常常造出后一条需要的状态。算法类
用例需要固定测试集与部署机；性能类用例需要部署机和达到设计容量的数据库；演示类用例需要搭好的装置。

`uncovered` 的用例根本跑不了。它们留在这份文档里，就是「评审现在还查不了什么」的清单，
背后功能落地时，它们是最先要回头改的。

用例失败时，缺陷记在该用例编号下，这样下次执行能分清「已修的缺陷」和「新出现的问题」。

## 五、当前状态

49 条用例：20 条 `automated`、21 条 `manual`、8 条 `uncovered`。这 8 条无覆盖的，就是这份文档现在
摆出来而不是藏起来的缺口——定时巡拍及其失败运行、重拍标记、清理、重复手机号、点位分布、
周期对比、消息去重，都还没有可查的东西。

21 条 `manual` 里有 6 条点名了覆盖其部分主张的测试（质量拦截、即时识别、报告数值、实验表、
字典校验、运行监控）；其余的等着人、部署机、一次训练或那套装置。
