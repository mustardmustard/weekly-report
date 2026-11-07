#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""figure_helper.py — 让 matplotlib 正确渲染中文标签。

matplotlib 默认没有 CJK 字体，中文轴标签会变成方块。画图前先调用 setup_cjk()，
它会自动挑本机实际存在的中文字体并套上适合双栏论文的简洁样式。

    from figure_helper import setup_cjk
    setup_cjk()
    import matplotlib.pyplot as plt
    ...
    plt.savefig("fig1.png", dpi=300, bbox_inches="tight")

与 goushi-writing 的同名助手一致，此处自带一份，保证 weekly-report 目录可独立复制。
"""
from matplotlib import font_manager as _fm
import matplotlib as _mpl

_CJK_PREF = [
    "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", "STSong",
    "Noto Sans CJK SC", "PingFang SC", "Hiragino Sans GB",
    "Arial Unicode MS", "STHeiti", "Heiti SC", "SimHei", "SimSun",
    "Microsoft YaHei", "WenQuanYi Zen Hei",
]


def available_cjk_font():
    """返回第一个已安装的中文字体名，找不到返回 None。"""
    installed = {f.name for f in _fm.fontManager.ttflist}
    for name in _CJK_PREF:
        if name in installed:
            return name
    for f in _fm.fontManager.ttflist:
        if any(k in f.name for k in ("CJK", "Song", "Hei", "Ming", "YaHei", "PingFang", "Gothic")):
            return f.name
    return None


def setup_cjk(base_size: int = 9):
    """配置 matplotlib：中文字体 + 干净的双栏图表样式。返回选中的字体名。"""
    font = available_cjk_font()
    rc = {
        "font.size": base_size,
        "axes.unicode_minus": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.alpha": 0.25,
        "grid.linewidth": 0.5,
        "axes.linewidth": 0.8,
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "legend.frameon": False,
    }
    if font:
        rc["font.sans-serif"] = [font, "DejaVu Sans"]
        rc["font.serif"] = [font, "DejaVu Serif"]
        rc["font.family"] = "sans-serif"
    _mpl.rcParams.update(rc)
    return font


if __name__ == "__main__":
    print("CJK font selected:", setup_cjk() or "(none found - use English labels)")
