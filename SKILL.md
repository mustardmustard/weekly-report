---
name: weekly-report
description: >-
  工作周报生成器：从本地工作痕迹（git 提交、随手草稿、工单导出）聚合出带来源的事实清单，
  用 matplotlib 从真实数据画统计图，渲染成一份 IEEE 双栏中文 PDF（主产物，XeLaTeX 或
  Chrome/Edge headless），并同时输出留存版 / 组长版 / 上级版 / 群消息四份同源文本、
  HTML 预览、lint 结果与 manifest。事实零编造、逐条可回溯、工具不发送、生成后需人工确认。
  当用户提到「写周报」「日报」「本周总结」「工作汇报」「周报生成」「把这周做的事整理一下」
  「帮我汇总本周进展」「周报模板」，或给出一个工作周期并想要结构化汇报时使用。不要把它当作
  文案润色任务，更不要替用户补写没有来源的进展、数字或结论。
---

# 周报生成器（weekly-report）

把一周的工作痕迹，整理成**一份带真实统计图表的双栏 PDF**，外加一屏能读完、
每条可回查、每件在途的事有下落的四份文本视图。

由 `goushi-writing` 的流水线抽象而来，保留了「结构化章节 + 硬配额 + 数字单一真源 +
真图 + 一份内容多渲染 + PDF 编译」，但**证据观与语体完全反转**：原来「玩具模型造数、
标示意即可」，这里每个数字、每个像素都只能来自采集到的真实痕迹。

## 交付目标

和 `goushi-writing` 一样，**最终交付的是一份成品 PDF**，不是几份待拼的文本：

| | 文件 | 说明 |
|---|---|---|
| ★ 主产物 | `report.pdf` + `工作周报_<起始日>.pdf` | IEEE 风格双栏中文，首页内嵌三张真图；PDF 内带结论、量化表、来源清单、预览闸声明 |
| 可复用工程 | `report.tex` / `report.print.html` / `fig*.png` | `.tex` 可丢 Overleaf（编译器选 XeLaTeX）；`.html` 是 Chrome 打印通道的等效双栏 |
| 辅助视图 | `report.full.md` / `lead.md` / `exec.md` / `chat.txt` | 四份受众视图，与 PDF 同源 |
| 机检与预览 | `report.html` / `lint.json` / `manifest.json` | lint 横幅、溯源结果、PDF 自检、图表清单 |

全部只写本地文件。预览确认属于人，工具不发送、不 @ 人、不改工单状态。

## 事实红线 ⚠️（动手前先读）

`facts.json` 是**唯一真源**。渲染器只做筛选 / 归组 / 排序 / 格式化，不生成新事实。

- 采集层 `collect.py` **零改写**：git subject、草稿原文、工单标题原样入库，每条带 `source`。
- 整理层**只能改格式**：归栏目、把草稿里的 `@owner` 提取成字段、补 `next_action` / `due` /
  `evidence`、写一句话结论。**不得新增 `raw_items.json` 里没有的事实或数字。**
- **`id` 原样沿用、`text` 逐字可回溯**：唯一允许的文本变换是去掉 `@owner` 标记并 trim；
  不许改写措辞、删字、加形容词、加预测，也不许重命名 id（细则见 report-guide §2.5）。
  `lint.py --raw` 会逐条比对，命中即报 `E015` / `E016`。
- 缺信息就留空并标 `unconfirmed`，由 lint 报出来让人补；**绝不用「顺利完成」「基本完成」
  「推进中」把空白糊过去**。
- `evidence` 三档：`fact`（有来源）/ `inference`（有来源且渲染自动加「推断：」）/
  `unconfirmed`（渲染自动加 `[待确认]`）。`fact` 与 `inference` 无来源即 lint 报错。
- 数字只从 `metrics`（由采集器算出）来，正文引用同一份，避免两份报告对不上。
- 演示数据 `demo: true` 会在所有视图打水印，禁止外发。

## 输入规范

**零必填。** 不给参数就默认本周一到本周日，并尝试读取当前工作区的 git 与随手草稿。
只有「一个数据源都没有」时才问一句：这周的痕迹在哪（仓库路径 / 草稿文件 / 工单导出）。
不要为了凑字段中断流程，更不要向用户索要「本周做了什么」的长描述。

| 字段 | 必要性 | 缺省 |
|---|---|---|
| 周期 | 可选 | 本周一 ~ 本周日 |
| 数据来源 | 可选（但至少要有一个） | cwd 的 git log + `sample/` 演示数据兜底 |
| 作者 / 团队 | 可选 | 留空或取 git config |
| 脱敏词 | 可选 | 无，`exec` / `chat` 视图默认隐藏 `internal_refs` |

## 工作流程

### 步骤 0 · 先读透文体
**动手前完整读 [references/report-guide.md](references/report-guide.md)**：与伪学术论文的差异表、
事实红线、**§2.5 整理层操作细则**、五栏目 DSL、硬配额、反模式清单、多视图取舍、
隐私护栏、lint 规则。`references/style-guide.md` 只是别名入口，内容不在这里。

### 步骤 1 · 采集（确定性，零改写）
```bash
python "<skill>/scripts/collect.py" --repo <仓库> --notes <草稿.md> \
       --tickets <工单.json> --out "<out>/raw_items.json"
```
没接真实来源时，用 `--sample` 跑通链路（会强制 `demo: true`）。
`--since / --until` 可指定周期；`--redact 词1,词2` 是唯一允许的文本变换，会被记录。

### 步骤 2 · 整理（只能改格式）
```bash
python "<skill>/scripts/scaffold_facts.py" "<out>/raw_items.json" \
       --out "<out>/facts.json"
```
脚本机械搬运：归栏目、保留来源、标 `evidence`，`headline` / `next_action` / `due` 一律留空。
然后由人或 agent 补齐这些内容——**只补格式字段，不补事实**；草稿里的 `@张三` 可提取为
`owner` 并从正文去掉。**`id` 必须原样沿用**（它是溯源主键），整理完每个 `text` 都必须
仍能在 `raw_items.json` 里逐字找到对应。正反例见 report-guide §2.5。

### 步骤 3 · lint
```bash
python "<skill>/scripts/lint.py" "<out>/facts.json" --raw "<out>/raw_items.json"
```
逐条核对 `error`：缺来源、缺 owner、缺 next_action、缺 due、结论超长、结论出现无来源的数字、
id 重复、日期格式，以及 **`E015` text 与采集原文不一致 / `E016` id 在 raw 中不存在**。
全部清零再出稿。

### 步骤 4 · 渲染（一条命令同时出真图 + PDF + 四视图）
```bash
python "<skill>/scripts/build_report.py" --facts "<out>/facts.json" \
       --views "<skill>/assets/views.json" --out "<out>" --strict --deterministic
```
这一步内部按 `goushi-writing` 的流水线顺序跑完：

1. **lint + 逐条溯源**（默认开）→ `lint.json`。自动探测 `facts.json` 同目录的
   `raw_items.json`；结果进 HTML 横幅与 `manifest.trace`。
2. **步骤 3.5 生成真图**：`make_figs.py` 只从真实数据统计——`fig1` 每日工作痕迹量
   （`raw.items[].date`）、`fig2` 栏目构成（`facts.items[].section`）、`fig3` 在途事项
   截止日分布（`due × section`）。**缺字段就跳过那张图，绝不补造数字**，每张 caption
   都写明 `data_source`；中文字体由 `figure_helper.py` 兜底。
3. **步骤 3.6 双通道出 PDF**：`build_pdf.py` 用同一份 facts 同时渲染 `report.tex` 与
   `report.print.html`。有 XeLaTeX 就走 `scripts/compile.sh` 编 IEEEtran 双栏；没有则自动
   降级用 Chrome / Edge headless 打印等效双栏 HTML（本机默认路径）。两个都没有时保留
   `.tex` 与 `.html`，把失败原因写进 `manifest.pdf.error`，`.tex` 可交 Overleaf 编译。
4. **逐页自检**：pymupdf 检查页数、中文、结论、图表、来源清单、预览闸声明，结果进
   `manifest.pdf.selfcheck`；另存一份 `工作周报_<起始日>.pdf` 便于转发。
5. **四视图 + HTML 预览 + manifest**：`figures` / `pdf` / `selfcheck` 全部写进 manifest。

常用开关：`--no-pdf` 只出文本四视图（第三方依赖缺失时降级）、
`--pdf-engine auto|xelatex|chrome` 指定后端、`--raw <path>` 指定采集原文、
`--no-trace` 关溯源（不建议，但**不影响**图表继续读真实 raw）。
`--strict` 让 lint 阻断出稿、并在 PDF 未产出时返回非零；`--deterministic` 便于 diff。

PDF 与四份视图来自同一份 facts，要改就改 facts 再重跑，**不要单独改某一视图或 PDF 的措辞**。
lint 未通过时 PDF 首页会自动打红条，成品不会「看起来是干净的」。

### 步骤 5 · 预览确认后交付
把 **`report.pdf` 打开给用户看**，同时给 `report.html`（lint 横幅 + 来源清单）、四份文本路径、
`lint.json` 与 `manifest.pdf.selfcheck` 摘要。交付话术讲「结论是什么、有几个风险、
哪几条待确认、PDF 几页 / 几张真图 / 自检是否通过」，主动邀请修改（「改结论 / 补来源 /
调群消息长度都行，改完我重跑」）。**到此为止，不发送。**

## 环境依赖

- Python 3.8+；`git` 命令行可选（没有就只用草稿 / 工单来源）。
- 文本四视图 + lint **只用标准库**，`--no-pdf` 可在裸环境跑通。
- PDF 主产物需要：`matplotlib`（画真图）、`pymupdf`（逐页自检），以及
  `XeLaTeX` 或 `Chrome / Edge` 之一（出 PDF）。三者都缺时自动降级为纯文本并如实报错。
- 无网络、无外部模型调用、不依赖原 `goushi-writing` 的任何文件。

## 分寸与隐私

- 采集与渲染全在本地，工作痕迹不上传、不写进日志。
- `exec` / `chat` 视图默认把 `internal_refs` 里的内部代号、客户名替换成「[内部信息]」。
- 涉及同事姓名、客户、未公开项目时，先问一句能不能出现在对外版本里再定 `hide_internal_refs`。
- `manifest.json` 固定带一句 `decision_gate`：本工具不发送任何内容；生成后需人工预览确认再自行转发。

## 目录结构

```
weekly-report/
├── SKILL.md                     本文件：工作流 + 输入规范 + 红线
├── references/
│   ├── report-guide.md          唯一真源：事实红线 / §2.5 / DSL / 配额 / 反模式 / lint
│   └── style-guide.md           兼容别名（只指向 report-guide.md，不写第二套规则）
├── assets/
│   ├── views.json               四视图配置（栏目、条数、字数、脱敏、compact）
│   └── template/Weekly-Template.tex   IEEEtran 中文双栏导言区（XeLaTeX / Overleaf）
├── scripts/
│   ├── collect.py               确定性采集 → raw_items.json
│   ├── scaffold_facts.py        机械整理 → facts.json 草稿
│   ├── lint.py                  可机检规则（含 E015 / E016 逐条溯源）
│   ├── figure_helper.py         matplotlib 中文 CJK 字体助手
│   ├── make_figs.py             真实统计出图 → fig1/2/3.png（不造数）
│   ├── build_pdf.py             .tex + 可打印双栏 HTML + PDF + pymupdf 自检
│   ├── compile.sh               XeLaTeX 编译 / 字体降级 / 缺包自愈
│   └── build_report.py          主入口：默认一次出 PDF + 真图 + 四视图 + manifest
└── sample/                      演示数据（demo=true，非真实工作痕迹）
```
