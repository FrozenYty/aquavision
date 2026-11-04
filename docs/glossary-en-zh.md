# Glossary — English ↔ 中文

Single source for terminology. When a word appears in code, docs or UI, use the term from this
table. Do not invent synonyms.

## 1. Rules

- **One concept, one word.** If the table says `capture`, the code must not say `acquire`.
- Chinese terms are for the `-zh` documents and the UI. English terms are for code, commit
  messages and `-en` documents.
- A new term is added here in the same PR that introduces it.

## 2. Core terms

| 中文 | English | 不要用 | 说明 |
|---|---|---|---|
| 采集 | capture | acquire, collect, grab | 从摄像头取帧的动作与链路 |
| 采集会话 | capture session | batch, run | 一次连续采集，`session_id` 标识 |
| 帧 | frame | image, picture, shot | 一次拍摄产生的单张图像 |
| 识别 | detection | recognition, identification | 目标检测，输出框与类别 |
| 检测框 | bounding box | rect, region | 归一化坐标，原点左上 |
| 复核 | review | verify, check, audit | 人工修正自动结果 |
| 难例 | hard sample | hard case, bad case | 低置信、被修正或跨模型不一致的样本 |
| 基线模型 | baseline model | base model, original | 未经改进的 YOLOv8n |
| 改进模型 | improved model | new model, ours | 加了改进点的模型 |
| 消融实验 | ablation study | comparison test | 逐项加码、单独评估贡献的实验 |
| 类别码 | class code | label, category id | 与模型 `labels.txt` 完全一致的标识 |
| 物种字典 | species dictionary | class table | 类别码、名称、大类与阈值的定义表 |
| 模型版本 | model version | model id | 一份权重与其指标的集合 |
| 质量分 | quality score | sharpness score | 清晰度、亮度、色偏的加权结果 |
| 需重拍 | needs retake | rejected, failed | 质量分低于阈值，只入库不识别 |
| 阈值 | threshold | cutoff | 置信度或质量分的判定边界 |
| 同框对比 | side-by-side comparison | A/B test | 同一帧跑基线与改进模型并排显示 |

## 3. Status and metrics

| 中文 | English | 取值 |
|---|---|---|
| 待复核 | pending review | `review_status = 0` |
| 已确认 | confirmed | `review_status = 1` |
| 已修改 | modified | `review_status = 2` |
| 已驳回 | rejected | `review_status = 3` |
| 排队中 | queued | `task.status = 0` |
| 运行中 | running | `task.status = 1` |
| 已完成 | done | `task.status = 2` |
| 已失败 | failed | `task.status = 3` |
| 平均精度 | mAP | mAP@0.5 与 mAP@0.5:0.95 分别标注，不写“精度” |
| 召回率 | recall | 分类别统计，不用平均值掩盖 |
| 计数偏差 | counting deviation | 去重后计数与人工判读的差 |

## 4. Classes

| 类别码 | 中文 | English | 大类 |
|---|---|---|---|
| `holothurian` | 海参 | sea cucumber | 经济种 |
| `strongylocentrotus` | 海胆 | sea urchin | 经济种 |
| `chlamys` | 扇贝 | scallop | 经济种 |
| `asterias` | 海星 | starfish | 敌害种 |
