#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect.py — 确定性采集工作痕迹，产出 raw_items.json。

事实红线的第一道闸门：零改写、零概括、零补充。
git subject / 草稿原文 / 工单标题原样入库，每条都带可回查的 source 指针。
只允许一种文本变换：--redact 显式指定的脱敏替换（并会被记录）。

只用 Python 标准库。不联网、不调模型、不改任何源文件。

用法：
  python collect.py --repo . --notes sample/notes.md --out output/raw_items.json
  python collect.py --sample --out output/raw_items.json
  python collect.py --repo . --since 2026-11-02 --until 2026-11-08 --out output/raw_items.json
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

PREFIX_KIND = {"!": "risk", ">": "next", "~": "doing"}
TICKET_STATUS = {
    "done": "done", "closed": "done", "resolved": "done", "已完成": "done",
    "doing": "doing", "in_progress": "doing", "progress": "doing", "进行中": "doing",
    "blocked": "risk", "阻塞": "risk",
    "todo": "next", "open": "next", "待办": "next",
}


def warn(msg):
    print("[warn] " + msg, file=sys.stderr)


def default_period():
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def period_label(start, end):
    y, w, _ = date.fromisoformat(start).isocalendar()
    return "{} ~ {}（{} 年第 {} 周）".format(start, end, y, w)


def redact(text, words):
    for w in words:
        if w:
            text = text.replace(w, "[已脱敏]")
    return text


def collect_git(repo, since, until, words):
    cmd = [
        "git", "-C", str(repo), "log",
        "--since=" + since,
        "--until=" + until + " 23:59:59",
        "--no-merges", "--date=short",
        "--pretty=format:%H%x09%ad%x09%an%x09%s",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        warn("git 不可用，跳过 git 来源")
        return []
    if p.returncode != 0:
        detail = (p.stderr or "").strip().splitlines()
        warn("git log 失败（可能不是仓库或区间无提交），跳过："
             + (detail[0] if detail else "无输出"))
        return []
    items = []
    for line in p.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        sha, day, author, subject = parts[0], parts[1], parts[2], "\t".join(parts[3:])
        items.append({
            "id": "g{}".format(len(items) + 1),
            "text": redact(subject, words),
            "date": day,
            "kind": "done",
            "author": author,
            "source": [{"type": "git", "ref": sha[:8], "detail": str(repo)}],
        })
    return items


def collect_notes(path, words):
    items = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as e:
        warn("读草稿失败，跳过：{}".format(e))
        return items
    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        kind = "done"
        if line[0] in PREFIX_KIND:
            kind = PREFIX_KIND[line[0]]
            line = line[1:].strip()
        if not line:
            continue
        m = re.search(r"@([\w\u4e00-\u9fff.\-]+)", line)
        items.append({
            "id": "n{}".format(len(items) + 1),
            "text": redact(line, words),
            "date": "",
            "kind": kind,
            "author": "",
            "owner": m.group(1) if m else "",
            "source": [{"type": "note", "ref": "{}:L{}".format(Path(path).name, n)}],
        })
    return items


def collect_tickets(path, words):
    items = []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        warn("读工单导出失败，跳过：{}".format(e))
        return items
    rows = data if isinstance(data, list) else data.get("items", data.get("tickets", []))
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or row.get("subject") or "").strip()
        if not title:
            continue
        status = str(row.get("status", "")).strip().lower()
        ref = str(row.get("id") or row.get("key") or "?")
        items.append({
            "id": "t{}".format(len(items) + 1),
            "text": redact(title, words),
            "date": str(row.get("updated") or row.get("date") or "")[:10],
            "kind": TICKET_STATUS.get(status, "doing"),
            "author": str(row.get("owner") or ""),
            "owner": str(row.get("owner") or ""),
            "source": [{"type": "ticket", "ref": ref,
                        "detail": str(row.get("url") or row.get("id") or "")}],
        })
    return items


def make_metrics(items):
    kinds = Counter(i["kind"] for i in items)
    days = {i["date"] for i in items if i.get("date")}
    src = "raw_items.json / collect.py"
    return [
        {"name": "工作痕迹条目", "value": len(items), "unit": "条",
         "source": src, "computed_by": "collect.py"},
        {"name": "已完成", "value": kinds["done"], "unit": "条",
         "source": src, "computed_by": "collect.py"},
        {"name": "进行中", "value": kinds["doing"], "unit": "条",
         "source": src, "computed_by": "collect.py"},
        {"name": "风险 / 阻塞", "value": kinds["risk"], "unit": "条",
         "source": src, "computed_by": "collect.py"},
        {"name": "下一步", "value": kinds["next"], "unit": "条",
         "source": src, "computed_by": "collect.py"},
        {"name": "有痕迹天数", "value": len(days), "unit": "天",
         "source": src, "computed_by": "collect.py"},
    ]


def main():
    ap = argparse.ArgumentParser(description="确定性采集工作痕迹 → raw_items.json")
    ap.add_argument("--repo", help="git 仓库路径")
    ap.add_argument("--notes", help="随手 bullet 草稿 (.md/.txt)")
    ap.add_argument("--tickets", help="工单导出 (.json)")
    ap.add_argument("--since", help="起始日期 YYYY-MM-DD，默认本周一")
    ap.add_argument("--until", help="结束日期 YYYY-MM-DD，默认本周日")
    ap.add_argument("--author", default="", help="报告作者")
    ap.add_argument("--out", required=True, help="输出 raw_items.json 路径")
    ap.add_argument("--redact", default="", help="逗号分隔的脱敏词，命中处替换为 [已脱敏]")
    ap.add_argument("--sample", action="store_true",
                    help="读 sample/raw_items.json 演示数据（强制 demo=true）")
    args = ap.parse_args()

    d_start, d_end = default_period()
    since = args.since or d_start
    until = args.until or d_end
    words = [w.strip() for w in args.redact.split(",") if w.strip()]

    if args.sample:
        sample = ROOT / "sample" / "raw_items.json"
        data = json.loads(sample.read_text(encoding="utf-8"))
        data["demo"] = True
        origin = [{"type": "sample", "path": str(sample), "demo": True}]
    else:
        if not any([args.repo, args.notes, args.tickets]):
            ap.error("至少给一个来源：--repo / --notes / --tickets / --sample")
        items, origin = [], []
        for label, fn, val in (("git", collect_git, args.repo),
                               ("note", collect_notes, args.notes),
                               ("ticket", collect_tickets, args.tickets)):
            if not val:
                continue
            got = (fn(val, since, until, words) if label == "git" else fn(val, words))
            items.extend(got)
            origin.append({"type": label, "path": str(val), "count": len(got)})
        data = {
            "schema_version": "1.0",
            "demo": False,
            "period": {"start": since, "end": until, "label": period_label(since, until)},
            "author": args.author,
            "generated_from": origin,
            "redactions": words,
            "items": items,
            "metrics": make_metrics(items),
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("raw_items.json →", out)
    print("  区间：{}".format(data["period"]["label"]))
    print("  条目：{} 条".format(len(data["items"])))
    for o in data["generated_from"]:
        print("  来源：{} {}".format(o["type"], o.get("path", "")))
    if data.get("demo"):
        print("  [演示数据] 非真实工作痕迹，仅供跑通链路")
    if not data["items"]:
        warn("没有采集到任何条目。不会替你补写内容，请检查来源或时间区间。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
