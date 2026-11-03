# 开发规范

> 本文为 `CONTRIBUTING.md` 的中文对照版，以英文版为准。
> 同步于：2026-11-03

本仓库的协作约定。第一次提交前请先读完。

## 一、分支

`main` 受保护，所有工作都在短期分支上：

```
feat/capture-quality    fix/review-rollback    docs/api-contract
```

通过 Pull Request 合入 `main`，合并后删除分支。

分支名全小写、连字符分隔、带类型前缀。不要中文，不要拼音。

## 二、提交

用 Conventional Commits，作用域写模块名：

```
feat(capture): add frame quality scoring
fix(detect): drop stale boxes when frame_id changes
docs(adr): record decision to drop pan-tilt
chore(ci): run ruff on pull requests
```

类型只有这些：`feat`、`fix`、`docs`、`style`、`refactor`、`test`、`chore`。
模块：`capture`、`detect`、`review`、`stats`、`model`、`web`、`firmware`、`docs`、`ci`。

一次提交只做一件事。如果提交信息里需要用“并且”，就拆成两次。

## 三、Pull Request

- 单个 PR 改动**不超过 400 行**，超了就拆。
- 按模板填写：改了什么、怎么验证的、还影响哪些地方。
- 至少**一人 review 通过**。组长的 PR 由模块负责人审。
- 用 **squash** 合并——一个功能在 `main` 上只留一个提交。
- 有关联 Issue 时写 `Closes #12`。

比小修大的活先开 Issue；小修可以直接提 PR。

## 四、代码风格

**Python** —— 由 `ruff` 统一管（检查 + 格式化），每次提交前跑：

```
ruff check . && ruff format .
```

- 所有公开函数必须写类型标注。
- 注释与文档字符串用英文。
- 单文件不超过 300 行，单函数不超过 50 行。
- 业务错误抛 `BizError`，不许裸抛 `Exception`。
- 用 `logging`，不用 `print`（`scripts/` 除外）。
- 配置走 `.env` 与 `pydantic-settings`，代码里不许出现硬编码路径与密钥。

**前端** —— 不引框架，不引构建工具。

- 所有 HTTP 调用走 `web/static/js/api.js`，页面脚本里禁止直接写 `fetch()`。
- 一页一个文件：`capture.html`、`review.html`、`stats.html`。
- 样式用 Bootstrap 工具类加 `web/static/css/app.css`，禁止行内 `style=`。
- 业务逻辑写在 `.js` 里，不写在 HTML 里。

**固件** —— ESP32，Arduino 框架。

- 引脚定义只写在 `config.h`。
- 串口命令与回包只在 `protocol.h` 里定义。
- `firmware/README.md` 必须写清接线表、烧录步骤与串口协议。

## 五、文档

- **文件名一律英文**，小写、连字符分隔；内容可以是中文。
- 交付物带版本、不带日期：`srs-v1.2.docx`。
- 设计文档成对出现：`architecture-en.md` 与 `architecture-zh.md`。README 同理：`README.md` 为英文，`README-zh.md` 为中文对照。
- **以英文版为准**：先改英文，同一个 PR 里再同步中文。
- 图用 Markdown 里的 Mermaid 代码块，不传图片文件。
- `PROGRESS.md` 每周更新，用英文，最多五行。

## 六、数据与资产

不许提交：

```
*.pt  *.onnx          模型权重
data/                 帧、缩略图、导出文件
datasets/             训练与测试数据
*.mp4  *.avi          视频
.env                  密钥
```

权重放 GitHub Releases，数据集放外部存储，在 README 里给链接和校验和。

仓库体积控制在 20 MB 以内。

## 七、每周节奏

| 时间 | 做什么 |
|---|---|
| 周三课后 | 20 分钟同步，只说卡点，不做进度汇报 |
| 周五 | 合并本周 PR，不把分支留到周末 |
| 周五 | 15 分钟走查本周的 PR |

## 八、完成的定义

以下全部满足，改动才算完成：

- [ ] `ruff check .` 与 `ruff format --check .` 通过
- [ ] 本地 `pytest` 通过
- [ ] 中英对照文档已同步（`scripts/check-bilingual.py`）
- [ ] PR 模板填写完整，且有人 review 通过
- [ ] 行为有变化时，`docs/` 已同步更新
