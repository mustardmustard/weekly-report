#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scaffold_facts.py — raw_items.json → facts.json 草稿。

整理层的机械部分：只做归栏目、搬运来源、标 evidence，绝不新增事实。
text 保持采集原文；owner 只有采集阶段就带得出来的才填；
next_action / due / headline 一律留空，交给 lint 明确报出来让人补。

  python scaffold_facts.py output/raw_items.json --out output/facts.json
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lint as L


def main():
    ap = argparse.ArgumentParser(description="raw_items.json → facts.json 草稿")
    ap.add_argument("raw")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
    items = []
    for r in raw.get("items", []):
        src = r.get("source") or []
        items.append({
            "id": r.get("id"),
            "section": r.get("kind", "done"),
            "text": r.get("text", ""),
            "owner": r.get("owner") or r.get("author") or "",
            "next_action": "",
            "due": "",
            "blocked": r.get("kind") == "risk",
            "evidence": "fact" if src else "unconfirmed",
            "source": src,
            "date": r.get("date", ""),
            "internal_refs": [],
        })

    facts = {
        "schema_version": "1.0",
        "demo": bool(raw.get("demo")),
        "period": raw.get("period", {}),
        "author": raw.get("author", ""),
        "headline": "",
        "items": items,
        "metrics": raw.get("metrics", []),
        "questions": [],
        "generated_from": raw.get("generated_from", []),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    result = L.lint(facts, raw=raw)
    print("facts.json 草稿 →", out)
    print("  搬运条目：{} 条（text 原样，未改写）".format(len(items)))
    print("  溯源：{}/{} 条与采集原文一致（E015/E016 应为 0）".format(
        len(items) - result["trace"]["mismatches"], len(items)))
    print("  待补：headline 1 处；lint 报出 {} 个 error / {} 个 warning".format(
        len(result["errors"]), len(result["warnings"])))
    print("  下一步：补齐结论、owner、next_action、due，再跑 build_report.py")
    if result["errors"]:
        codes = {}
        for e in result["errors"]:
            codes[e["code"]] = codes.get(e["code"], 0) + 1
        print("  待补分布：" + "、".join(
            "{}={}".format(k, v) for k, v in sorted(codes.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
