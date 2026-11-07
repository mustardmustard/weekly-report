#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lint.py — 周报事实清单的可机检质量规则。

对应 references/report-guide.md §8 与 §2.5。可被 build_report.py import，也可单独跑：
  python lint.py output/facts.json --raw output/raw_items.json
退出码：有 error 时 1，否则 0。
"""
import argparse
import json
import re
import sys
from pathlib import Path

BANNED = ("顺利完成", "大力推进", "显著提升", "基本完成", "有序开展",
          "积极跟进", "圆满完成", "全面铺开", "卓有成效")
NO_OWNER_OPENERS = ("已推进", "已完成对接", "持续优化", "继续推进", "已开展")
SECTIONS = {"done", "doing", "risk", "next", "questions"}
EVIDENCE = {"fact", "inference", "unconfirmed"}
ACTION_SECTIONS = {"doing", "risk", "next"}
DUE_SECTIONS = {"risk", "next"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OWNER_MARK_RE = re.compile(r"@[\w\u4e00-\u9fff.\-]+")


def normalize_text(s):
    """整理层唯一允许的文本变换：去掉 @owner 草稿标记并压缩空白。"""
    return re.sub(r"\s+", " ", OWNER_MARK_RE.sub("", s or "")).strip()


def check_trace(facts, raw):
    """§2.5：逐条回溯，text / id 必须与采集原文对得上。"""
    by_id = {}
    for i in raw.get("items", []):
        by_id[str(i.get("id"))] = str(i.get("text") or "").strip()
    errors = []
    for idx, it in enumerate(facts.get("items", [])):
        iid = str(it.get("id") or "items[{}]".format(idx))
        if iid not in by_id:
            errors.append({
                "code": "E016", "item": iid,
                "message": "id 在 raw_items.json 中不存在（不许重命名，也不许凭空新增事实条目）",
            })
            continue
        orig = by_id[iid]
        text = str(it.get("text") or "").strip()
        if text != orig and text != normalize_text(orig):
            errors.append({
                "code": "E015", "item": iid,
                "message": "text 与采集原文不一致；只允许去掉 @owner 标记",
            })
    return errors


def lint(facts, raw=None):
    errors, warnings = [], []
    items = facts.get("items", [])
    trace = {"checked": raw is not None,
             "raw_items": len(raw.get("items", [])) if raw is not None else 0,
             "mismatches": 0}

    def err(code, iid, msg):
        errors.append({"code": code, "item": iid or "-", "message": msg})

    def wrn(code, iid, msg):
        warnings.append({"code": code, "item": iid or "-", "message": msg})

    seen = set()
    for idx, it in enumerate(items):
        iid = str(it.get("id") or "items[{}]".format(idx))
        text = str(it.get("text") or "")
        sec = it.get("section", "")
        ev = it.get("evidence", "")
        src = it.get("source") or []

        if iid in seen:
            err("E010", iid, "id 重复")
        seen.add(iid)
        if sec not in SECTIONS:
            err("E013", iid, "section 非法：{}".format(sec))
        if ev not in EVIDENCE:
            err("E012", iid, "evidence 非法：{}".format(ev))
        if ev in ("fact", "inference") and not src:
            err("E001" if ev == "fact" else "E002", iid,
                "{} 条目必须带 source".format(ev))
        if sec in ACTION_SECTIONS and not str(it.get("owner") or "").strip():
            err("E003", iid, "{} 缺 owner（谁负责）".format(sec))
        if sec in ACTION_SECTIONS and not str(it.get("next_action") or "").strip():
            err("E004", iid, "{} 缺 next_action（接下来做什么）".format(sec))
        if sec in DUE_SECTIONS and not str(it.get("due") or "").strip():
            err("E005", iid, "{} 缺 due（什么时候）".format(sec))
        due = str(it.get("due") or "").strip()
        if due and not DATE_RE.match(due):
            err("E011", iid, "due 格式应为 YYYY-MM-DD：{}".format(due))
        if len(text) > 80:
            wrn("W001", iid, "单条 {} 字，超过 80 字".format(len(text)))
        for w in BANNED:
            if w in text:
                wrn("W002", iid, "禁用词「{}」：用事实代替形容词".format(w))
        for op in NO_OWNER_OPENERS:
            if text.startswith(op) and not str(it.get("owner") or "").strip():
                wrn("W005", iid, "无主语句开头「{}」".format(op))
                break
        if sec == "done" and ev == "unconfirmed":
            wrn("W004", iid, "待确认条目不应放进「已完成」")

    if not any(i.get("section") == "done" for i in items):
        err("E006", "-", "「已完成」至少要有 1 条")

    headline = str(facts.get("headline") or "").strip()
    if not headline:
        err("E007", "-", "缺一句话结论 headline")
    if len(headline) > 40:
        err("E008", "-", "结论 {} 字，超过 40 字".format(len(headline)))

    def nums(s):
        return set(re.findall(r"\d+(?:\.\d+)?", s))

    known = set()
    for it in items:
        known |= nums(str(it.get("text") or "")) | nums(str(it.get("due") or ""))
    for m in facts.get("metrics", []):
        known.add(str(m.get("value")))
    period = facts.get("period", {})
    for k in ("start", "end"):
        known |= nums(str(period.get(k, "")))
    for n in nums(headline):
        if n not in known:
            err("E009", "-", "结论里的数字「{}」在 facts 中找不到来源".format(n))

    if raw is not None:
        terrors = check_trace(facts, raw)
        errors.extend(terrors)
        trace["mismatches"] = len(terrors)

    stats = {
        "items": len(items),
        "by_section": {s: sum(1 for i in items if i.get("section") == s)
                       for s in sorted(SECTIONS)},
        "by_evidence": {e: sum(1 for i in items if i.get("evidence") == e)
                        for e in sorted(EVIDENCE)},
        "metrics": len(facts.get("metrics", [])),
        "headline_chars": len(headline),
    }
    return {"pass": not errors, "errors": errors,
            "warnings": warnings, "stats": stats, "trace": trace}


def lint_views(rendered, views_cfg):
    """渲染后检查各视图字数上限（只告警，不截断正文）。"""
    warnings = []
    for name, text in rendered.items():
        cfg = views_cfg.get("views", {}).get(name, {})
        limit = int(cfg.get("max_chars") or 0)
        if limit and len(text) > limit:
            warnings.append({
                "code": "W003", "view": name,
                "message": "{} {} 字，超过上限 {} 字".format(
                    cfg.get("label", name), len(text), limit),
            })
    return warnings


def main():
    ap = argparse.ArgumentParser(description="校验 facts.json（可逐条溯源）")
    ap.add_argument("facts")
    ap.add_argument("--raw", help="raw_items.json，开启 E015/E016 逐条溯源校验")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    args = ap.parse_args()

    facts = json.loads(Path(args.facts).read_text(encoding="utf-8"))
    raw = json.loads(Path(args.raw).read_text(encoding="utf-8")) if args.raw else None
    result = lint(facts, raw=raw)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        t = result["trace"]
        print("lint: {}  errors={}  warnings={}  trace={}".format(
            "PASS" if result["pass"] else "FAIL",
            len(result["errors"]), len(result["warnings"]),
            "ON ({} 条原文 / {} 处不一致)".format(t["raw_items"], t["mismatches"])
            if t["checked"] else "OFF"))
        for e in result["errors"]:
            print("  [{}] {} {}".format(e["code"], e["item"], e["message"]))
        for w in result["warnings"]:
            print("  [{}] {} {}".format(w["code"], w["item"], w["message"]))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
