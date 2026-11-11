# 海瞳 AquaVision

[English](README.md)

基于 YOLOv8 的水下生物识别与监测系统。摄像头实时采集水下影像，识别四类目标
（海参、海胆、扇贝、海星）的种类、数量与位置，人工复核后把修正结果回流
到训练样本，形成「采集—识别—复核—迭代」的闭环。

> 本文为 `README.md` 的中文对照版，以英文版为准。

**当前状态**：P2 阶段，进展见 [PROGRESS.md](PROGRESS.md)。后端在同一源下同时提供接口与十三个页面，
在全新数据库上可以正常登录，ESP32 固件可编译并能驱动面板。检测会在采集到的帧上运行已注册的模型并写入目标框，
采集装置尚未组装，摄像头链路由硬件决定。

## 快速开始

以下每一步都在干净克隆上实际跑过才写下来。**哪一步不work，那是这份文档的缺陷，请说出来。**

**需要**：Python 3.11 或更高版本，其它都可以没有。摄像头、ESP32 与训练环境都是可选的，
没有它们应用照样能启动。

### 一、克隆并进入

```bash
git clone https://github.com/FrozenYty/aquavision.git
cd aquavision
```

### 二、创建环境

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Windows cmd
.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate
```

### 三、安装依赖

```bash
python -m pip install -r requirements-server.txt
```

这是网页应用与它测试所需的全部依赖。`requirements.txt` 是**完整**环境，额外固定了 `ultralytics`，
它会连带拉下 torch、torchvision 和第二个 OpenCV 构建——好几个 GB，而服务端从不 import 它。
只有在要训练的那台机器上才用完整版。

### 四、创建数据库

```bash
python scripts/init_db.py
```

它建十四张表、灌入四个物种，并**只在空库上**创建第一个账号。**密码只打印一次，请立刻记下。**

```
username: admin
password: <只打印一次，之后无法找回>
```

想自己指定就加 `--admin-password`（或设 `AV_ADMIN_PASSWORD`），想换库就加 `--dsn` 或设 `DB_DSN`。
脚本是幂等的：再跑一次什么都不会变，也**不会重置密码**。

### 五、启动

```bash
python -m uvicorn app.main:app --app-dir server --port 8000
```

**一个进程**。它同时提供接口和页面，所以没有第二个服务器，也没有要配的代理。

### 六、打开

| 内容 | 地址 |
|---|---|
| 应用本体 | <http://127.0.0.1:8000/> —— 会跳到登录页 |
| 可交互的接口文档 | <http://127.0.0.1:8000/api/docs> |
| 健康状态与配置 | <http://127.0.0.1:8000/api/health> |

用第四步打印的 `admin` 与密码登录。

### 七、跑测试

```bash
pytest -q
```

229 个测试，约一分钟。不需要摄像头、数据库服务或网络。

### 出问题的时候

| 现象 | 原因与处理 |
|---|---|
| 密码是对的，登录却说「账号或密码不正确」 | 服务端打开的库不是你建的那个。两边都用**仓库根目录**下的 `data/app.db`，与从哪个目录启动无关，所以先确认两个终端里都没设 `DB_DSN`。 |
| `Address already in use` | 8000 被占用——停掉另一个进程，或换 `--port 8001`。 |
| 每个页面都说「没有找到接口服务」 | 页面是从别处打开的（比如另一个标签里还留着 `python -m http.server`）。请打开第六步的地址。 |
| 页面空白，控制台提到 CORS 或 `Origin null` | HTML 是从文件系统直接打开的。它必须经由 HTTP 提供——第五步就是那个服务器。 |
| `ModuleNotFoundError: app` | 启动时漏了 `--app-dir server`，或目录不对。 |

### 现在能做什么，还不能做什么

这份清单是诚实的，因为夸大的 README 比简短的更糟。

- **能用**：登录与角色、帧列表与详情、复核提交、统计分析、数据集导出、系统设置——都走真实数据表与真实数据库。
- **没有硬件也能用**：以上全部；采集相关页面会退化为空列表。
- **还不能**：批量识别尚未满足 `P3-01` 的验收（一百帧、运行中可查进度、重启后继续），但接口本身已经会建排队任务；采集页按 api-contract 第七节走 `/ws/capture` 实时流，轮询只是 socket 无法提供时的兜底。装置链路的 PC 端已经存在（`server/app/rig/`），但只有设置了 `AV_RIG_PORT` 才会启动；插上板子后第一件事是跑 `scripts/test_rig_link.py`。

### 不想起后端：原型模式

页面也可以跑在模拟数据上，用于没有数据库的演示：

```bash
python -m http.server 8765 --directory web
```

然后打开 <http://127.0.0.1:8765/templates/login.html?mock=1>。该参数只对当前标签页生效，会把所有调用
切到 `web/static/mock/`；不加则调用真实接口并要求登录。**模拟模式按设计会掩盖后端缺陷**——
它用来展示界面，不用来测试。

## 文档

| 文档 | 说明 |
|---|---|
| [文档索引](docs/INDEX-zh.md) | 哪份文档回答什么，以及改一处要连带改哪些 |
| [需求定义书 V1.12](docs/srs-zh.md) | 功能需求 29 条、用例 9 个、数据表 14 张、验收项 36 条 |
| [任务计划](PLAN.md) | 阶段、任务与门禁，团队的任务契约 |
| [总体架构](docs/architecture-zh.md) · [English](docs/architecture-en.md) | 分层、依赖规则、运行时模型、一帧的生命周期 |
| [接口约定](docs/api-contract-zh.md) · [English](docs/api-contract-en.md) | REST 路径、响应封装、错误码、WebSocket 协议 |
| [数据模型](docs/data-model-zh.md) · [English](docs/data-model-en.md) | 十四张表、字段、索引、文件存储 |
| [测试计划](docs/test-plan-zh.md) · [English](docs/test-plan-en.md) | 测试分层、数据集划分、指标与验收 |
| [术语表](docs/glossary-en-zh.md) | 中英对照，代码与文档共用的唯一词表 |
| [决策记录](docs/adr/) | 十三份决策记录及其理由：09 已被 10 取代，07 的 pytest 条款已被 11 取代，12 增补了 08；逐条列在 `docs/architecture-zh.md` 第十节 |

设计文档以英文版为准，中文为对照版，两者必须在同一次提交内同步。

## 目录结构

```
docs/        设计文档与需求定义书
docs/adr/    架构决策记录
scripts/     数据集准备、训练、数据库初始化、文档检查
server/      FastAPI 后端——接口，以及从这个版本起的页面
web/         静态前端页面
firmware/    ESP32 固件
tests/       测试
```

## 技术栈

| 层次 | 选择 |
|---|---|
| 采集 | USB 摄像头（1080P、手动曝光、UVC）配合 OpenCV |
| 识别 | PyTorch + Ultralytics YOLOv8n，三项改进：水下色彩校正、EMA 注意力、WIoU v3 |
| 后端 | Python 3.11、FastAPI、SQLAlchemy 2.1；本地跑用 SQLite，部署用 PostgreSQL 14 |
| 前端 | HTML5、Bootstrap 5.3.3、手写 SVG 图表、原生 ES 模块，无构建步骤；Bootstrap 已本地化于 `web/static/vendor/` |
| 装置控制 | ESP32-S3（Arduino 框架，PlatformIO 构建）；0.96 寸 OLED 与两颗状态指示灯 |

指标目标：四类目标 mAP@0.5 ≥ 0.75，比基线提升 +0.03，推理速度不低于基线的 90%。

## 团队

| 成员 | 分工 |
|---|---|
| 姚天宇 | 采集链路、系统架构、需求定义 |
| 高天翔 | 模型训练与改进、推理服务、后端接口 |
| 孙健恒 | 前端页面、标注与数据集 |
| 付怡佳 | 文档、测试用例、验收检查 |

## 贡献

第一次提交前请先读 [CONTRIBUTING.md](CONTRIBUTING.md)：
分支、提交、拉取请求与文档规则都在那里。

如果你是 AI 助手，先读 [AGENTS.md](AGENTS.md)——它说明你属于哪条线。

## 模型权重

`models/<version_name>/` 是本项目交付的模型要放的地方——`best.pt`、`labels.txt` 与 `metrics.json`——纳入版本库而不是另行发布，这样文件到位之后，一份干净的克隆也能注册版本并跑起识别。**这一版里该目录是空的：还没有任何权重文件被交付。** 这份副本仍欠在训练那一侧；在它落地之前，干净的克隆没有东西可注册，识别路由会返回 501，因为没有任何模型权重被注册。这项决定及其代价见 [ADR 13](docs/adr/13-weights-in-the-repository.md)。

- **首先要放进来的是什么。** 探索性基线（YOLOv8n），它的用途是让仪表盘和演示有真实数字。它**不是**官方 E0 基线——E0 在 `P4-01` 用冻结数据集训练。不要把它的指标当作本项目的结果引用。
- **它从哪来。** 本项目团队在 DUO 数据集上训练得到。**本仓库不再分发任何 DUO 图像**——`datasets/` 在忽略列表里——只分发从中学到的权重。
- **怎么用。** `python scripts/register_model.py --weights models/<version_name>/best.pt`，然后以管理员身份激活该版本。目录布局见[数据模型](docs/data-model-zh.md)第五节。
- **许可与引用。** 代码为 MIT。权重由本项目团队以同样条款提供。DUO 数据集归其作者所有且未声明自身许可，因此使用这些权重时请引用 [DUO 论文](https://arxiv.org/abs/2106.05681)。

## 许可证

MIT，见 [LICENSE](LICENSE)。

## 说明

训练数据来自公开水下数据集与团队自行拍摄的影像，不含真实调查数据与个人信息。
