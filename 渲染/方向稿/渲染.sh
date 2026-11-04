#!/bin/sh
# 渲染方向稿：sh 渲染.sh A [输出目录]
set -e
cd "$(dirname "$0")"
out=${2:-_out}; mkdir -p "$out"
B=${VIVLIOSTYLE_BROWSER:+--executable-browser $VIVLIOSTYLE_BROWSER}
for f in "$1" "$1-grid"; do
  ../node_modules/.bin/vivliostyle build "$f.html" -o "$out/$f.pdf" --timeout 120 $B >/dev/null
done
echo "$out/$1.pdf"
