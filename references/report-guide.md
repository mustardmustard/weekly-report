# 周报文体解剖 (Report Guide)

> 由 `goushi-writing` / SHIT Journal 改造而来。**相同的是骨架，相反的是证据观与语体。**
> 本工具不「写文章」，只做一件事：把有来源的工作痕迹，整理成一屏能读完、每条有下落的事实清单。

## 0. 与伪学术论文的根本差异（先看这张表）

| 维度 | 伪学术论文 | 工作周报 |
|---|---|---|
| 数字来源 | 玩具模型，标「示意 / 数值模拟」即可 | 只能来自真实痕迹；无来源的数字一律不写 |
| 允许虚构 | 是，且是笑点来源 | **零容忍**，编造「已完成 X」是事故 |
| 篇幅目标 | 靠加料扩到 3–4 页 | 压缩到一屏；删形容词比加内容更重要 |
| 语体 | 庄重形式 × 荒诞对象（70/30 梗） | 纯事实、无梗、无反差、无自创术语 |
| 解决方案节 | 荒诞但自洽的产品机制 | 每条必须有 owner + next_action + due |
| 图表 | `make_figs.py` 用玩具模型造示意曲线 | `make_figs.py` 只统计真实痕迹，缺字段就跳过那张图 |
| 出厂动作 | 全自动编译完直接交付 | 同样编译出成品 PDF，但生成后**必须人工预览确认**，工具永不发送 |
| 免责声明 | 「纯属戏仿，请勿模仿」 | 「来源清单 + 待确认项」，不是免责而是溯源 |

一句话：**原 skill 的内核是「让编造看起来可信」，本工具的内核是「让可信的东西看起来清楚」。**

## 1. 价值公式

一篇合格的周报 = **一句结论先行** + **每条事实可追溯** + **每件在途的事有下落**。

读者是上级，最怕「看起来很忙但没结论」。所以顺序永远是：结论 → 已完成 → 进行中 → 风险阻塞 → 下一步 → 附来源。

## 2. 事实红线（本工具的心脏）

`facts.json` 是**唯一真源**。渲染器只做筛选、归组、排序、格式化，**不生成任何新事实**。

每条 item 必须带 `evidence`，三档：

| evidence | 含义 | 要求 |
|---|---|---|
| `fact` | 有来源、可直接复述 | **必须有 `source`**，否则 lint 报错 |
| `inference` | 基于 fact 的推断 | 必须有 source，渲染时自动加「推断：」前缀 |
| `unconfirmed` | 信息不全 / 待确认 | 渲染时自动加 `[待确认]`，不写进结论 |

硬规则：

- 采集层（`collect.py`）**零改写**：git subject、草稿原文、工单标题原样入库。
- 整理层（人或 agent）**只能改格式**：归栏目、补 owner、补 next_action、标 evidence；**不得新增 `raw_items.json` 里没有的事实**（操作细则见 §2.5）。
- 缺信息填「待确认」，**绝不用「顺利完成」「基本完成」「推进中」这类词把空白糊过去**。
- 数字（`metrics`）必须由 `collect.py` 从痕迹算出，正文引用同一个值，杜绝「正文 7 个、表格 8 个」。
- **PDF 里的图表同样受事实红线约束**：只允许对 `raw_items.json` / `facts.json` 做计数、分组、
  排序、画柱；不许插值、不许补零、不许「为了让图好看」改刻度或造示例点。细则见 §4.5。
- 演示数据必须 `demo: true`，所有视图与 PDF 自动打「演示数据」水印。

## 2.5 整理层操作细则（唯一允许改文本的地方）

原则一句话：**改完之后每个 `text` 都必须能在 `raw_items.json` 里逐字找到对应；
新增的只能是 `section` / `owner` / `next_action` / `due` / `evidence` 这些字段。**
`id` 必须原样沿用，不许重命名——它是溯源校验的主键。

唯一允许的文本变换：把草稿里的 `@owner` 标记提取成字段后从正文去掉，并 trim 空白。

```
raw_items.json（采集原文）
  {"id":"n2", "text":"跨组鉴权 SDK 联调中 @张三", "kind":"doing",
   "source":[{"type":"note","ref":"notes.md:L3"}]}

允许（只改格式）
  {"id":"n2", "section":"doing", "text":"跨组鉴权 SDK 联调中",
   "owner":"张三", "next_action":"拿到联调环境账号后完成首轮联调",
   "due":"2026-11-11", "evidence":"fact",
   "source":[{"type":"note","ref":"notes.md:L3"}]}

禁止（新增事实、改变语气或断链）
  text: "顺利推进跨组鉴权 SDK 联调，整体进展良好"  ← 无来源形容词 + 完成态
  text: "跨组鉴权 SDK 联调中，预计下周可完成"      ← 未经确认的时间预测
  text: "鉴权 SDK 联调"                           ← 擅自删字，与原文不等
  id:   "n2" → "doing-1"                         ← 重命名，溯源断链
```

**机器判据**：`lint.py --raw <raw_items.json>` 逐条比对，命中即报 `E015`
（text 与采集原文不一致）或 `E016`（id 在 raw 中不存在）。
`build_report.py` 会自动探测 `facts.json` 同目录的 `raw_items.json` 并默认开启这道校验；
确实不需要时用 `--no-trace` 关闭，或用 `--raw` 显式指定另一份采集结果。
`lint.json` / HTML 横幅 / `manifest.trace` 三处都会记录是否做了溯源。

## 3. 章节 DSL（5 栏目固定）

```
headline      一句话结论（≤40 字，只复述 facts，不引入新数字）
done          已完成      —— 必须有来源
doing         进行中      —— 必须有 owner + next_action
risk          风险 / 阻塞 —— 必须有 owner + next_action + due；无风险也要显式写「本周无阻塞」
next          下一步      —— 必须有 owner + due
questions     待确认项    —— 所有 unconfirmed 汇总于此
metrics       量化指标    —— 由 collect.py 计算，带 computed_by 与来源
```

「解决方案必做」这条从原 skill 迁移过来，改成：**`doing` / `risk` / `next` 三条栏目里每一条，都必须能回答「谁、接下来做什么、什么时候」。** 没有下落的条目不是进展，是噪音。

## 4. 硬配额

| 视图 | 目标 | 上限 |
|---|---|---|
| `full` 留存版 | 全量 + 来源 | 不限，但每条 ≤80 字 |
| `lead` 组长版 | 一屏 | ≤800 字，量化指标用单行 |
| `exec` 上级版 | 三眼看完 | ≤300 字，`compact` |
| `chat` 群消息 | 可直接粘贴 | ≤300 字，纯文本无 Markdown，`compact` |

`compact` 视图只保留条目正文与证据标记，省掉 owner / next_action / due 这些细节，并补一句「完整版见留存文档」——细节不丢，只是不塞进摘要。

超配额时 lint 给 warning，**不强行截断正文**（截断会丢事实，比超字数更糟）。截断只允许发生在「视图按条数取前 N 条」，并显式写「另有 N 条见留存版」。

## 4.5 图表与 PDF 产物（A 层 / F 层的机检落点）

这一节是「规范即测试」在产物层的落点：每条规则都有代码位置，不是口号。

**主产物是 PDF，不是文本。** 和 `goushi-writing` 一致，交付物是编译好的双栏 PDF +
可复用的 `.tex` 工程；四份文本视图降级为同源辅助产物。

**真图规则（对应 `scripts/make_figs.py`）**

| 规则 | 机检落点 |
|---|---|
| 每张图的数据只能来自 `raw_items.json` 或 `facts.json` | 三张图分别只读 `date`、`section`、`due × section`，代码里没有任何常量数据数组 |
| caption 必须写明 `data_source` | `figure["data_source"]` → `caption_full`，同时写进 `manifest.figures.files[]` |
| 缺字段就跳过，绝不补数 | 每个 builder 返回 `None` 即不进 `figures`，`manifest.figures.count` 如实记 |
| 中文字体必须可用 | `figure_helper.setup_cjk()` 返回字体名写入 `manifest.figures.font`，找不到时明确写降级说明 |
| 禁止出现「示意性推演」「数值模拟」字样 | 与论文生成器的 `model.py` 相反，本 skill 任何产物都不许用这两句话给数字开脱 |

三张固定图：`fig1` 每日工作痕迹量、`fig2` 栏目构成、`fig3` 在途事项截止日分布。

**PDF 规则（对应 `scripts/build_pdf.py` / `compile.sh`）**

| 规则 | 机检落点 |
|---|---|
| 一份 facts 同时渲染 `.tex` 与可打印双栏 HTML | `build_tex()` / `build_html()` 共用同一组 `section_pool()` |
| XeLaTeX 优先，缺则 Chrome / Edge headless 降级 | `build()` 的 `engine` 分支，`manifest.pdf.engine` 记录实际走的通道 |
| 两个后端都没有时如实失败 | 保留 `.tex` / `.html`，错误写进 `manifest.pdf.error`，`.tex` 可交 Overleaf |
| 逐页自检，不能只看「文件生成了」 | `selfcheck()` 用 pymupdf 查页数、中文、结论、图表、来源清单、预览闸声明 → `manifest.pdf.selfcheck.pass` |
| lint 失败不许「看起来是干净的」 | `lint_warning()` 在 `.tex` 与 `.html` 顶部打红条 |
| PDF 内必须带来源清单与预览闸声明 | PDF 末尾两节 + `selfcheck.has_sources` / `has_gate_note` |
| 图表、PDF、自检都要可核对 | `manifest.figures` / `manifest.pdf` / `manifest.primary_output` 三处落盘 |

**降级规则**：第三方依赖（matplotlib / pymupdf / 浏览器 / XeLaTeX）不齐全时，
`--no-pdf` 或自动降级只影响 PDF，四视图与 lint 照常产出，失败原因必须进 manifest，不许静默吞掉。

**自检边界**：`selfcheck.pass` 只回答「PDF 该有的东西齐不齐」，不回答「事实对不对」；
确实没有可绘制数据时 `expect_figures=false`，不因缺图误判失败。事实正确性由 `lint.pass`
负责，两者在 `manifest.json` 里并列，缺一不可。

## 5. 反模式清单（机器可检）

- ❌ `fact` 条目没有 `source`
- ❌ `doing` / `risk` / `next` 缺 `owner` 或 `next_action`
- ❌ 无主语句：「已推进」「已完成对接」「持续优化」
- ❌ 形容词糊墙：顺利完成 / 大力推进 / 显著提升 / 基本完成 / 有序开展 / 积极跟进
- ❌ 结论里出现 facts 里没有的数字
- ❌ 把 `unconfirmed` 写成确定语气
- ❌ 流水账：把 20 条 commit 逐条翻译，没有归组也没有结论
- ❌ 给上级 / 群消息的版本里出现内部代号、客户名、同事全名（见 §7）
- ❌ 工具自动发送、自动 @ 人、自动改工单状态
- ❌ 为了让图好看补造数据点、插值、补零，或用「示意性推演 / 数值模拟」给数字开脱（见 §4.5）
- ❌ 只交几份文本、把 PDF 当成「可选附加」——主产物就是编译好的 PDF
- ❌ PDF 里没有来源清单或预览闸声明，或 lint 失败却交出不带警示条的干净成品

## 6. 多受众视图（复用「一份内容源 + 多渲染器」）

同一份 `facts.json` 渲染四份，差异只在**取舍与语体**，不在事实：

| 视图 | 给谁 | 保留 | 隐藏 |
|---|---|---|---|
| `full` | 自己留存 / 复盘 | 全量条目、来源、metrics、待确认 | — |
| `lead` | 直属组长 | 全部栏目、每栏目前 N 条 | 来源角标（HTML 里仍可查） |
| `exec` | 上级 | 结论 + 3 条 done + 2 条 risk + 3 条 next | 细节、来源、进行中、内部代号 |
| `chat` | 群消息 | 结论 + 已完成 + 阻塞 + 下一步 | Markdown 语法、来源、内部代号 |

**不许为不同受众改写同一条事实的措辞** —— 这会让两份报告对不上。要改就改 `facts.json`，重跑，四份一起变。

PDF 是这套「一份内容源 + 多渲染器」里的第 5 个渲染器，且是主产物：它取**全量**事实
（不按 `max_items` 截断）、带三张真图、带来源清单。四份文本做的是取舍，PDF 做的是完整留存。

## 7. 隐私与发送护栏

- 采集与渲染**全部本地**，不调外部模型、不上传任何工作痕迹。
- `exec` / `chat` 视图默认隐藏 `internal_refs`（内部代号、客户名、同事全名）；需要更严格的脱敏时在采集层用 `--redact`。
- 工具**只写文件**。`manifest.json` 固定写一句：`本工具不发送任何内容；生成后需人工预览确认再自行转发。`；PDF 末尾也印同一句，并经 `selfcheck.has_gate_note` 核对。
- 确认动作属于人：扫一眼 PDF 结论与图表、核一遍风险条目、再自行转发带日期副本。
- **代码防不住 `raw_items.json` 本身被伪造**：溯源只能保证「整理层没改字」，保不了「采集层是真」。人工预览是最后一道闸，不是可省略的礼貌步骤。

## 8. lint 规则对照

| 规则 | 级别 | 对应 |
|---|---|---|
| `fact` / `inference` 必须有 source | error | §2 |
| 三栏目必须有 owner / next_action | error | §3 |
| `done` 至少 1 条、`risk` 必须显式 | error | §3 |
| 单条 ≤80 字 | warning | §4 |
| 视图字数上限 | warning | §4 |
| 结论 ≤40 字且不含新数字 | error | §5 |
| 禁用词命中 | warning | §5 |
| id 唯一、due 日期格式 | error | schema |
| 逐条可回溯：text / id 对得上 raw（E015 / E016） | error | §2.5 |
| PDF 逐页自检：中文 / 结论 / 图表 / 来源 / 预览闸 | 产物自检 | §4.5 |
| 图表 caption 带 `data_source`、缺字段跳过 | 产物自检 | §4.5 |
| PDF 后端与失败原因落盘 | 产物自检 | §4.5 |

**默认行为**：lint 不通过也生成，但结果写进 `lint.json`、`report.html` 顶部横幅、
`manifest.json`，并在 PDF 首页打红条；`--strict` 才阻断出稿。先让人看见问题，
比直接失败更适合每天要用的工具。

溯源校验是**默认开启**的（`build_report.py` 自动找同目录的 `raw_items.json`），
因为它是整套红线的最后一道闸；`manifest.trace` 记录是否执行过。
PDF 自检结果在 `manifest.pdf.selfcheck`，与 lint 是两件事：**lint 管事实，selfcheck 管成品完整度**，
两个都要看。
