# weekly-report · 周报生成器（v0.3）

从工作痕迹到**一份带真实统计图表的双栏 PDF**：事实零编造、每条可回溯、一份内容多渲染、工具绝不代发。

由 `goushi-writing`（SHIT Journal 论文生成器）的流水线抽象而来。和它一样：**调用工具画真图 →
编译成品 PDF → 交付可复用的 `.tex` 工程**。反转的是证据观：那边用玩具模型造「示意数据」，
这边每个数字、每个像素都只能来自真实采集痕迹。

## 30 秒跑通（演示数据）

在本目录（`skills/weekly-report/`）下：

```bash
python scripts/collect.py --sample --out output/raw_items.json
python scripts/build_report.py --facts sample/facts.json --out output/ --strict --deterministic
```

第二条用「已整理好的示范事实清单」，一条命令跑完整条流水线：
lint + 逐条溯源 → matplotlib 真实统计出图 → 双通道 PDF → pymupdf 逐页自检 → 四视图 + manifest。

```
周报已生成 → output
  ★ 主产物 PDF  report.pdf       2 页 / 214674 字节 / 引擎 chrome-headless / 自检 PASS
    副本        工作周报_20261102.pdf
  图表          3 张真实统计（fig1.png、fig2.png、fig3.png）
  full       report.full.md       1275 字 / 14 条
  lead       report.lead.md        790 字 / 12 条
  exec       report.exec.md        285 字 / 5 条
  chat       report.chat.txt       282 字 / 5 条
  lint: PASS  error=0  warning=0  trace=ON (12 条原文 / 0 处不一致)
```

`sample/facts.json` 同目录有 `sample/raw_items.json`，所以**溯源校验会自动开启**，
`lint.json` / HTML 横幅 / `manifest.trace` 三处都会记录它通过。打开 `output/report.pdf`
看成品，打开 `output/report.html` 看 lint 横幅、四视图与来源清单。

想看完整链路（含「草稿 → 待补字段」这一步）：

```bash
python scripts/collect.py --sample --out output/raw_items.json
python scripts/scaffold_facts.py output/raw_items.json --out output/facts.draft.json
python scripts/lint.py output/facts.draft.json --raw output/raw_items.json
# 会报出 13 个待补字段（E004/E005/E007），这是设计意图；E015/E016 应为 0
# 人工/agent 补齐 headline、next_action、due 后（id 与 text 不许动）：
python scripts/build_report.py --facts output/facts.json --out output/ --strict
```

## 输出

| 文件 | 用途 |
|---|---|
| ★ `report.pdf` | **主产物**：IEEE 风格双栏中文，结论 / 五栏目 / 三张真图 / 量化表 / 来源清单 / 预览闸声明 |
| `工作周报_<起始日>.pdf` | 同一份 PDF 的带日期副本，便于自行转发 |
| `report.tex` | 可复用 LaTeX 工程，丢进 Overleaf（编译器选 XeLaTeX）即可重编 |
| `report.print.html` | Chrome 打印通道的等效双栏 HTML |
| `fig1.png` / `fig2.png` / `fig3.png` | 三张真实统计图表，300 dpi |
| `report.full.md` | 留存版：全量条目 + 每条来源角标 + 量化表 + 待确认 |
| `report.lead.md` | 组长版：一屏，全部栏目，带 owner / 下一步 / 截止 |
| `report.exec.md` | 上级版：结论 + 少量要点，隐藏内部代号 |
| `report.chat.txt` | 群消息：纯文本，无 Markdown，可直接粘贴 |
| `report.html` | 预览：PDF 卡片 + lint 横幅 + 四视图折叠 + 来源清单 |
| `lint.json` | 机检结果（error / warning / 统计），含 E015 / E016 |
| `manifest.json` | facts 哈希、视图字数、lint 摘要、`trace`、`figures`、`pdf.selfcheck`、`decision_gate` |

## PDF 双通道

`build_pdf.py` 用同一份 `facts.json` 同时渲染 `.tex` 与可打印双栏 HTML：

| 条件 | 走哪条 | 产物 |
|---|---|---|
| 本机有 XeLaTeX | `scripts/compile.sh` 编 IEEEtran（含字体降级 / 缺包自愈） | `report.pdf` |
| 无 XeLaTeX、有 Chrome / Edge | headless 打印 `report.print.html` | `report.pdf`（本机默认） |
| 两者都没有 | 保留 `.tex` / `.html`，如实报错 | `manifest.pdf.error`，`.tex` 可交 Overleaf |

`--pdf-engine auto|xelatex|chrome` 可强制后端。pymupdf 逐页自检会核对：页数、中文可提取、
结论、图表、来源清单、预览闸声明，结果写进 `manifest.pdf.selfcheck`（数据不足导致没有图时，
不因「缺图」误判失败）。**自检只管成品完整度，lint 才管事实正确性，两个都要看**；
lint 未通过时 PDF 首页会自动打红条，命令行也会追加提示，不会让不合格的成品看起来是干净的。
`--strict` 下若 PDF 没产出来，退出码为 3（但 `.tex` / `.html` 仍保留，可交 Overleaf）。

## 图表：只画真实统计

`make_figs.py` 从不造数，每张图都标 `data_source` 并写进 caption：

| 图 | 内容 | 数据来源 |
|---|---|---|
| `fig1.png` | 每日工作痕迹量 | `raw_items.json` 的 `date` 按天聚合 |
| `fig2.png` | 栏目构成 | `facts.json` 的 `section` 计数 |
| `fig3.png` | 在途事项截止日分布 | `facts.json` 的 `due × section` 堆叠 |

缺字段就跳过那张图（比如没有 `raw_items.json` 时不出 fig1），**绝不补造数字**。
中文由 `figure_helper.py` 自动挑选本机 CJK 字体（本机命中 `SimHei`），找不到就明确写在
`manifest.figures.font` 里，不静默画成方框。

## 接真实数据

```bash
python scripts/collect.py \
  --repo . \
  --notes ../my-notes/this-week.md \
  --tickets exports/tickets.json \
  --since 2026-11-02 --until 2026-11-08 \
  --author 张三 \
  --redact "客户A,内部代号X" \
  --out output/raw_items.json
```

草稿语法（一行一条，原文入库）：

```
无前缀 = 已完成    ~ = 进行中    ! = 风险    > = 下一步    @张三 = 负责人
```

工单导出是 JSON 数组，字段 `id / title / status / updated / url / owner`。
`status` 支持 `done|closed|doing|in_progress|blocked|todo` 及对应中文。

## 事实回溯（把「不许编」变成机检）

`raw_items.json` 是采集原文，`facts.json` 是整理结果。整理层**只能改格式**：

- `id` 原样沿用，**不许重命名**（它是溯源主键）；
- `text` 必须逐字对应采集原文；唯一允许的变换是把 `@owner` 标记提取成字段后从正文去掉并 trim；
- 新增的只能是 `section` / `owner` / `next_action` / `due` / `evidence` 这些字段。

```bash
python scripts/lint.py output/facts.json --raw output/raw_items.json
# E015 = text 与采集原文不一致    E016 = id 在 raw 中不存在
```

`build_report.py` 会自动探测 `facts.json` 同目录的 `raw_items.json` 并默认开启这道校验；
`--raw <path>` 可显式指定，`--no-trace` 可关闭（不建议，且**不影响**图表继续读真实 raw）。
正反例见 `references/report-guide.md` §2.5。

## 常用开关

| 开关 | 作用 |
|---|---|
| `--strict` | lint 有 error 时阻断出稿；PDF 没产出来也返回非零 |
| `--deterministic` | manifest 不写时间戳，文本产物与 manifest 可逐字节 diff |
| `--no-pdf` | 跳过出图与 PDF，只出四视图 + HTML（裸环境降级用，纯标准库） |
| `--pdf-engine` | `auto`（默认，XeLaTeX 优先）/ `xelatex` / `chrome` |
| `--raw` / `--no-trace` | 指定采集原文 / 关闭溯源比对 |

已验证：连跑两次 `--strict --deterministic`，四份视图、`report.html`、`lint.json`、
`manifest.json` 七个文件的 sha256 完全一致。

## `facts.json` 速查

```json
{
  "period": {"start": "2026-11-02", "end": "2026-11-08", "label": "..."},
  "author": "张三",
  "headline": "一句话结论，≤40 字，不引入无来源的数字",
  "items": [{
    "id": "n2", "section": "done|doing|risk|next|questions",
    "text": "采集原文，≤80 字，去掉 @owner 后逐字一致",
    "owner": "张三", "next_action": "接下来做什么", "due": "2026-11-10",
    "blocked": false,
    "evidence": "fact|inference|unconfirmed",
    "source": [{"type": "git|note|ticket", "ref": "a1b2c3d"}],
    "internal_refs": ["需要脱敏的内部代号"]
  }],
  "questions": ["待确认的问题"],
  "metrics": [{"name": "已完成", "value": 5, "unit": "条", "computed_by": "collect.py"}],
  "demo": false
}
```

`id` 必须来自 `raw_items.json`；`questions` 里的纯文本待确认项不参与溯源比对。

## 与原 skill 的七层对照

| 层 | 论文生成器 | 本骨架 |
|---|---|---|
| A 产物 | 4 页 IEEE 双栏 PDF + `.tex` 工程 | **2 页 IEEE 风格双栏 PDF + `.tex` / HTML 工程**（外加四视图文本） |
| B 范式 | `style-guide.md`：IEEE 骨架、三流派、配额、翻车清单 | `report-guide.md`：五栏目 DSL、配额、反模式、lint 对照（另留 `style-guide.md` 别名入口，不写第二套规则） |
| C 证据 | `model.py` 玩具模型 + 标「示意 / 数值模拟」 | `collect.py` 真实痕迹 + `source` 指针 + 三档 `evidence` + **E015/E016 逐条溯源** + **真图只从真实数据统计** |
| D 流程 | 步骤 0–5 + `make_figs.py` 出图 + `compile.sh` 缺包自愈 | 采集 → 机械整理 → lint → **真图 → 双通道 PDF → pymupdf 自检** → 多视图 → 预览闸 |
| E 入口 | 一句话选题 + 全部字段缺省 | 定时 / 多源，默认本周，零必填 |
| F 交付 | PDF + 可复用工程 + 邀请修改 | PDF + 副本 + 可复用工程 + 哈希 manifest + `trace` + `pdf.selfcheck` + `decision_gate`，**不发送** |
| G 语体 | 70/30 学术腔 × 网络梗，反差取乐 | 纯事实，`compact` 摘要、`hide_internal_refs` 脱敏，反差归零 |

## 环境依赖

- 文本四视图 + lint：**纯 Python 3.8+ 标准库**，`git` 可选。
- PDF 主产物：`matplotlib`（出真图）、`pymupdf`（逐页自检）、`XeLaTeX` 或 `Chrome / Edge`（出 PDF）。
- 三者不齐全时自动降级为纯文本并在 `manifest.pdf.error` 里如实写明，不静默失败。
- 无网络、无外部模型调用、不依赖原 `goushi-writing` 的任何文件。

## 边界（明确不做）

- 不接 Jira / 飞书 / 企业微信 / 邮件 API，不自动推送、不 @ 人。
- 不调外部模型：抽取与归栏目由人或 agent 在整理层做，渲染层是纯确定性代码。
- 不做日报（高频、信息量小，容易退化成 commit 翻译）；日报痕迹按天攒，周末汇总成周报。
- 不做自然语言润色、不改 `id`、不改写 `text`：改写措辞会让多份产物对不上，也会被 E015 拦下。
- 代码不能防止 `raw_items.json` 本身被伪造；**最后一道闸永远是人工预览确认**。
- 演示数据带 `demo: true` 水印，**禁止外发**。

## 独立成仓

本目录自包含，直接复制出去就是一个独立项目；`install.sh`（仓库根）会自动把它
识别为第二个 skill（扫描 `skills/*/SKILL.md`）。
