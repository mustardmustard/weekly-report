#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_figs.py — 用真实工作痕迹统计出图，绝不造数。

这是与 goushi-writing 最关键的分野：那边用玩具模型造「示意数据」，
这边每个像素都只能来自 raw_items.json（采集原文）或 facts.json（整理结果）。

    fig1 每日工作痕迹量   ← raw.items[].date
    fig2 栏目构成         ← facts.items[].section
    fig3 在途事项截止日   ← facts.items[].due × section

缺字段就跳过那张图，绝不补造数字。每张图的 caption 都写明数据来源。

用法：python make_figs.py --facts sample/facts.json --raw sample/raw_items.json --out output/
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from figure_helper import setup_cjk

INK = "#222222"
PURPLE = "#534AB7"
BLUE = "#378ADD"
TEAL = "#1D9E75"
AMBER = "#BA7517"
RED = "#B02424"

SECTION_LABELS = {
    "done": "已完成", "doing": "进行中", "risk": "风险 / 阻塞",
    "next": "下一步", "questions": "待确认",
}
SECTION_COLORS = {
    "done": PURPLE, "doing": BLUE, "risk": RED, "next": TEAL,
    "questions": AMBER,
}
SECTION_ORDER = ["done", "doing", "risk", "next", "questions"]
ACTIVE_SECTIONS = ["doing", "risk", "next"]


def _save(fig, out_dir, name):
    path = Path(out_dir) / name
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_daily(raw, out_dir):
    """按采集原文的 date 字段统计每日痕迹量。"""
    if not raw:
        return None
    dates = Counter(
        str(i.get("date") or "").strip()[:10]
        for i in raw.get("items", [])
        if str(i.get("date") or "").strip()
    )
    if not dates:
        return None
    keys = sorted(dates)
    vals = [dates[k] for k in keys]
    fig, ax = plt.subplots(figsize=(3.35, 2.0))
    ax.bar(range(len(keys)), vals, color=PURPLE, width=0.6)
    for x, v in zip(range(len(keys)), vals):
        ax.text(x, v + 0.04, str(v), ha="center", va="bottom",
                fontsize=8, color=INK)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([k[5:] for k in keys], fontsize=8)
    ax.set_ylim(0, max(vals) * 1.35 + 0.3)
    ax.set_ylabel("条数", fontsize=8.5)
    ax.set_title("(a) 每日工作痕迹量", fontsize=9, loc="left")
    ax.tick_params(axis="both", labelsize=8)
    fig.tight_layout()
    _save(fig, out_dir, "fig1.png")
    return {
        "file": "fig1.png", "title": "每日工作痕迹量", "width": 0.92,
        "data_source": "raw_items.json / date",
        "caption": "每日工作痕迹条数。数据来源：raw_items.json 按 date 聚合，"
                   "共 {} 条带日期记录；无日期的草稿条目未计入。".format(sum(vals)),
    }


def fig_sections(facts, out_dir):
    """按 facts 的 section 字段统计栏目构成。"""
    items = facts.get("items", [])
    if not items:
        return None
    counts = Counter(i.get("section") for i in items)
    keys = [s for s in SECTION_ORDER if counts.get(s)]
    if not keys:
        return None
    vals = [counts[k] for k in keys]
    fig, ax = plt.subplots(figsize=(3.35, 1.95))
    ys = list(range(len(keys)))
    ax.barh(ys, vals, color=[SECTION_COLORS[k] for k in keys], height=0.6)
    ax.set_yticks(ys)
    ax.set_yticklabels([SECTION_LABELS[k] for k in keys], fontsize=8.5)
    ax.invert_yaxis()
    for y, v in zip(ys, vals):
        ax.text(v + 0.06, y, str(v), va="center", fontsize=8, color=INK)
    ax.set_xlim(0, max(vals) * 1.3 + 0.3)
    ax.set_xlabel("条目数", fontsize=8.5)
    ax.set_title("(b) 栏目构成", fontsize=9, loc="left")
    ax.tick_params(axis="both", labelsize=8)
    fig.tight_layout()
    _save(fig, out_dir, "fig2.png")
    return {
        "file": "fig2.png", "title": "栏目构成", "width": 0.92,
        "data_source": "facts.json / section",
        "caption": "各类条目数量。数据来源：facts.json 的 section 字段，"
                   "共 {} 条；questions 中的纯文本待确认项未计入。".format(len(items)),
    }


def fig_deadlines(facts, out_dir):
    """按 facts 的 due × section 统计在途事项的截止日分布。"""
    rows = [i for i in facts.get("items", [])
            if str(i.get("due") or "").strip()
            and i.get("section") in ACTIVE_SECTIONS]
    if not rows:
        return None
    table = defaultdict(Counter)
    for i in rows:
        table[str(i["due"]).strip()][i["section"]] += 1
    keys = sorted(table)
    fig, ax = plt.subplots(figsize=(3.35, 2.05))
    bottom = np.zeros(len(keys), dtype=float)
    for s in ACTIVE_SECTIONS:
        vals = np.array([table[k].get(s, 0) for k in keys], dtype=float)
        if vals.sum() == 0:
            continue
        ax.bar(range(len(keys)), vals, bottom=bottom,
               color=SECTION_COLORS[s], width=0.6,
               label=SECTION_LABELS[s])
        bottom += vals
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([k[5:] for k in keys], fontsize=8)
    ax.set_ylabel("条目数", fontsize=8.5)
    ax.set_title("(c) 在途事项截止日分布", fontsize=9, loc="left")
    ax.legend(fontsize=7.5, ncol=3, loc="upper left", frameon=False)
    ax.tick_params(axis="both", labelsize=8)
    fig.tight_layout()
    _save(fig, out_dir, "fig3.png")
    return {
        "file": "fig3.png", "title": "在途事项截止日分布", "width": 0.92,
        "data_source": "facts.json / due x section",
        "caption": "进行中 / 风险 / 下一步按截止日的堆叠分布，共 {} 条。"
                   "数据来源：facts.json 的 due 与 section 字段。".format(len(rows)),
    }


def generate(facts, raw, out_dir):
    """生成所有可行图表，返回 figures 元信息列表（含渲染后的 caption_full）。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    font = setup_cjk(9)
    builders = [
        lambda: fig_daily(raw, out),
        lambda: fig_sections(facts, out),
        lambda: fig_deadlines(facts, out),
    ]
    figs = []
    for build in builders:
        meta = build()
        if meta:
            figs.append(meta)
    for n, meta in enumerate(figs, 1):
        meta["n"] = n
        meta["caption_full"] = "图 {}. {}".format(n, meta["caption"])
    return {"font": font or "(未找到中文字体，标签退化为英文)",
            "figures": figs}


def main():
    ap = argparse.ArgumentParser(description="用真实痕迹统计出图")
    ap.add_argument("--facts", required=True)
    ap.add_argument("--raw", help="raw_items.json，缺则跳过 fig1")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    facts = json.loads(Path(args.facts).read_text(encoding="utf-8"))
    raw = json.loads(Path(args.raw).read_text(encoding="utf-8")) if args.raw else None
    result = generate(facts, raw, args.out)
    print("CJK font:", result["font"])
    for f in result["figures"]:
        print("  {} -> {}  [{}]".format(f["file"], f["title"], f["data_source"]))
    if not result["figures"]:
        print("  没有可绘制的真实数据，未生成任何图（不造数）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
