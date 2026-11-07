# 海瞳 AquaVision

[English](README.md)

基于 YOLOv8 的水下生物识别与监测系统。摄像头实时采集水下影像，识别四类目标
（海参、海胆、扇贝、海星）的种类、数量与位置，人工复核后把修正结果回流
到训练样本，形成「采集—识别—复核—迭代」的闭环。

> 本文为 `README.md` 的中文对照版，以英文版为准。

**当前状态**：P1 阶段，进展见 [PROGRESS.md](PROGRESS.md)。后端可用（`uvicorn`，42 条契约路由），
十三张页面以模拟数据运行，ESP32 固件可编译；采集装置尚未组装。

## 文档

| 文档 | 说明 |
|---|---|
| [文档索引](docs/INDEX-zh.md) | 哪份文档回答什么，以及改一处要连带改哪些 |
| [需求定义书 V1.10](docs/srs-zh.md) | 功能需求 29 条、用例 9 个、数据表 13 张、验收项 36 条 |
| [任务计划](PLAN.md) | 阶段、任务与门禁，团队的任务契约 |
| [总体架构](docs/architecture-zh.md) · [English](docs/architecture-en.md) | 分层、依赖规则、运行时模型、一帧的生命周期 |
| [接口约定](docs/api-contract-zh.md) · [English](docs/api-contract-en.md) | REST 路径、响应封装、错误码、WebSocket 协议 |
| [数据模型](docs/data-model-zh.md) · [English](docs/data-model-en.md) | 十三张表、字段、索引、文件存储 |
| [测试计划](docs/test-plan-zh.md) · [English](docs/test-plan-en.md) | 测试分层、数据集划分、指标与验收 |
| [术语表](docs/glossary-en-zh.md) | 中英对照，代码与文档共用的唯一词表 |
| [决策记录](docs/adr/) | 十条已采纳的决定及其理由 |

设计文档以英文版为准，中文为对照版，两者必须在同一次提交内同步。

## 结构

```
docs/        设计文档与需求定义书
docs/adr/    架构决策记录
scripts/     数据准备、训练评估、文档校验
server/      服务端（FastAPI）
web/         前端静态页面
firmware/    单片机固件（ESP32）
tests/       测试
```

## 技术路线

| 层 | 选型 |
|---|---|
| 采集 | USB 摄像头（1080P、手动曝光、免驱 UVC）+ OpenCV |
| 识别 | PyTorch + Ultralytics YOLOv8n，三项改进：水下色彩校正、EMA 注意力、WIoU v3 |
| 服务 | Python 3.11、FastAPI、SQLAlchemy 2.1、PostgreSQL 14 |
| 前端 | HTML5、Bootstrap 5.3.3、ECharts 5，原生 ES 模块，无构建步骤；第三方库放在 `web/static/vendor/` |
| 采集控制 | ESP32-S3，Arduino 框架 + PlatformIO 构建；0.96 寸 OLED 与两个状态灯 |

目标指标：四类物种 mAP@0.5 ≥ 0.75，改进模型较基线提升 ≥ 0.03，
推理速度不低于基线 90%。

## 前端预览

页面无需构建。用静态服务器打开 `web/` 目录：

```bash
python -m http.server 8765 --directory web
```

然后访问 <http://localhost:8765/templates/login.html>。在 `web/static/js/api.js` 的 `USE_MOCK`
关闭之前，数据来自 `web/static/mock/`。

## 团队

| 成员 | 负责 |
|---|---|
| 姚天宇 | 采集链路、系统架构、需求文档 |
| 高天翔 | 算法训练与改进、推理服务、后端接口 |
| 孙健恒 | 前端页面、数据标注与数据集 |
| 付怡佳 | 文档、测试用例、验收核对 |

## 协作

第一次提交前请读 [CONTRIBUTING.md](CONTRIBUTING.md)（仅英文）。
分支、提交、Pull Request 与文档规则都在那里。

如果你是 AI 助手，先读 [AGENTS.md](AGENTS.md)，它会告诉你该在哪条线上干活。

## 许可

MIT，见 [LICENSE](LICENSE)。

## 说明

训练数据来自公开水下数据集与小组自采影像，不含真实调查数据与个人信息。
