# 接口约定

> 本文为 `api-contract-en.md` 的中文对照版，以英文版为准。
> 同步于：2026-11-03

> 维护人：@Gtechson · 重审时机：接口或字段变化时

## 一、总则

- 基础路径 `/api`，所有接口返回 JSON。
- 方法遵循 REST：`GET` 读、`POST` 建或执行动作、`PATCH` 改、`DELETE` 删。
- 字段名在 JSON 与数据库中都使用 `snake_case`。
- 除特别说明，标识符都是整数（`BIGINT`）。

## 二、响应封装

无论成功失败，响应都是这个结构：

```json
{ "code": 0, "message": "ok", "data": { }, "request_id": "req-7f3a" }
```

- `code`——成功为 `0`，非 0 表示失败。
- `message`——中文、可直接展示给用户。
- `data`——载荷，失败时为 `null`。
- `request_id`——每个响应都带，服务端日志里同值。

## 三、错误码

| 段位 | 含义 | 示例 |
|---|---|---|
| `400xx` | 请求不合法 | `40001` 缺少参数 |
| `401xx` | 未认证 | `40101` 令牌过期 |
| `403xx` | 无权限 | `40301` 角色无权访问 |
| `404xx` | 不存在 | `40401` 帧不存在 |
| `500xx` 前的 `409xx` | 状态冲突 | `40901` 任务已在运行 |
| `500xx` | 服务端错误 | `50001` 内部错误 |

不许直接抛 500 加堆栈，一律包装成 `50001`，细节写日志。

## 四、认证

`POST /api/auth/login` 返回 JWT，后续请求带 `Authorization: Bearer <token>`。

- 令牌有效期 8 小时，本项目不做刷新令牌。
- 角色：`observer`、`analyst`、`algo`、`admin`。
- 权限在服务端校验，前端隐藏菜单只是展示层。

## 五、分页与时间

```
GET /api/frames?page=1&size=24&site=A3&from=2026-11-01&to=2026-11-03
```

```json
{ "items": [], "total": 412, "page": 1, "size": 24 }
```

- `size` 默认 24，最大 100。
- 时间一律 ISO 8601 带时区，库内存 UTC，展示转本地。
- 日期筛选两端都含，按服务端时区解释。

## 六、REST 接口

每条路由标注它服务的需求，优先级继承 SRS 表 3-1。于是范围问题去 SRS 里查，不在这里数行数：
**路由数量是结果，不是指标。**

| 方法 | 路径 | 用途 | 需求 | 优先级 |
|---|---|---|---|---|
| POST | `/api/auth/login` | 获取令牌 | FR-M1-01 | P0 |
| GET | `/api/auth/me` | 当前用户与角色 | FR-M1-01 | P0 |
| GET | `/api/users` | 账号列表 | FR-M1-03 | P1 |
| POST | `/api/users/{id}/status` | 停用或恢复账号 | FR-M1-03 | P1 |
| POST | `/api/users/{id}/reset-password` | 重置密码 | FR-M1-03 | P1 |
| GET | `/api/logs` | 操作日志 | FR-M1-04 | P1 |
| GET | `/api/cameras` | 枚举可用摄像头 | FR-M2-01 | P0 |
| POST | `/api/capture/sessions` | 开一次采集会话 | FR-M2-01 | P0 |
| GET | `/api/capture/sessions` | 采集会话列表 | FR-M2-04 | P1 |
| POST | `/api/capture/sessions/{id}/frames` | 抓一帧 | FR-M2-01 | P0 |
| POST | `/api/capture/sessions/{id}/close` | 关闭会话 | FR-M2-01 | P0 |
| GET | `/api/frames` | 查询帧 | FR-M2-04 | P1 |
| GET | `/api/stats/quality` | 质量拦截率 | FR-M2-03 | P0 |
| POST | `/api/detect/frames/{frame_id}` | 单帧识别 | FR-M3-01 | P0 |
| POST | `/api/detect/batches` | 发起批量任务 | FR-M3-02 | P0 |
| GET | `/api/tasks` | 识别任务列表 | FR-M3-02 | P0 |
| GET | `/api/tasks/{task_id}` | 任务进度 | FR-M3-02 | P0 |
| POST | `/api/tasks/{id}/cancel` | 取消任务 | FR-M3-02 | P0 |
| POST | `/api/tasks/{id}/retry` | 重试失败任务 | FR-M3-02 | P0 |
| GET | `/api/frames/{frame_id}` | 帧详情 | FR-M3-04 | P0 |
| GET | `/api/frames/{frame_id}/objects` | 检测框 | FR-M3-04 | P0 |
| POST | `/api/review/frames/{frame_id}` | 提交复核 | FR-M4-01 | P0 |
| GET | `/api/hard-samples` | 难例池 | FR-M4-03 | P1 |
| DELETE | `/api/hard-samples/{frame_id}` | 移出难例池 | FR-M4-03 | P1 |
| GET | `/api/datasets` | 数据集快照 | FR-M4-04 | P1 |
| POST | `/api/datasets` | 导出数据集快照 | FR-M4-04 | P1 |
| GET | `/api/stats/corrections` | 复核修正分布 | FR-M4-02 | P1 |
| GET | `/api/stats/species` | 物种组成统计 | FR-M5-01 | P1 |
| GET | `/api/stats/trend` | 每日采集量 | FR-M5-03 | P2 |
| GET | `/api/reports` | 报告历史 | FR-M5-04 | P1 |
| POST | `/api/reports` | 生成报告 | FR-M5-04 | P1 |
| GET | `/api/models` | 模型版本列表 | FR-M6-01 | P0 |
| POST | `/api/models/{id}/activate` | 切换线上模型 | FR-M6-02 | P1 |
| GET | `/api/experiments` | 训练实验列表 | FR-M6-03 | P0 |
| POST | `/api/compare/frames/{frame_id}` | 同一帧跑基线与改进模型 | FR-M6-03 | P0 |
| GET | `/api/species` | 物种字典与阈值 | FR-M6-04 | P0 |
| PATCH | `/api/species/{class_code}` | 修改分类别阈值 | FR-M6-04 | P0 |
| GET | `/api/params` | 系统参数 | FR-M7-01 | P1 |
| PATCH | `/api/params` | 修改系统参数 | FR-M7-01 | P1 |
| GET | `/api/monitor` | 运行监控 | FR-M8-01 | P1 |
| GET | `/api/messages` | 站内消息 | FR-M8-02 | P2 |
| POST | `/api/messages/{id}/read` | 标记消息已读 | FR-M8-02 | P2 |

### 帧对象

```json
{
  "frame_id": "20261103T193012-0042",
  "session_id": "s-a3-001",
  "captured_at": "2026-11-03T19:30:12.418+08:00",
  "quality": { "score": 66, "verdict": "ok" },
  "env": { "turbidity_rel": 12 },
  "width": 1920, "height": 1080
}
```

总分背后的三个分项——清晰度、亮度、色偏——由
`POST /api/capture/sessions/{id}/frames` 放在 `quality_components` 里返回，**不入库**：帧表只留总分与判定，
那才是后续每一步实际读的东西。分项是拍摄当下的诊断量，不是图像的属性。

### 检测框

```json
{
  "object_id": 10231,
  "class_code": "holothurian",
  "confidence": 0.87,
  "x": 0.41, "y": 0.52, "w": 0.12, "h": 0.09,
  "is_manual": 0,
  "review_status": 0
}
```

坐标归一化到 `0..1`，相对整幅图像，原点在左上角。

- `object_id` —— `detect_object` 主键；复核页要能稳定地指向某个框。
- `is_manual` —— `0` 自动识别，`1` 复核时人工补画。
- `review_status` —— `0` 待复核，`1` 已确认，`2` 已修改，`3` 已驳回。

### 复核提交

```
POST /api/review/frames/{frame_id}
{ "objects": [ <检测框> ], "note": "礁石误判为海参，已删除" }

→ { "version_no": 2, "object_count": 11, "hard_sample": true }
```

请求体提交**整份修正后的框集合**，不是增量差异：复核画布才是准，差异还要跟一个可能已经变过的版本合并。
`hard_sample` 表示这一帧是否进入了难例池（FR-M4-03）。

### 数据集快照

```json
{
  "dataset_id": 3,
  "snapshot_name": "DS-V3",
  "split_ratio": "7:2:1",
  "seed": 42,
  "frame_count": 7782,
  "status": "ready",
  "created_at": "2026-11-06T15:40:00+00:00"
}
```

`status` 取 `building`、`ready` 或 `archived`。帧级归属存在快照条目表里，不放进响应——七千帧不是载荷。

### 巡检报告

```json
{
  "report_id": 12,
  "report_code": "RP261106-001",
  "period_start": "2026-11-01T00:00:00+00:00",
  "period_end": "2026-11-30T23:59:59+00:00",
  "template": "standard",
  "basis": "reviewed",
  "model_version_id": 3,
  "status": "ready",
  "file_path": "reports/RP261106-001.md",
  "created_at": "2026-11-06T15:41:00+00:00"
}
```

### 系统参数

```json
{
  "retention_days": 30,
  "max_concurrency": 2,
  "detect_interval_ms": 300,
  "quality_threshold": 60,
  "camera_index": 0
}
```

`PATCH` 接受其中任意子集，返回完整的一组。每次改动都写入审计日志并记录前后值（AC-27）。

## 七、WebSocket 协议

`/ws/capture`，每个浏览器标签页一条连接。

| 方向 | 类型 | 载荷 |
|---|---|---|
| 客户端 → 服务端 | `start` | `{ "session_id": "...", "fps": 10, "detect_interval_ms": 300 }` |
| 服务端 → 客户端 | 二进制 | JPEG 字节，一条消息一帧 |
| 服务端 → 客户端 | `detect` | `{ "frame_id": "...", "boxes": [], "latency_ms": 128 }` |
| 服务端 → 客户端 | `status` | `{ "fps": 9.8, "queue": 0, "model": "v8n-e3" }` |
| 客户端 → 服务端 | `stop` | `{}` |

图像走二进制帧，结果走 JSON，两者靠 `frame_id` 关联，**不靠顺序**。

## 八、帧与结果的对齐

- 服务端在抓帧时生成 `frame_id`，每条结果都带上它。
- 客户端维护一张 `frame_id → boxes` 的小表，只有在新帧尚未到达时才渲染这组框。
- **过期结果直接丢弃**：比当前显示帧更旧的框不排队、不补画。
- `latency_ms` 从服务端抓帧时刻算到结果构造完成。

## 九、版本

- 破坏性变更升路径：`/api/v2/...`。同一版本内只许加字段，不许删或改名。
- 每个识别响应都记 `model_version` 与 `conf_threshold`，保证结果可复现。
