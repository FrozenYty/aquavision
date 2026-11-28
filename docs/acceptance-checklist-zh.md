# 验收清单

> 本文为 `acceptance-checklist-en.md` 的中文对照版，以英文版为准。
> 维护人：@IkeaFyj · 重审时机：验收项变化，或它的证据换了位置

SRS 表 8-1 的每条验收项一行，按编号排序，旁边是今天已有的证据和一个评审能据以行动的状态。SRS 是「必须成立什么」的权威；`docs/test-cases-zh.md` 是「人怎么跑」；本页只补证据与结论，不再写一遍步骤。没有证据的行就是缺陷，不是理由——这是 `PLAN.md` P4-16 的规则，第四节把这样的三行写下来。

## 一、这页是干什么的

答辩之后要回答的不是「它跑没跑通」，而是「哪一条背后有什么」。本页对 36 条全部回答：SRS 怎么说、哪条用例服务它、证明它的文件或演示分钟是哪个、评审能不能把它当作已闭环。它不重跑任何东西，也不改用例——两边不一致时，第五节说明原因并点名是哪个任务移动了它。

## 二、一行怎么读

| 字段 | 含义 |
|---|---|
| AC | SRS 表 8-1 的验收编号（`docs/srs-zh.md` 第 8.1 节）；表按它排序 |
| SRS 判据 | 该项的原句，压到一行；权威仍然是 SRS |
| 用例 | `docs/test-cases-zh.md` 中服务该项的用例 |
| 证据 | 今天证明它的测试文件、文档章节或演示分钟 |
| 状态 | `closed` 表示证据已自动化；`manual` 表示还要人、部署机或装置去跑；`open` 表示有条款完全没有证据 |

用例自己写的 `Not asserted` 留在用例里，本页不重复；状态跟随用例的结论，除非后来的任务把缺的证据补上了（第五节）。`open` 的行是带主人的缺陷，不是承诺。

## 三、清单

| AC | SRS 判据 | 用例 | 证据 | 状态 |
|---|---|---|---|---|
| AC-01 | 连续五次失败锁定账号并显示剩余时间；口令列是哈希；锁定期内正确口令也被拒。 | TC-AUTH-01、TC-AUTH-02 | `tests/test_api_skeleton.py::test_wrong_password_counts_down_then_locks`；口令列与剩余秒数那句话要人工读（TC-AUTH-01、TC-AUTH-02） | manual |
| AC-02 | 采集员调用激活接口被拒且拒绝入日志；未认证用户进不了采集接口。 | TC-PERM-01、TC-PERM-02 | `tests/test_forbidden_is_logged.py::test_a_route_level_guard_logs_the_attempt_too`；`tests/test_capture_local_only.py::test_a_remote_call_without_a_token_is_still_a_401`；`tests/test_permission_matrix.py::test_the_matrix_is_honoured_in_both_directions` | closed |
| AC-03 | 停用账号不能登录且历史仍可查；重复手机号被拒。 | TC-ACC-01、TC-ACC-02 | `tests/test_accounts.py::test_a_duplicate_identifier_is_refused_with_the_message`；停用、登录、回查历史要人工做（TC-ACC-01） | manual |
| AC-04 | 复核可追溯到操作人、时间与前后值；没有接口能删日志。 | TC-AUD-01、TC-AUD-02 | `tests/test_review_versions.py::test_two_submissions_appear_newest_first_with_their_counts_and_authors`；逐条走契约找删除路由要人工做（TC-AUD-02） | manual |
| AC-05 | 采集停止就没有图像来源；时间偏差超过 5 秒被拒；重复帧只入一次库。 | TC-CAP-01、TC-CAP-02、TC-CAP-03 | `tests/test_ws_capture.py::test_a_server_without_a_camera_closes_with_1011`；`tests/test_api_skeleton.py::test_detect_frame_rejects_a_frame_that_never_came_through_capture`、`::test_a_frame_with_a_skewed_clock_is_refused`、`::test_capture_scores_the_frame_and_is_idempotent` | closed |
| AC-06 | 十分钟内六次采集产生六个批次；失败的一次把该轮记为失败。 | TC-CAP-04、TC-CAP-05 | 无：`server/` 里没有定时采集的路由、表或定时器（`PLAN.md` P3-13 未完成） | open |
| AC-07 | 失焦帧低于 60 分并留在队列外；重拍帧被标成自己的记录。 | TC-CAP-06、TC-CAP-07 | 队列那一半：`tests/test_batch_quality.py`、`tests/test_capture.py::test_flat_frame_is_a_retake`、`tests/test_params_live.py::test_the_capture_verdict_uses_the_threshold_in_force`；重拍标记没有写入方：`server/app/routers/capture.py` 每帧写 `is_retake=0` | open |
| AC-08 | 四个筛选条件正确组合；批次能下钻到帧；勾选的帧成为任务。 | TC-CAP-08 | `tests/test_frames_filters.py::test_the_four_filters_combine_as_an_intersection`、`::test_the_total_counts_the_filtered_set_not_the_page`；`tests/test_batch_selection.py`（用例里的 `Not implemented` 条款，P4-05 已关闭） | closed |
| AC-09 | 清理把引用置空、释放磁盘；默认策略下原图不动。 | TC-CAP-09 | `scripts/cleanup_retention.py`；`tests/test_cleanup_retention.py`（用例写成之后才交付） | closed |
| AC-10 | 触发到出现框不超过 3 秒；不是从采集进来的图被拒。 | TC-DET-01、TC-DET-02 | `tests/test_api_skeleton.py::test_detect_frame_rejects_a_frame_that_never_came_through_capture`；`tests/test_detect_real.py`（缺 torch 或开发库时跳过）；3 秒那一半是部署机上的秒表（TC-DET-01） | manual |
| AC-11 | 100 帧任务实时更新；取消 5 秒内生效；失败帧可重试。 | TC-DET-03 | `tests/test_worker.py::test_queue_runs_100_frames_to_done`、`::test_cancel_at_frame_40_stops_within_five_seconds`、`::test_failure_is_retryable`；`tests/test_batch_acceptance.py::test_progress_is_queryable_while_a_batch_task_runs` | closed |
| AC-12 | 改阈值改变结果数；任务参数事后不可编辑。 | TC-DET-04、TC-DET-05 | 无自动化：同一帧跑两个阈值、以及参数不可改的逐条走查都要人工（TC-DET-04、TC-DET-05） | manual |
| AC-13 | 分类计数等于列表行数；类别筛选让计数与图一起变。 | TC-DET-06 | `tests/test_api_skeleton.py::test_boxes_come_back_by_frame_id`；单类筛选与图表在用例里标为 `Not asserted`（TC-DET-06） | closed |
| AC-14 | CSV 行数等于页面行数；Excel 打开中文不乱码。 | TC-DET-07 | `tests/test_result_csv.py::test_comma_quote_newline_and_chinese_survive_a_round_trip`、`::test_the_bytes_are_utf8_so_chinese_opens_in_excel`、`::test_the_header_is_the_servers_field_names` | closed |
| AC-15 | 删框使计数下降、画框使其上升；自动结果仍可查看。 | TC-REV-01 | `tests/test_api_skeleton.py::test_review_submission_returns_the_documented_result`；`tests/test_review_versions.py::test_rollback_marks_removed_boxes_rejected_instead_of_deleting_them` | closed |
| AC-16 | 两次复核产生两个版本；回滚后结果与目标版本一致。 | TC-REV-02 | `tests/test_review_versions.py::test_two_submissions_appear_newest_first_with_their_counts_and_authors`、`::test_rollback_restores_the_target_box_set_as_a_new_version` | closed |
| AC-17 | 每个纠正过的样本带来源进入难例池；移除后不再出现。 | TC-REV-03 | `tests/test_hard_samples.py::test_a_review_correction_enters_the_pool_with_its_origin`、`::test_the_pool_lists_each_frame_once_and_keeps_the_origins_filterable`、`::test_removal_empties_the_pool_entry_and_keeps_the_evidence` | closed |
| AC-18 | 同一随机种子给出相同文件列表；未复核样本被拒。 | TC-REV-04 | `tests/test_api_skeleton.py::test_dataset_export_is_deterministic_and_keeps_groups_together`、`::test_export_without_reviewed_frames_is_refused`；`tests/test_datasets.py::test_a_snapshot_keeps_a_burst_out_of_two_splits` | closed |
| AC-19 | 切换口径时数字与标签一起变；占比合计 100 %。 | TC-STA-01 | `tests/test_api_skeleton.py::test_stats_figures_follow_the_rows_detection_and_review_wrote`；演示 4:40 | closed |
| AC-20 | 热力图与点位排名一致；没有数据的点位显示空状态而不是空图。 | TC-STA-02 | 无：页面与契约里都没有热力图，也没有点位分布图（`docs/test-cases-zh.md` TC-STA-02；`docs/traceability-zh.md` TM-089） | open |
| AC-21 | 比率能对上手工计算；缺基线时显示短横线。 | TC-STA-03 | `tests/test_stats_view.py`，它运行 `tests/stats_view.mjs`：日环比、短横线与单日情形（用例写成之后才交付）；演示 4:40 | closed |
| AC-22 | 报告数字等于总览；页脚带模型版本与统计口径。 | TC-STA-04 | `tests/test_report_dashboard_agree.py`；页脚标签：`tests/test_api_skeleton.py::test_report_is_generated_from_the_same_figures_as_the_dashboard`；演示 5:25 | closed |
| AC-23 | 缺指标的版本不能上线；一个版本名恰好一行。 | TC-MOD-01 | `tests/test_model_activation.py::test_a_version_without_metrics_cannot_go_online`；`tests/test_register_model.py::test_registration_is_idempotent_and_can_stay_candidate` | closed |
| AC-24 | 新任务记录生效版本；回滚恢复到先前版本。 | TC-MOD-02 | `tests/test_model_activation.py::test_a_task_records_the_version_that_was_online_when_it_was_created` | closed |
| AC-25 | 基线与改进实验在一张表里对比；两次相同运行差异小于 1 %。 | TC-MOD-03 | 实验表：`tests/test_api_skeleton.py::test_experiments_list_reports_metrics_and_baseline`；两次运行的可复现那一半要人工（TC-MOD-03） | manual |
| AC-26 | 与 labels 矛盾的类别码被拒；新的分类阈值对新任务生效。 | TC-MOD-04 | `tests/test_class_thresholds.py`（两句话与 labels 拒绝都在里面，P3-15 交付）；`tests/test_detect_real.py::test_the_loader_refuses_a_model_whose_class_order_disagrees` | closed |
| AC-27 | 新的并发上限约束后续任务，日志带前后值。 | TC-SYS-01 | `tests/test_params_live.py::test_a_limit_changed_at_the_page_binds_the_claims_that_follow` | closed |
| AC-28 | 大批量让队列数字明显变化；磁盘超过阈值变红并带说明。 | TC-SYS-02 | `tests/test_monitoring.py::test_a_large_batch_moves_the_queue_figure`、`::test_disk_past_its_threshold_turns_the_item_red_with_a_note`（P3-09 交付） | closed |
| AC-29 | 一次离线事件产生一条未读消息；一小时内重复不再增加。 | TC-SYS-03 | `tests/test_messages.py::test_repeated_failures_within_the_hour_add_nothing` | closed |
| AC-30 | 固定测试集上 mAP@0.5 不低于 0.75、mAP@0.5:0.95 不低于 0.45。 | TC-ALG-01 | 无自动化：固定集评估要人工（`PLAN.md` P4-01、P4-04 未完成） | manual |
| AC-31 | 四类的召回不低于 0.75、精确率不低于 0.70。 | TC-ALG-02 | 无自动化：分类表来自同一次人工评估（P4-04） | manual |
| AC-32 | 相对基线 mAP@0.5 至少 +0.03，FPS 至少保持 90 %。 | TC-ALG-03 | 无自动化：两次运行与对比要人工（P4-02、P4-03） | manual |
| AC-33 | 去重计数与人工读数偏差不超过 15 %。 | TC-ALG-04 | 无自动化：人工计数要人做（TC-ALG-04） | manual |
| AC-34 | 单帧端到端 GPU 上不超过 1.5 秒；列表接口 P90 不超过 2 秒。 | TC-PERF-01、TC-PERF-02 | `python scripts/measure_performance.py --detect-only` 与 `--list-only` 在部署机上打印数字；`tests/test_measure_performance.py` 守的是脚本的算术，不是机器的速度 | manual |
| AC-35 | 矩阵覆盖全部 29 条需求，每条都有验收项；过程文档齐全。 | TC-DOC-01、TC-DOC-02 | `scripts/check-ac-coverage.py`（归属与所点测试存在）；逐行走矩阵与 SRS 第 7.3 节要人工（TC-DOC-01、TC-DOC-02） | manual |
| AC-36 | 从采集到报告的链路不中断地现场跑通；模型迭代环能讲清并展示关键步骤。 | TC-DEMO-01、TC-DEMO-02 | `docs/demo-script-zh.md` 第 4 节（0:50–6:50）及它讲迭代环的收尾段；三次彩排（`PLAN.md` P4-07） | manual |

## 四、未闭环的行

按 `PLAN.md` P4-16，这些是缺陷，不许拿话术抹平。

- **AC-06——定时采集。** `server/` 里没有路由、表或定时器，六个定时批次和失败记录无从展示。归 `PLAN.md` P3-13。
- **AC-07——重拍标记。** `media_asset.is_retake` 每次采集都写 0，没有任何路由写过它，所以重拍不是自己的记录。质量拦截那一半由本行所列测试证明。归采集模块的下一项任务。
- **AC-20——点位分布。** 页面与契约里都没有热力图、排名或点位分布图；`docs/traceability-zh.md` TM-089 记着缺失的元素。归 `PLAN.md` P3-02。

## 五、用例与本页不一致的地方

用例的结论是 2026-11-12 通过读测试定下的。有六行在那之后才有了证据；本页采用证据，不动用例，让它的维护人重跑用例，而不是相信这张表。这些都不是凭空声明：每一行都点名了现在断言该句的测试。

| AC | 11-12 的用例结论 | 今天的证据 | 由谁交付 |
|---|---|---|---|
| `AC-08` | automated，附 `Not implemented: carrying a frame selection into job creation` | `tests/test_batch_selection.py` | P4-05，11-28 |
| `AC-09` | uncovered | `scripts/cleanup_retention.py`、`tests/test_cleanup_retention.py` | P3-08，11-27 |
| `AC-21` | uncovered | `tests/stats_view.mjs`，由 `tests/test_stats_view.py` 运行 | P3-02 的统计工作 |
| `AC-22` | manual | `tests/test_report_dashboard_agree.py` | P3-07，11-28 |
| `AC-26` | manual | `tests/test_class_thresholds.py` | P3-15，11-16 |
| `AC-28` | manual | `tests/test_monitoring.py` | P3-09，11-12 |

## 六、这一页怎么自检

- `python scripts/check-ac-coverage.py` 退出 0：36 条都有任务归属，且每个声称已闭环的任务都点了存在的测试。
- 每个编号恰好出现一次为行：`grep -cE '^\| AC-[0-9]{2} \|' docs/acceptance-checklist-zh.md` 打印 36，对英文文件跑同一条也打印 36。
- 证据列点到的每个测试路径都在 `tests/` 里存在；第三节点到的演示分钟是 `docs/demo-script-zh.md` 第 4 节的刻度。
- 这一对通过 `python scripts/check-bilingual.py`，且两份文件都列在 `docs/INDEX-zh.md` 与 `docs/INDEX-en.md` 里。

## 七、这一页不做什么

它不跑用例，不拥有用例，也不代替彩排。它不为 `PLAN.md` P4-04 还没记录的指标行声明状态；在数字和日期存在之前，它们一直是 `manual`。它是 `PLAN.md` P4-06 背后的证据索引，演示分钟就是 `docs/demo-script-zh.md` 里的那些。
