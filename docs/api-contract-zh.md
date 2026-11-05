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

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/auth/login` | 获取令牌 |
| GET | `/api/auth/me` | 当前用户与角色 |
| GET | `/api/cameras` | 枚举可用摄像头 |
| POST | `/api/capture/sessions` | 开一次采集会话 |
| POST | `/api/capture/sessions/{id}/frames` | 抓一帧 |
| POST | `/api/capture/sessions/{id}/close` | 关闭会话 |
| POST | `/api/detect/frames/{frame_id}` | 单帧识别 |
| POST | `/api/detect/batches` | 发起批量任务 |
| GET | `/api/tasks/{task_id}` | 任务进度 |
| GET | `/api/frames` | 查询帧 |
| GET | `/api/frames/{frame_id}` | 帧详情 |
| GET | `/api/frames/{frame_id}/objects` | 检测框 |
| POST | `/api/review/frames/{frame_id}` | 提交复核 |
| POST | `/api/compare/frames/{frame_id}` | 同一帧跑基线与改进模型 |
| GET | `/api/stats/species` | 物种组成统计 |
| GET | `/api/stats/quality` | 质量拦截率 |
| GET | `/api/models` | 模型版本列表 |
| POST | `/api/models/{id}/activate` | 切换线上模型 |

### 帧对象

```json
{
  "frame_id": "20261103T193012-0042",
  "session_id": "s-a3-001",
  "captured_at": "2026-11-03T19:30:12.418+08:00",
  "quality": { "sharpness": 71, "brightness": 64, "colorcast": 58, "score": 66, "verdict": "ok" },
  "env": { "turbidity_rel": 12 },
  "width": 1920, "height": 1080
}
```

### 检测框

```json
{ "class_code": "holothurian", "confidence": 0.87, "x": 0.41, "y": 0.52, "w": 0.12, "h": 0.09 }
```

坐标归一化到 `0..1`，相对整幅图像，原点在左上角。

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
