# Interface copy review

<!-- allow-chinese: reviews the interface copy; the Chinese strings are the material under review -->

> Chinese version: [copy-review-zh.md](copy-review-zh.md). This file is the source of truth.
> Owner: @FrozenYty · Revisit when: the interface copy is rewritten, or the page set changes

Findings and suggestions for the copy across the thirteen pages. **This is a review, not a change
log**: the edits below have not been applied, except where noted in §6.

## 1. Scope and method

Every string a user can see was extracted from the templates and the scripts that build them, then
checked twice:

1. **Mechanically** — doubled characters, half-width punctuation inside Chinese sentences, missing
   spaces around Latin text, stray exclamation marks.
2. **By judgement** — parallelism between sibling labels, rhythm in a column, whether a word matches
   the glossary, whether a phrase is developer shorthand.

The second pass is what produced the findings; the first pass found nothing.

## 2. What was already clean

| Check | Result |
|---|---|
| Doubled characters (的的, 了了) | 0 |
| Half-width punctuation inside Chinese | 0 |
| Latin and Chinese jammed together without a space | 0 |
| Exclamation marks | 0 |
| `%` spacing | consistent throughout |
| Terminology | 采集 48 uses, 识别 54, 检测 only where the verb is literal (detecting a camera) |

The copy is better than it reads as. What follows is about rhythm, not correctness.

## 3. Layout and parallelism

**Sidebar group names.** Three groups are two characters and three are five:

```
概览(2) · 采集(2) · 识别(2) · 复核与回流(5) · 统计与报告(5) · 模型与系统(5)
```

A sidebar is a vertical column of text; unequal lengths leave the right edge ragged on every page.
Suggested: 概览 · 采集 · 识别 · 复核 · 统计 · 模型 — six groups, two characters each. The dropped
words (回流, 报告, 系统) are carried by the items underneath.

**Statistics card subtitles.** The four cards measure different things, but the subtitles do not say
so consistently:

| Card | Subtitle | Length |
|---|---|---|
| 物种组成 | 近 7 日目标框数 | 7 |
| 采集量趋势 | 每日收帧 | 4 |
| 质量拦截率 | 低质量帧占比 | 6 |
| 复核修正分布 | 人工改动汇总 | 6 |

Three problems at once: the lengths are 4/6/7, the structures differ (one gives a time window, one a
frequency, two give definitions), and 收帧 is internal shorthand while the others are ordinary words.

Suggested: 目标框数 · 采集帧数 · 重拍帧占比 · 改动次数. The first two clarify a real ambiguity — one
counts boxes and the other counts frames, and today the reader cannot tell.

**Dashboard KPI labels.** 今日采集(4) · 待复核(3) · 质量拦截率(5) · 在线模型(4). The first three are
"today's numbers" and the fourth is "current state", but nothing in the labels marks the split. Also a
precision issue: 质量拦截率 does not say *today*, though the figure is today's.

Suggested: 今日采集 · 今日待复核 · 今日拦截率 · 当前模型 — the first three share a prefix, the fourth
declares itself different, and the semantic grouping matches the visual one.

## 4. Units, status words and form labels

**The only Latin unit in the interface.** `识别间隔（ms）` is the sole Latin unit; every other unit is
Chinese (帧, 秒, 像素, %). Suggested: `识别间隔（毫秒）`.

**Status words already follow a pattern** — 待 X for waiting, 已 X for settled:

```
待复核 / 已确认 / 已修改 / 已驳回
排队中 / 运行中 / 已完成 / 已失败
```

The hard-example source chips break it with a passive form: 低置信 / **被修正** / 跨模型不一致. The
second should be 已修正. The three chips also run 3/4/6 characters in a single row, which makes three
buttons of very different widths; 低置信 / 已修正 / 模型分歧 even them out, at the cost of the word
"cross-model". That trade is worth naming rather than hiding.

**One label is missing a word.** The parameter list reads 默认置信度阈值 next to 质量分阈值 — both are
defaults, only one says so. Suggested: 默认质量分阈值.

**Sentence endings.** Long hints mostly end with a full stop; the one complete sentence that does not
is 超出范围的项会标红并拒绝保存. Rule worth adopting: full sentences take a full stop, phrases do not.

## 5. What not to change

Parallelism is not worth paying for with meaning:

| Item | Why it stays |
|---|---|
| Page titles 工作台 / 难例池 (3 characters) | These names come from SRS §5.2; changing them breaks the trace to the specification |
| Table headers 创建时间 / 登记时间 (4 characters) | Four characters is normal in a table; shortening loses information |
| `mAP@0.5` beside 平均召回 | Metric names keep their English form; translating them makes them harder to recognise, not easier |
| The five parameter labels being unequal | Form labels stack vertically, each above its own input, so their right edges never align anyway. Forcing equal length would delete 中间文件 and 批量识别, which say what the parameter applies to |

One earlier suggestion is withdrawn: renaming 检测框 to 目标框. The glossary already fixes 检测框, and a
review that contradicts the glossary would start exactly the drift the glossary exists to prevent.

## 6. Status

Applied before this review was written, in the copy pass of 2026-11-06: the detection box / target box
wording, the out-of-range hint, the seed hint, the hard-example caption, and the capture button.

Still open, and listed by priority: the sidebar group names, the statistics subtitles, and the
dashboard KPI prefixes. The remaining items are polish, and belong with the design pass that also
removes the `P-xx` eyebrow from the page headers — that marker stays until then because it is the only
anchor tying a screen to its row in SRS §5.2.
