#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_report.py — facts.json → 双栏 PDF（主产物）+ 四视图 + 预览 + manifest

原则：
- facts.json 是唯一真源；渲染只做筛选 / 归组 / 排序 / 格式化，不生成任何新事实
- 一份内容出四个受众视图 + 一份 PDF，全部来自同一份 facts，要改就改 facts 再重跑
- 图表只由 make_figs.py 从 raw_items.json / facts.json 真实统计生成，绝不造数
- PDF 双通道：XeLaTeX 优先，缺则 Chrome / Edge headless 打印等效双栏 HTML
- 只写文件，绝不发送；预览确认这一步属于人
- 幂等：视图正文不含生成时间；--deterministic 时 manifest 也不含，便于 diff

  python build_report.py --facts output/facts.json --out output/
  python build_report.py --facts output/facts.json --strict --deterministic
  python build_report.py --facts output/facts.json --no-pdf        # 只出文本
  python build_report.py --facts output/facts.json --pdf-engine xelatex
"""
import argparse
import hashlib
import html
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import lint as L

GATE_NOTE = "本工具不发送任何内容；生成后需人工预览确认再自行转发。"

CSS = """
:root{--bd:#dcdcdc;--ink:#1b1b1b;--mut:#666;--bg:#fafafa}
*{box-sizing:border-box}
body{margin:0;padding:28px;background:var(--bg);color:var(--ink);
     font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
main{max-width:900px;margin:0 auto}
h1{font-size:20px;font-weight:600;margin:0 0 4px}
.meta{color:var(--mut);font-size:13px;margin:0 0 16px}
.banner{padding:10px 14px;border-radius:8px;margin:0 0 12px;font-size:13px}
.banner.ok{background:#e7f5ee;border:1px solid #9fd8bd;color:#0f5b3d}
.banner.bad{background:#fceaea;border:1px solid #e6a9a9;color:#8b2626}
.banner.demo{background:#fff3d6;border:1px solid #e8c571;color:#7a5300}
.banner ul{margin:6px 0 0;padding-left:18px}
.gate{font-size:13px;color:var(--mut);border-left:3px solid #bbb;
      padding-left:10px;margin:0 0 20px}
details{background:#fff;border:1px solid var(--bd);border-radius:10px;
        margin:0 0 12px;overflow:hidden}
summary{cursor:pointer;padding:12px 16px;font-weight:600;list-style:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"\\25b8 ";color:var(--mut)}
details[open] summary::before{content:"\\25be "}
summary span{float:right;font-weight:400;color:var(--mut);font-size:12px}
pre{margin:0;padding:16px;border-top:1px solid var(--bd);background:#fcfcfc;
    white-space:pre-wrap;word-break:break-word;color:#222;
    font:12.5px/1.7 "Cascadia Code",Consolas,"Microsoft YaHei",monospace}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #eee;vertical-align:top}
.src{padding:8px 16px 16px}
@media print{body{background:#fff;padding:0}details{break-inside:avoid}
             summary span{display:none}}
"""


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def uniq(pool):
    seen, out = set(), []
    for item in pool:
        key = str(item.get("id"))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def format_item(item, cfg):
    text = str(item.get("text") or "").strip()
    ev = item.get("evidence", "fact")
    if ev == "inference":
        text = "推断：" + text
    elif ev == "unconfirmed":
        text = "[待确认] " + text
    if item.get("blocked"):
        text = "[阻塞] " + text
    if cfg.get("hide_internal_refs"):
        for ref in item.get("internal_refs") or []:
            if ref:
                text = text.replace(ref, "[内部信息]")

    tail = []
    if not cfg.get("compact"):
        if str(item.get("owner") or "").strip():
            tail.append(str(item["owner"]).strip())
        if str(item.get("next_action") or "").strip():
            tail.append("下一步：" + str(item["next_action"]).strip())
        if str(item.get("due") or "").strip():
            tail.append("截止 " + str(item["due"]).strip())
    line = text + ("（" + " · ".join(tail) + "）" if tail else "")

    if cfg.get("show_sources") and item.get("source"):
        refs = "、".join("{}{}".format(s.get("type", "?"), s.get("ref", "?"))
                        for s in item["source"])
        line += "  `[来源: {}]`".format(refs)
    return line


def render_view(name, cfg, facts, sections, empty_labels):
    is_md = cfg.get("format") == "markdown"
    items = facts.get("items", [])
    period = facts.get("period", {})
    out, shown_total = [], 0

    title = "周报｜" + str(period.get("label") or "周期未标注")
    if not cfg.get("compact") and facts.get("author"):
        title += " · " + str(facts["author"])
    out.append(("# " + title) if is_md else title)
    if facts.get("demo"):
        out.append("> 演示数据 · 非真实工作痕迹，请勿外发" if is_md
                   else "[演示数据 · 非真实工作痕迹，请勿外发]")
    out.append("")

    if cfg.get("include_headline", True):
        headline = str(facts.get("headline") or "").strip()
        out.append(("**结论**：" + headline) if is_md else ("【结论】" + headline))
        out.append("")

    for sec in cfg.get("sections", []):
        label = sections.get(sec, {}).get("label", sec)
        out.append(("## " + label) if is_md else ("【" + label + "】"))
        if sec == "questions":
            pool = [i for i in items
                    if i.get("section") == "questions" or i.get("evidence") == "unconfirmed"]
            for n, q in enumerate(facts.get("questions", []), 1):
                if isinstance(q, str) and q.strip():
                    pool.append({"id": "q{}".format(n), "text": q.strip(),
                                 "evidence": "unconfirmed", "source": []})
        else:
            pool = [i for i in items
                    if i.get("section") == sec and i.get("evidence") != "unconfirmed"]
        pool = uniq(pool)

        cap = int(cfg.get("max_items", {}).get(sec, 0) or 0)
        shown = pool[:cap] if cap else pool
        hidden = len(pool) - len(shown)
        prefix = "- " if is_md else ""

        if not shown:
            out.append(prefix + empty_labels.get(sec, "无"))
        else:
            for n, item in enumerate(shown, 1):
                line = format_item(item, cfg)
                out.append((prefix + line) if is_md else ("{}. {}".format(n, line)))
            shown_total += len(shown)
            if hidden > 0 and not cfg.get("compact"):
                out.append(prefix + "（另有 {} 条见留存版）".format(hidden))
        out.append("")

    if cfg.get("show_metrics") and facts.get("metrics"):
        metrics = facts["metrics"]
        inline = " · ".join("{} {}{}".format(
            m.get("name", ""), m.get("value", ""), m.get("unit", ""))
            for m in metrics)
        if is_md and cfg.get("metrics_style") == "inline":
            out.append("**本周量化**：" + inline)
        elif is_md:
            out.append("## 本周量化")
            out.append("| 指标 | 值 | 计算来源 |")
            out.append("| --- | --- | --- |")
            for m in metrics:
                out.append("| {} | {}{} | {} |".format(
                    m.get("name", ""), m.get("value", ""), m.get("unit", ""),
                    m.get("computed_by", "")))
        else:
            out.append("【本周量化】" + inline)
        out.append("")

    if cfg.get("compact"):
        out.append("（以上为摘要，完整明细含来源、负责人与截止时间。）")

    return "\n".join(out).rstrip() + "\n", shown_total


def render_html(facts, rendered, views_cfg, lint_result, pdf_info=None, figs_info=None):
    esc = html.escape
    p = facts.get("period", {})
    parts = [
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">",
        "<title>周报预览</title><style>", CSS, "</style></head><body><main>",
        "<h1>周报预览</h1>",
        "<p class=\"meta\">{} · 作者：{} · 生成视图 {} 份</p>".format(
            esc(str(p.get("label") or "周期未标注")),
            esc(str(facts.get("author") or "未填写")), len(rendered)),
    ]
    if facts.get("demo"):
        parts.append("<div class=\"banner demo\">演示数据 · 非真实工作痕迹，请勿外发。"
                     "接入真实来源后此水印自动消失。</div>")
    trace = lint_result.get("trace", {})
    trace_note = (" · 溯源 ON（{} 条原文 / {} 处不一致）".format(
        trace.get("raw_items", 0), trace.get("mismatches", 0))
        if trace.get("checked") else " · 溯源 OFF")
    if lint_result["pass"]:
        parts.append("<div class=\"banner ok\">lint PASS · 0 error · {} warning{}</div>".format(
            len(lint_result["warnings"]), trace_note))
    else:
        parts.append("<div class=\"banner bad\">lint FAIL · {} error{}<ul>".format(
            len(lint_result["errors"]), trace_note))
        for e in lint_result["errors"][:12]:
            parts.append("<li>[{}] {} {}</li>".format(
                esc(e["code"]), esc(str(e["item"])), esc(e["message"])))
        parts.append("</ul></div>")
    if pdf_info and pdf_info.get("file"):
        check = pdf_info.get("selfcheck") or {}
        tail = ("（自检仅验证成品完整度，lint 仍有 error，见上方红条）"
                if not lint_result["pass"] else "")
        parts.append("<div class=\"banner ok\">主产物 PDF 已生成：<a href=\"{}\">{}</a>"
                     " · 引擎 {} · 图表 {} 张 · 逐页自检 {}{}</div>".format(
                         esc(pdf_info["file"]), esc(pdf_info["file"]),
                         esc(str(pdf_info.get("engine") or "—")),
                         len((figs_info or {}).get("files") or []),
                         "PASS" if check.get("pass") else "未通过/未执行",
                         esc(tail)))
    elif pdf_info and pdf_info.get("error"):
        parts.append("<div class=\"banner bad\">PDF 生成失败：{}；"
                     "可把 report.tex 交给 Overleaf 编译。</div>".format(
                         esc(pdf_info["error"])))
    parts.append("<p class=\"gate\">{} 下方为可直接复制的原始文本，"
                 "四份视图与 PDF 来自同一份事实清单。</p>".format(esc(GATE_NOTE)))

    for name, cfg in views_cfg.get("views", {}).items():
        text = rendered.get(name, "")
        opener = " open" if name == "lead" else ""
        parts.append("<details{}><summary>{} · {}<span>{} 字</span></summary>".format(
            opener, esc(str(cfg.get("label", name))), esc(str(cfg.get("audience", ""))),
            len(text)))
        parts.append("<pre>" + esc(text) + "</pre></details>")

    items = facts.get("items", [])
    with_src = [i for i in items if i.get("source")]
    parts.append("<details><summary>来源清单（{} / {} 条可回查）</summary><div class=\"src\">".format(
        len(with_src), len(items)))
    parts.append("<table><thead><tr><th>ID</th><th>条目</th><th>证据</th>"
                 "<th>来源</th></tr></thead><tbody>")
    for i in items:
        refs = "、".join("{}{}".format(s.get("type", "?"), s.get("ref", "?"))
                        for s in (i.get("source") or [])) or "—"
        text = str(i.get("text") or "")
        if len(text) > 46:
            text = text[:46] + "…"
        parts.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(str(i.get("id", ""))), esc(text),
            esc(str(i.get("evidence", ""))), esc(refs)))
    parts.append("</tbody></table></div></details>")
    parts.append("</main></body></html>")
    return "\n".join(parts) + "\n"


def build_manifest(facts_path, facts, views_cfg, rendered, counts, lint_result,
                   deterministic, trace_info, figs_info, pdf_info):
    facts_bytes = Path(facts_path).read_bytes()
    m = {
        "schema_version": "1.0",
        "period": facts.get("period", {}),
        "author": facts.get("author", ""),
        "demo": bool(facts.get("demo")),
        "facts_sha256": hashlib.sha256(facts_bytes).hexdigest(),
        "views": [
            {"name": name, "label": views_cfg["views"][name].get("label", name),
             "file": views_cfg["views"][name].get("file"),
             "chars": len(rendered.get(name, "")),
             "items_shown": counts.get(name, 0)}
            for name in rendered
        ],
        "lint": {"pass": lint_result["pass"],
                 "errors": len(lint_result["errors"]),
                 "warnings": len(lint_result["warnings"])},
        "trace": trace_info,
        "primary_output": (pdf_info or {}).get("file"),
        "figures": figs_info,
        "pdf": pdf_info,
        "decision_gate": GATE_NOTE,
        "deterministic": bool(deterministic),
    }
    if not deterministic:
        m["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    return m


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


def build_pdf_artifacts(facts, views_cfg, raw, out_dir, engine, lint_result, enabled):
    """默认开启的「真实统计出图 → 双通道 PDF」链路。

    第三方依赖（matplotlib / pymupdf）缺失或引擎都不可用时，只降级掉 PDF，
    文本四视图照常产出；失败原因写进 manifest，不静默吞掉。
    """
    if not enabled:
        return ({"enabled": False, "reason": "--no-pdf", "files": [], "count": 0},
                {"enabled": False, "reason": "--no-pdf", "pass": False})
    try:
        import make_figs as F
        import build_pdf as P

        result = F.generate(facts, raw, out_dir)
        figs = result["figures"]
        figs_info = {
            "enabled": True,
            "font": result["font"],
            "count": len(figs),
            "files": [{"n": f["n"], "file": f["file"], "title": f["title"],
                       "data_source": f["data_source"]} for f in figs],
        }
        pdf_info = P.build(facts, views_cfg, figs, out_dir, engine,
                           lint_info=lint_result)
        pdf_info["enabled"] = True
        pdf_info["pass"] = bool(pdf_info.get("file")) and bool(
            (pdf_info.get("selfcheck") or {}).get("pass"))
        return figs_info, pdf_info
    except Exception as e:  # noqa: BLE001 - 降级原因必须回写 manifest
        reason = "{}: {}".format(type(e).__name__, e)
        return ({"enabled": True, "error": reason, "files": [], "count": 0},
                {"enabled": True, "error": reason, "pass": False})


def main():
    ap = argparse.ArgumentParser(description="facts.json → 多视图周报")
    ap.add_argument("--facts", required=True)
    ap.add_argument("--views", default=str(ROOT / "assets" / "views.json"))
    ap.add_argument("--out", help="输出目录，默认与 facts.json 同目录")
    ap.add_argument("--raw", help="显式指定 raw_items.json（默认自动探测 facts 同目录）")
    ap.add_argument("--no-trace", action="store_true",
                    help="关闭 E015/E016 逐条溯源校验（不建议）")
    ap.add_argument("--strict", action="store_true",
                    help="lint 有 error 时阻断出稿（默认只告警并照常生成）")
    ap.add_argument("--deterministic", action="store_true",
                    help="manifest 不写生成时间，便于 diff 与幂等重跑")
    ap.add_argument("--no-pdf", action="store_true",
                    help="只出文本四视图 + HTML，跳过出图与 PDF（依赖缺失时的降级开关）")
    ap.add_argument("--pdf-engine", choices=["auto", "xelatex", "chrome"],
                    default="auto",
                    help="PDF 后端：auto = XeLaTeX 优先，缺则 Chrome/Edge headless")
    args = ap.parse_args()

    facts = load_json(args.facts)
    views_cfg = load_json(args.views)
    out_dir = Path(args.out) if args.out else Path(args.facts).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # §2.5：默认自动探测 facts 同目录的采集原文，既做溯源，也做出图的数据源
    # --no-trace 只关 lint 比对，不影响图表继续读真实数据。
    raw_path = None
    if args.raw:
        raw_path = Path(args.raw)
    else:
        cand = Path(args.facts).resolve().parent / "raw_items.json"
        if cand.exists():
            raw_path = cand
    raw = load_json(raw_path) if raw_path else None
    if raw is None and not args.no_trace:
        print("[info] 未找到 raw_items.json，跳过溯源校验（E015/E016 不执行）；"
              "fig1 每日痕迹量也会跳过")

    lint_result = L.lint(facts, raw=None if args.no_trace else raw)
    trace_info = dict(lint_result["trace"])
    trace_info["raw_file"] = raw_path.name if (raw_path and not args.no_trace) else None
    rendered, counts = {}, {}
    for name, cfg in views_cfg.get("views", {}).items():
        text, n = render_view(name, cfg, facts,
                              views_cfg.get("sections", {}),
                              views_cfg.get("empty_labels", {}))
        rendered[name], counts[name] = text, n
    lint_result["warnings"].extend(L.lint_views(rendered, views_cfg))

    write(out_dir / "lint.json",
          json.dumps(lint_result, ensure_ascii=False, indent=2) + "\n")
    if args.strict and not lint_result["pass"]:
        print("lint 未通过，--strict 已阻断出稿。详见", out_dir / "lint.json",
              file=sys.stderr)
        for e in lint_result["errors"][:10]:
            print("  [{}] {} {}".format(e["code"], e["item"], e["message"]),
                  file=sys.stderr)
        return 2

    # 主产物：真实统计出图 → 双通道 PDF（默认开启）
    figs_info, pdf_info = build_pdf_artifacts(
        facts, views_cfg, raw, out_dir, args.pdf_engine, lint_result,
        enabled=not args.no_pdf)

    for name, cfg in views_cfg["views"].items():
        write(out_dir / cfg["file"], rendered[name])
    write(out_dir / "report.html",
          render_html(facts, rendered, views_cfg, lint_result, pdf_info, figs_info))
    write(out_dir / "manifest.json",
          json.dumps(build_manifest(args.facts, facts, views_cfg, rendered, counts,
                                    lint_result, args.deterministic, trace_info,
                                    figs_info, pdf_info),
                     ensure_ascii=False, indent=2) + "\n")

    print("周报已生成 →", out_dir)
    if pdf_info.get("file"):
        chk = pdf_info.get("selfcheck") or {}
        print("  ★ 主产物 PDF  {:<16} {} 页 / {} 字节 / 引擎 {} / 自检 {}".format(
            pdf_info["file"], chk.get("pages", "?"), pdf_info.get("bytes", "?"),
            pdf_info.get("engine", "?"),
            "PASS" if chk.get("pass") else "FAIL"))
        if not lint_result["pass"]:
            print("    ↑ 自检只管成品完整度；lint 仍有 {} 个 error，PDF 已打红条，"
                  "确认前必须修掉".format(len(lint_result["errors"])))
        if pdf_info.get("copy"):
            print("    副本        " + pdf_info["copy"])
    elif not args.no_pdf:
        print("  ! PDF 未生成：" + str(pdf_info.get("error") or "未知原因")
              + "（report.tex 可交 Overleaf）")
    if figs_info.get("enabled"):
        print("  图表          {} 张真实统计（{}）".format(
            figs_info.get("count", 0),
            "、".join(f["file"] for f in figs_info.get("files", [])) or "无"))
    for name, cfg in views_cfg["views"].items():
        print("  {:<10} {:<20} {} 字 / {} 条".format(
            name, cfg["file"], len(rendered[name]), counts[name]))
    t = trace_info
    print("  lint: {}  error={}  warning={}  trace={}".format(
        "PASS" if lint_result["pass"] else "FAIL",
        len(lint_result["errors"]), len(lint_result["warnings"]),
        "ON ({} 条原文 / {} 处不一致)".format(t["raw_items"], t["mismatches"])
        if t["checked"] else "OFF"))
    print("  " + GATE_NOTE)
    if args.strict and not args.no_pdf and not pdf_info.get("file"):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
