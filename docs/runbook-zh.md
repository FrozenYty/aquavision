# 运维手册

当重点不再是系统本身，而是要把它启动起来、搬到别处、备份好，或者查清楚它为什么停下来的时候——看这一页。
下面每一条都在本项目上实际跑过之后才写下来。

如果某一步在你这儿跑不通，那是这一页的缺陷，不是你的问题。请说出来。

## 1. 这一页是干什么的

`README` 负责让一份克隆跑起来。这一页管的是之后的全部：第二台机器、推理环境、冒险改动之前的备份、
凌晨两点要读的日志。它只假定你会用命令行，别的不假定。

## 2. 动手之前

- Python 3.11 或更新版本。
- 只要 Web 应用和它的测试：`pip install -r requirements-server.txt`。
- 演示需要的识别能力：**完整**环境，`pip install -r requirements.txt`。它锁定了 `ultralytics`，
  会连带装上 torch、torchvision 和第二个 OpenCV 构建——好几个 GB，而服务端永远不 import 它。
  两个环境要分开；见第 4 节。
- 不需要别的。摄像头、ESP32 和训练栈都是可选的：没有它们应用照样启动，并且它会明说，而不是失败。

## 3. 从克隆开始第一次部署

三条命令，按这个顺序，在仓库根目录执行。

```bash
python -m pip install -r requirements-server.txt
python scripts/init_db.py
python -m uvicorn app.main:app --app-dir server --port 8000
```

- `init_db.py` 建十四张表、播种四个类别、注册 `models/` 下交付的任何版本，并且——**仅在空库上**——创建
  第一个账号。它只打印一次该账号的密码，之后不再打印；趁终端还没滚走抄下来。重复执行是安全的：
  它不会覆盖密码，也不会把在线模型从操作员手里拿走。
- 在已有数据库上它同样安全，但它**不会加列**——见第 7 节。
- `--app-dir server` 是让 `app.main` 能在仓库根被 import 的原因。在 `server/` 里启动 `uvicorn` 也能跑，
  但那样配置中的相对路径解析方式不同，所以优先用这个写法。

然后打开页面，用第 2 步那个账号登录。从终端先看 `/api/health` 更快：它会报数据库状态、已挂载路由数量，
以及 JWT 密钥是否还是默认值。

## 4. 推理环境

识别需要 `ultralytics` 和 torch。服务端环境**故意**不带它们——那是 ADR 11 的论证，也让"只跑 API"的克隆
保持精简。所以一台要演示识别的机器上有**两个**环境。

建第二个，每个克隆建一次，放在它自己的环境里：

```bash
python -m venv .venv-infer
.venv-infer/Scripts/python -m pip install -r requirements.txt
```

`.venv-infer/` 在 `.gitignore` 里，所以不会进仓库。之后凡是要加载模型的命令，都用那个解释器：

```bash
.venv-infer/Scripts/python -m pytest tests/test_detect_real.py -o addopts="" -q
```

那三个测试只在这里跑，在别处一律跳过，因为它们是"交付的权重确实能加载、并且产出 API 所报的那些框"的
唯一证据。它们通过，就说明识别是通的。

**Windows 上有两件事会出问题，本项目两件都遇到过：**

- `python -m venv` 或 `pip` 在写**它自己刚创建的临时目录**时报 `PermissionError`。Python 给临时目录设的是
  仅属主可访问的权限，而受限进程并不是那个属主，所以把 `TMP` 指到别处没用。**向它要它声称需要的那种访问权限**，
  不要绕过。
- **同一个摄像头，一个解释器打得开、另一个打不开。** 写这一页的机器上，设备能从 Anaconda 环境打开，
  而从它上面建出来的任何虚拟环境都打不开——两者加载的是**同一个目录下逐字节相同的 OpenCV 文件**，
  所以差异在进程，不在 wheel，换 OpenCV 构建也修不好。对现场演示的实际后果：确认将来提供 socket 的
  那个解释器能打开摄像头，因为"有画面没识别"和"有识别没画面"都只是半场演示。
- 用户配置目录不可写时，`ultralytics` 会把设置目录写到**当前**目录，于是 `Ultralytics/` 出现在仓库根。
  运行之前把 `YOLO_CONFIG_DIR` 指到仓库外的可写路径；该目录同时也在 gitignore 里，所以即便有一份残留也
  不可能被提交。

## 5. 备份与恢复

构成状态的是两样东西：数据库，以及数据根下的采集帧（默认 `data/`，设了 `AV_DATA_DIR` 则是它）。
两样都要备，否则恢复回来会是一堆指向已不存在图像的记录。

SQLite 开发默认库：

```bash
python -c "import sqlite3; sqlite3.connect('data/app.db').execute('VACUUM INTO \"data/backup-app.db\"')"
```

这是安全写法：**服务运行期间直接复制文件可能截到写了一半的页**。`VACUUM INTO` 写的是一致副本。
能停服务就先停，那样直接复制文件也可以。

`DB_DSN` 指向 PostgreSQL 时：

```bash
pg_dump --no-owner --format=custom "$DB_DSN" > backup.dump
```

恢复就是把上面的过程倒过来：停服务、把数据库文件或 dump 放回去、把采集帧目录放回它旁边、启动服务。
然后查 `/api/health`、登录、随便打开一帧——**一个能过健康检查却显示不出帧的恢复，恢复错了那一半**。

## 6. 轮换 JWT 密钥

每个已签发的令牌都用 `AV_JWT_SECRET` 签名，而令牌是无状态的：没有会话表可以清。所以轮换密钥会
**一次性作废全部令牌**，所有人都得重新登录。这是有意为之，不是副作用——**这也是让泄露的密钥退休的唯一办法**。

```bash
# 在 .env 或服务环境里设一个新值，然后重启进程
AV_JWT_SECRET="<一段足够长的随机串>"
```

只要还在用随仓库附带的默认值，`/api/health` 就会报 `jwt_secret_is_default: true`。一个可达的机器上
该字段为 `true` 是一处发现，不是细节：凡是能读到仓库的人都能为它伪造一个令牌。

轮换**并不**满足"改密码使已签发令牌失效"——那是另一套机制，现在由每用户的令牌纪元承担，不需要操作员动作。

## 7. 升级表结构

**`init_db.py` 现在会就地升级已有数据库。** 以前这里只能如实说清缺口：`create_all` 能补一张缺的*表*，却不会给已存在的表加**列**，于是加在 `server/app/models.py` 里的一列只到得了新库，旧库的每条查询都会报

```text
sqlite3.OperationalError: no such column: sys_user.token_epoch
```

而应用把它报成**"数据库无法连接，请确认已启动"**——报错了：库是通的，只是少了一列。2026-11-12 真的发生过。

自 `P3-25` 起，一条命令就能补上：

```bash
python scripts/init_db.py
```

它先补齐缺的东西，再把模型声明了、表里还没有的列按模型给的默认值就地加上，一行数据不动：

```text
schema upgraded: sys_user.token_epoch (existing rows kept)
```

规则是**只加不改**：不删列、不改类型、不碰任何一行。这是有意的——多一列只花几个字节，删错一列丢的是数据。**加不上**的列（`NOT NULL` 且没有默认值，而表里已有行）会被拒绝、脚本以退出码 1 报出列名，因为只升了一半的表结构会在第一条选中该列的查询上失败：

```text
not upgraded: sys_user.real_name: NOT NULL without a server default
```

遇到那种情况，或者超出"加列"之外的变化（改名、改类型），仍然走手工路线：先备份、手工改表、**并记录做了什么**——一份没人写下来的手工表结构，就是两台机器对数据库内容各执一词的起源。

## 8. 读日志

两个地方：进程日志，说明应用做了什么；以及 `sys_log` 表，那是复核者会读的审计轨迹。两者都必要，
谁也代替不了谁。

一次权限被拒，是 `sys_log` 里 `action = 'forbidden'` 的一行，路由在 `target_id`，调用者在 `user_id`：

```bash
python -c "import sqlite3; [print(r) for r in sqlite3.connect('data/app.db').execute(\"SELECT created_at, module, action, target_id, user_id FROM sys_log WHERE action='forbidden' ORDER BY log_id DESC LIMIT 20\")]"
```

**登录失败是刻意不记录的。** 这个决定写在 `PROGRESS.md` 里：未认证的请求根本进不到角色矩阵，
没有用户可以记录，而把每个畸形请求头都记下来会让这张表变成无需凭据即可写入的无界黑洞。
那类情况请去进程日志里找，不在这里。

## 9. 队列停了怎么办

`/api/monitor` 是操作员的窗口：队列深度、帧数量、磁盘水位，以及检测线程是否活着。如果它报出
`worker.problem`，队列不是慢，是停了，消息会说明是两种原因中的哪一种、以及该做什么。

按这个顺序查三件事：worker 是否被关掉了（`AV_WORKER_ENABLED`）、进程日志里线程有没有抛异常、
队列里是否有任务找不到它们的帧。重启服务是安全的：跑到一半的任务会继续，而不是丢失。

## 10. 可以在运行时修改的配置

这些存在 `sys_param` 里，并且是在**需要它的时候**才读，不是在启动时读一次，所以一次修改会在几秒内
约束新工作，且不需要重启（ADR 15）。每项都有取值范围，超出范围的值在页面上就被拒绝，若从别的途径
混进来也会被忽略。

| 配置项 | 范围 | 管什么 |
|---|---|---|
| `max_concurrency` | 1–32 | 同时允许几个检测任务运行 |
| `quality_threshold` | 0–100 | 一帧要通过多少分才能进队列 |
| `detect_interval_ms` | 50–10000 | 实时画面多久跑一次识别 |
| `camera_index` | 0–9 | 服务打开哪个采集设备 |
| `retention_days` | 1–3650 | 中间帧要到多少天才算清理候选 |

其余的只能用环境变量：密钥、DSN、时区、数据根、装置端口。那些是部署决定，改一个就意味着刻意重启。

## 11. 本手册不覆盖的部分

- **硬件。** 接线和光学指标在 `procurement-en.md` 与 `rig-state-machine-en.md` 里。
- **训练。** 见 `PLAN.md` 的 P4 与 `test-plan-en.md`。
- **迁移机制**，因为它还不存在；等它存在了，第 7 节会缩成一条命令，这一段也会删掉。
- **第二个应用进程。** 参数缓存是短 TTL 而不是写时失效，这对单进程是正确的，对多进程未经验证；
  该重新审视什么，ADR 15 里记着。
