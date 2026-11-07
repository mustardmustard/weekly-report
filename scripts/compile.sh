#!/usr/bin/env bash
#
# compile.sh <report.tex> [output_dir]
#
# 用 XeLaTeX 把周报 .tex 编译成 IEEEtran 双栏 PDF（与 goushi-writing 同款自愈逻辑）：
#   1. xelatex 不在 PATH 时，去 TinyTeX / MacTeX / TeX Live 常见位置找
#   2. 把模板硬编码的 Noto CJK 字体替换为本机实际存在的中文字体
#   3. 缺宏包时用 tlmgr 自动补装，重试编译
#   4. 多趟编译解交叉引用，PDF 落到 .tex 同目录
#
# 源 .tex 永不修改，所有补丁只作用于 .build/ 副本。
# 退出码：0 成功 · 1 参数错 · 2 找不到 XeLaTeX · 3 编译失败
#
# 本机没有 XeLaTeX 时不要调用本脚本：build_pdf.py 会自动降级到
# Chrome / Edge headless 打印等效双栏 HTML；.tex 可直接丢进 Overleaf（编译器选 XeLaTeX）。

set -uo pipefail

TEX="${1:-}"
[ -n "$TEX" ] && [ -f "$TEX" ] || { echo "usage: compile.sh <report.tex> [output_dir]"; exit 1; }
TEXDIR="$(cd "$(dirname "$TEX")" && pwd)"
TEXNAME="$(basename "$TEX")"
STEM="${TEXNAME%.tex}"
OUTDIR="${2:-$TEXDIR}"
mkdir -p "$OUTDIR"

# 1. 定位工具链 -------------------------------------------------------------
if ! command -v xelatex >/dev/null 2>&1; then
  for d in "$HOME/Library/TinyTeX/bin/"*/ /usr/local/texlive/*/bin/*/ /Library/TeX/texbin ~/.TinyTeX/bin/*/; do
    if [ -x "$d/xelatex" ]; then export PATH="$d:$PATH"; break; fi
  done
fi
command -v xelatex >/dev/null 2>&1 || {
  echo "✗ XeLaTeX 不可用。请把 .tex 交给 Overleaf（编译器选 XeLaTeX），"
  echo "  或安装 TinyTeX (https://yihui.org/tinytex/)。"
  exit 2
}
TLMGR="$(command -v tlmgr || true)"

# 2. 隔离构建目录 -----------------------------------------------------------
BUILD="$TEXDIR/.build_$STEM"
rm -rf "$BUILD"; mkdir -p "$BUILD"
cp "$TEX" "$BUILD/$STEM.tex"
for ext in png jpg jpeg pdf eps bib; do
  for f in "$TEXDIR"/*."$ext"; do [ -e "$f" ] && cp "$f" "$BUILD/" 2>/dev/null; done
done

# 3. 中文字体降级 -----------------------------------------------------------
font_available() { fc-match "$1" 2>/dev/null | grep -qiF "\"$1\""; }
pick_font() {
  for f in "$@"; do
    if font_available "$f"; then echo "$f"; return; fi
  done
  echo "$1"
}
SERIF="$(pick_font 'Noto Serif CJK SC' 'Source Han Serif SC' 'Songti SC' 'STSong' 'SimSun' 'PingFang SC')"
SANS="$(pick_font  'Noto Sans CJK SC'  'Source Han Sans SC'  'PingFang SC' 'STHeiti' 'SimHei')"
MONO="$(pick_font  'Noto Sans Mono CJK SC' 'Sarasa Mono SC' 'PingFang SC' 'SimHei')"
sed -i.bak \
  -e "s/\\\\setCJKmainfont{[^}]*}/\\\\setCJKmainfont{$SERIF}/" \
  -e "s/\\\\setCJKsansfont{[^}]*}/\\\\setCJKsansfont{$SANS}/" \
  -e "s/\\\\setCJKmonofont{[^}]*}/\\\\setCJKmonofont{$MONO}/" \
  "$BUILD/$STEM.tex"
rm -f "$BUILD/$STEM.tex.bak"
echo "→ CJK fonts: main=$SERIF | sans=$SANS | mono=$MONO"

# 4. 编译 + 缺包自愈 --------------------------------------------------------
cd "$BUILD"
XEL=(xelatex -interaction=nonstopmode -halt-on-error "$STEM.tex")
ok=0
for attempt in $(seq 1 10); do
  if "${XEL[@]}" > compile.log 2>&1; then ok=1; break; fi
  miss="$(grep -oE "File \`[^']+\.(sty|cls|def)' not found" compile.log | head -1 | sed -E "s/File \`([^']+)'.*/\1/")"
  if [ -z "$miss" ]; then
    miss="$(grep -oE "the language definition file [^ ]+\.ldf" compile.log | head -1 | awk '{print $NF}')"
  fi
  if [ -n "$miss" ] && [ -n "$TLMGR" ]; then
    pkg="$("$TLMGR" search --global --file "/$miss" 2>/dev/null | grep -E ':[[:space:]]*$' | head -1 | sed 's/:.*//' | tr -d ' ')"
    if [ -n "$pkg" ]; then
      echo "→ installing missing package: $pkg (provides $miss)"
      "$TLMGR" install "$pkg" >/dev/null 2>&1 && continue
    fi
  fi
  break
done

if [ "$ok" -ne 1 ]; then
  echo "✗ Compile failed. Last errors:"
  grep -iE "^!|not found|Undefined|Emergency" compile.log | head -12
  echo "  (full log: $BUILD/compile.log)"
  exit 3
fi
"${XEL[@]}" > compile.log 2>&1
"${XEL[@]}" > compile.log 2>&1

# 5. 交付 -------------------------------------------------------------------
if [ -f "$STEM.pdf" ]; then
  cp "$STEM.pdf" "$OUTDIR/$STEM.pdf"
  echo "✓ PDF ready: $OUTDIR/$STEM.pdf ($(wc -c < "$STEM.pdf" | tr -d ' ') bytes)"
  rm -rf "$BUILD"
  exit 0
else
  echo "✗ No PDF produced despite exit 0 - see $BUILD/compile.log"
  exit 3
fi
