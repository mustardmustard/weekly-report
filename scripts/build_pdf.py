#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_pdf.py — 一份 facts.json 同时渲染 .tex 与可打印双栏 HTML，产出 PDF。

走的是 goushi-writing 在本机实际跑通的双通道：
  XeLaTeX 可用  → scripts/compile.sh 编译 IEEEtran 双栏（正统）
  否则          → Chrome / Edge headless 打印等效双栏 HTML → PDF（本机默认）
  两者都不可用  → 保留 .tex / .html，明确报错，.tex 可丢进 Overleaf

图表由 make_figs.py 用真实统计生成，这里只负责引用，不生成任何数字。
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEMPLATE = ROOT / "assets" / "template" / "Weekly-Template.tex"
GATE_NOTE = "本工具不发送任何内容；生成后需人工预览确认再自行转发。"

SECTION_LABELS = [
    ("done", "已完成 / DONE", "本周无已完成条目"),
    ("doing", "进行中 / IN PROGRESS", "本周无在途事项"),
    ("risk", "风险 / 阻塞 / RISKS", "本周无阻塞"),
    ("next", "下一步 / NEXT", "下周计划待补充"),
    ("questions", "待确认 / OPEN QUESTIONS", "无待确认项"),
]
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]

CSS = r"""
@page { size: Letter; margin: 13mm 14mm 14mm 14mm; }
* { box-sizing: border-box; }
body { margin:0; padding:0; color:#151515; font-size:9pt; line-height:1.42;
       text-align:justify;
       font-family:"SimSun","Songti SC","Noto Serif CJK SC","Microsoft YaHei",serif; }
.running-head { display:flex; justify-content:space-between; align-items:center;
       padding:0 2mm 1mm 2mm; margin-bottom:1.5mm; border-bottom:0.4pt solid #bbb;
       font-size:7.6pt; color:#555; letter-spacing:0.2pt; }
.masthead { padding-bottom:1.5mm; border-bottom:0.6pt solid #999; margin-bottom:2mm; }
.masthead h1 { font-size:14pt; line-height:1.3; text-align:center;
       margin:0 0 1.8mm 0; font-weight:bold; }
.meta-line { text-align:center; font-size:8.2pt; color:#444; margin:0 0 1.6mm; }
.conclusion { font-size:9.2pt; border-left:2.5pt solid #534ab7; padding-left:3mm;
       margin:1.5mm 0; line-height:1.45; }
.conclusion b, .metrics b { color:#3c3489; }
.metrics { font-size:8.2pt; color:#333; margin-top:1.4mm; }
.demo { font-size:8pt; color:#854f0b; background:#faeeda; padding:1mm 2mm;
       margin-top:1.5mm; border:0.4pt solid #ef9f27; }
.lintbad { font-size:8pt; color:#8b2626; background:#fceaea; padding:1mm 2mm;
       margin-top:1.5mm; border:0.4pt solid #e6a9a9; }
.paper { column-count:2; column-gap:6mm; }
h2 { font-size:9.4pt; font-weight:bold; margin:2.6mm 0 1.1mm 0;
     padding-top:0.9mm; border-top:0.5pt solid #bbb;
     break-after:avoid; page-break-after:avoid; }
ul.items { margin:0.6mm 0 1.4mm 0; padding-left:4mm; }
ul.items li { margin-bottom:0.9mm; font-size:8.6pt; line-height:1.4;
              break-inside:avoid; }
.owner { color:#555; font-size:8pt; }
.flag { color:#8b2626; font-weight:bold; }
.infer { color:#3c3489; }
.unconf { color:#854f0b; }
.empty { color:#777; font-size:8.3pt; font-style:italic; }
figure { margin:1.8mm 0 2.4mm 0; break-inside:avoid; page-break-inside:avoid; }
figure img { width:100%; height:auto; display:block; margin:0 auto; }
figcaption { font-size:7.4pt; color:#333; margin-top:1mm; line-height:1.35;
             text-align:left; }
table { width:100%; border-collapse:collapse; font-size:7.7pt;
        break-inside:avoid; page-break-inside:avoid; margin:1mm 0 2mm 0; }
th, td { padding:0.8mm 1mm; text-align:left; border-bottom:0.4pt solid #ddd;
         vertical-align:top; }
th { border-bottom:0.8pt solid #444; font-weight:bold; }
.sources { font-size:7.2pt; line-height:1.35; }
.footer { font-size:7.5pt; color:#555; border-top:0.5pt solid #bbb;
          margin-top:2mm; padding-top:1.2mm; }
@media print { body { -webkit-print-color-adjust:exact; print-color-adjust:exact; } }
"""


def esc(s):
    return html.escape(str(s), quote=False)


def esc_tex(s):
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("_", r"\_"), ("#", r"\#"), ("$", r"\$"),
                 ("^", r"\textasciicircum{}"), ("~", r"\textasciitilde{}"),
                 ("{", r"\{"), ("}", r"\}")):
        s = s.replace(a, b)
    return s


def item_text(it):
    text = str(it.get("text") or "").strip()
    ev = it.get("evidence")
    if ev == "inference":
        text = "推断：" + text
    elif ev == "unconfirmed":
        text = "[待确认] " + text
    if it.get("blocked"):
        text = "[阻塞] " + text
    return text


def item_tail(it):
    bits = []
    if str(it.get("owner") or "").strip():
        bits.append(str(it["owner"]).strip())
    if str(it.get("next_action") or "").strip():
        bits.append("下一步：" + str(it["next_action"]).strip())
    if str(it.get("due") or "").strip():
        bits.append("截止 " + str(it["due"]).strip())
    return "（" + " · ".join(bits) + "）" if bits else ""


def section_pool(facts, sec):
    items = [i for i in facts.get("items", [])
             if i.get("section") == sec and i.get("evidence") != "unconfirmed"]
    if sec == "questions":
        for n, q in enumerate(facts.get("questions", []), 1):
            if isinstance(q, str) and q.strip():
                items.append({"id": "q{}".format(n), "text": q.strip(),
                              "evidence": "unconfirmed", "source": []})
    return items


def metrics_line(facts):
    return " · ".join("{} {}{}".format(m.get("name", ""), m.get("value", ""),
                                       m.get("unit", ""))
                      for m in facts.get("metrics", []))


def source_refs(it):
    return "、".join("{}{}".format(s.get("type", "?"), s.get("ref", "?"))
                    for s in (it.get("source") or [])) or "—"


# --------------------------------------------------------------------------
# LaTeX 渲染（XeLaTeX / Overleaf 通道）
# --------------------------------------------------------------------------
def lint_warning(lint_info):
    """lint 未通过时给 PDF 打红条；不能在 lint 失败时还让成品看起来干净。"""
    if not lint_info or lint_info.get("pass", True):
        return None
    return "注意：lint 未通过（{} 个 error / {} 个 warning），请先核对 lint.json 再使用本 PDF。".format(
        len(lint_info.get("errors") or []), len(lint_info.get("warnings") or []))


def build_tex(facts, figs, out_dir, lint_info=None):
    preamble = TEMPLATE.read_text(encoding="utf-8").split(r"\begin{document}")[0]
    period = facts.get("period", {})
    out = [preamble, r"\begin{document}", ""]
    title = "工作周报 · " + str(period.get("label") or "周期未标注")
    out.append(r"\title{\vspace*{0.2cm}" + esc_tex(title) + "}")
    out.append(r"\author{" + esc_tex(str(facts.get("author") or "未填写")) + "}")
    out.append(r"\maketitle")
    out.append(r"\begin{abstract}" + esc_tex(str(facts.get("headline") or ""))
               + r"\end{abstract}")
    out.append(r"\noindent\textbf{本周量化：} " + esc_tex(metrics_line(facts)) + r"\par")
    warning = lint_warning(lint_info)
    if warning:
        out.append(r"\noindent\textbf{\color{red}" + esc_tex(warning) + r"}\par")
    if facts.get("demo"):
        out.append(r"\noindent\textit{演示数据：非真实工作痕迹，禁止外发。}\par")

    for num, (sec, label, empty) in enumerate(SECTION_LABELS):
        out.append(r"\section{" + label + "}")
        pool = section_pool(facts, sec)
        if not pool:
            out.append(r"\noindent " + esc_tex(empty) + r"\par")
            continue
        out.append(r"\begin{itemize}\setlength{\itemsep}{1pt}")
        for it in pool:
            out.append(r"\item " + esc_tex(item_text(it) + item_tail(it)))
        out.append(r"\end{itemize}")

    if figs:
        out.append(r"\section{本周图表 / FIGURES}")
        for f in figs:
            out.append(r"\begin{figure}[t]\centering")
            out.append(r"\includegraphics[width=" + str(f["width"]) + r"\linewidth]{./"
                       + f["file"] + "}")
            out.append(r"\caption{" + esc_tex(f["caption_full"]) + "}")
            out.append(r"\end{figure}")

    if facts.get("metrics"):
        out.append(r"\section{量化指标 / METRICS}")
        out.append(r"\begin{table}[ht]\centering\small")
        out.append(r"\begin{tabular}{lrl}\hline")
        out.append(r"指标 & 数值 & 计算来源 \\\hline")
        for m in facts["metrics"]:
            out.append("{} & {}{} & {} \\\\".format(
                esc_tex(m.get("name", "")), m.get("value", ""),
                esc_tex(m.get("unit", "")), esc_tex(m.get("computed_by", ""))))
        out.append(r"\hline\end{tabular}")
        out.append(r"\caption{全部数值由 collect.py 从工作痕迹统计得出，非估算。}")
        out.append(r"\end{table}")

    out.append(r"\section{来源清单 / SOURCES}")
    out.append(r"\small\begin{itemize}\setlength{\itemsep}{0pt}")
    for it in facts.get("items", []):
        out.append(r"\item " + esc_tex("{}：{}".format(it.get("id", ""), source_refs(it))))
    out.append(r"\end{itemize}")
    out.append(r"\noindent\textit{" + esc_tex(GATE_NOTE) + "}")
    out.append(r"\end{document}")
    path = Path(out_dir) / "report.tex"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# HTML 渲染（Chrome headless 打印通道，等效双栏）
# --------------------------------------------------------------------------
def build_html(facts, figs, out_dir, lint_info=None):
    period = facts.get("period", {})
    label = str(period.get("label") or "周期未标注")
    parts = [
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
        '<title>工作周报 · ' + esc(label) + '</title><style>', CSS,
        '</style></head><body>',
        '<div class="running-head"><span>WEEKLY REPORT / 工作周报</span><span>'
        + esc(label) + " · " + esc(str(facts.get("author") or "未填写"))
        + '</span></div>',
        '<div class="masthead">',
        '<h1>工作周报</h1>',
        '<div class="meta-line">周期：' + esc(label)
        + '　|　作者：' + esc(str(facts.get("author") or "未填写"))
        + '　|　条目：' + str(len(facts.get("items", []))) + ' 条（可回溯）</div>',
        '<div class="conclusion"><b>结论</b>：'
        + esc(str(facts.get("headline") or "")) + '</div>',
        '<div class="metrics"><b>本周量化</b>：' + esc(metrics_line(facts)) + '</div>',
    ]
    if facts.get("demo"):
        parts.append('<div class="demo">演示数据 · 非真实工作痕迹，请勿外发。</div>')
    warning = lint_warning(lint_info)
    if warning:
        parts.append('<div class="lintbad">' + esc(warning) + '</div>')
    parts.append('</div><div class="paper">')

    for num, (sec, head, empty) in enumerate(SECTION_LABELS):
        parts.append('<h2>' + ROMAN[num] + '. ' + esc(head) + '</h2>')
        pool = section_pool(facts, sec)
        if not pool:
            parts.append('<p class="empty">' + esc(empty) + '</p>')
            continue
        parts.append('<ul class="items">')
        for it in pool:
            text = item_text(it)
            for flag, cls in (("[阻塞] ", "flag"), ("推断：", "infer"),
                              ("[待确认] ", "unconf")):
                if text.startswith(flag):
                    text = '<span class="' + cls + '">' + esc(flag.strip()) + '</span> ' + esc(text[len(flag):])
                    break
            else:
                text = esc(text)
            tail = item_tail(it)
            if tail:
                text += '<span class="owner"> ' + esc(tail) + '</span>'
            parts.append('<li>' + text + '</li>')
        parts.append('</ul>')

    if figs:
        parts.append('<h2>' + ROMAN[len(SECTION_LABELS)] + '. 本周图表 / FIGURES</h2>')
        for f in figs:
            parts.append('<figure><img src="' + esc(f["file"]) + '" alt="'
                         + esc(f["title"]) + '"><figcaption>'
                         + esc(f["caption_full"]) + '</figcaption></figure>')

    if facts.get("metrics"):
        parts.append('<h2>' + ROMAN[len(SECTION_LABELS) + 1] + '. 量化指标 / METRICS</h2>')
        parts.append('<table><thead><tr><th>指标</th><th>数值</th><th>计算来源</th>'
                     '</tr></thead><tbody>')
        for m in facts["metrics"]:
            parts.append('<tr><td>' + esc(m.get("name", "")) + '</td><td>'
                         + esc(str(m.get("value", "")) + str(m.get("unit", "")))
                         + '</td><td>' + esc(m.get("computed_by", "")) + '</td></tr>')
        parts.append('</tbody></table>')
        parts.append('<p class="sources">全部数值由 collect.py 从工作痕迹统计得出，非估算。</p>')

    parts.append('<h2>' + ROMAN[len(SECTION_LABELS) + 2] + '. 来源清单 / SOURCES</h2>')
    parts.append('<table class="sources"><thead><tr><th>ID</th><th>条目</th>'
                 '<th>来源</th></tr></thead><tbody>')
    for it in facts.get("items", []):
        text = str(it.get("text") or "")
        if len(text) > 30:
            text = text[:30] + "…"
        parts.append('<tr><td>' + esc(it.get("id", "")) + '</td><td>' + esc(text)
                     + '</td><td>' + esc(source_refs(it)) + '</td></tr>')
    parts.append('</tbody></table>')
    parts.append('<div class="footer">' + esc(GATE_NOTE) + '</div>')
    parts.append('</div></body></html>')

    path = Path(out_dir) / "report.print.html"
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# 后端探测与自检
# --------------------------------------------------------------------------
BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    "/usr/bin/google-chrome", "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_browser():
    for p in BROWSER_CANDIDATES:
        if p and Path(p).exists():
            return p
    for name in ("google-chrome", "chromium", "msedge", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    return None


def print_with_browser(html_path, pdf_path, browser):
    cmd = [browser, "--headless", "--disable-gpu", "--no-sandbox",
           "--no-pdf-header-footer", "--allow-file-access-from-files",
           "--print-to-pdf=" + str(pdf_path.resolve()), html_path.resolve().as_uri()]
    proc = subprocess.run(cmd, capture_output=True, timeout=180)
    if not pdf_path.exists() or pdf_path.stat().st_size < 1024:
        raise RuntimeError("浏览器打印未产出 PDF："
                           + (proc.stderr or b"").decode("utf-8", "replace")[-400:])
    return str(Path(browser).name)


def compile_with_xelatex(tex_path, pdf_path, out_dir):
    script = HERE / "compile.sh"
    proc = subprocess.run(["bash", str(script), str(tex_path), str(out_dir)],
                          capture_output=True, timeout=300)
    candidate = Path(out_dir) / (tex_path.stem + ".pdf")
    if proc.returncode == 0 and candidate.exists():
        if candidate.resolve() != pdf_path.resolve():
            shutil.copyfile(candidate, pdf_path)
        return True
    return False


def selfcheck(pdf_path, expect_figures=True):
    """逐页核对成品完整度；与 lint（事实正确性）是两件事，两个都要看。"""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz
    except ImportError:
        return {"available": False, "reason": "pymupdf 未安装，跳过逐页自检"}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        doc = fitz.open(str(pdf_path))
        texts = [page.get_text() for page in doc]
        pages = doc.page_count
        doc.close()
    all_text = "".join(texts)
    result = {
        "available": True, "pages": pages, "chars": len(all_text),
        "per_page_chars": [len(t) for t in texts],
        "has_chinese": bool(re.search(r"[\u4e00-\u9fff]", all_text)),
        "has_headline": "结论" in all_text,
        "has_figures": ("图 1" in all_text) or ("每日工作痕迹" in all_text),
        "has_sources": "来源清单" in all_text,
        "has_gate_note": "不发送任何内容" in all_text,
    }
    result["expect_figures"] = bool(expect_figures)
    result["pass"] = bool(
        pages >= 1 and result["has_chinese"] and result["has_headline"]
        and result["has_sources"] and result["has_gate_note"]
        and (result["has_figures"] or not expect_figures))
    return result


def build(facts, views_cfg, figs, out_dir, engine="auto", lint_info=None):
    """生成 .tex / .print.html / PDF，返回 PDF 元信息。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tex_path = build_tex(facts, figs, out, lint_info)
    html_path = build_html(facts, figs, out, lint_info)
    pdf_path = out / "report.pdf"
    info = {"file": None, "tex": tex_path.name, "html": html_path.name,
            "engine": None, "selfcheck": {}, "copy": None, "error": None}

    try:
        if engine in ("auto", "xelatex") and shutil.which("xelatex"):
            if compile_with_xelatex(tex_path, pdf_path, out):
                info["engine"] = "xelatex"
        if not info["engine"] and engine in ("auto", "chrome"):
            browser = find_browser()
            if not browser:
                raise RuntimeError("找不到 Chrome / Edge，且无 XeLaTeX；"
                                   "请把 report.tex 交给 Overleaf（编译器选 XeLaTeX）")
            info["browser"] = print_with_browser(html_path, pdf_path, browser)
            info["engine"] = "chrome-headless"
        if engine == "xelatex" and not info["engine"]:
            raise RuntimeError("XeLaTeX 编译失败，详见 compile.sh 输出")
        if not info["engine"]:
            raise RuntimeError("未产出 PDF（engine={}）".format(engine))
        info["file"] = pdf_path.name
        info["bytes"] = pdf_path.stat().st_size
        info["selfcheck"] = selfcheck(pdf_path, expect_figures=bool(figs))
        period = facts.get("period", {})
        stamp = str(period.get("start", "unknown")).replace("-", "")
        copy_name = "工作周报_{}.pdf".format(stamp)
        shutil.copyfile(pdf_path, out / copy_name)
        info["copy"] = copy_name
    except Exception as e:  # noqa: BLE001 - 降级信息必须回写 manifest
        info["error"] = str(e)
    return info


def main():
    ap = argparse.ArgumentParser(description="facts.json → 双栏 PDF")
    ap.add_argument("--facts", required=True)
    ap.add_argument("--raw", help="raw_items.json，用于 fig1 真实统计")
    ap.add_argument("--out", required=True)
    ap.add_argument("--engine", choices=["auto", "xelatex", "chrome"],
                    default="auto")
    args = ap.parse_args()
    sys.path.insert(0, str(HERE))
    import lint as L
    import make_figs
    facts = json.loads(Path(args.facts).read_text(encoding="utf-8"))
    raw = json.loads(Path(args.raw).read_text(encoding="utf-8")) if args.raw else None
    figs = make_figs.generate(facts, raw, args.out)["figures"]
    info = build(facts, {}, figs, args.out, args.engine, lint_info=L.lint(facts, raw=raw))
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0 if info["file"] else 1


if __name__ == "__main__":
    sys.exit(main())
