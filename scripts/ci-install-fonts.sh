#!/usr/bin/env bash
# CI 字体安装: 下载 Google 可变字体 → fonttools instancer 生成静态实例 → fc-cache
#
# 背景（2026-08-05 血泪）: xdvipdfmx 不支持**可变字体**（报 "Invalid font: -1"），
# 必须用静态 TTF。google/fonts 仓库已全面转向可变字体（static/ 目录 404），
# 故用 fonttools varLib.instancer 把官方可变字体实例化为标准静态 TTF。
# 本地项目 ~/.fonts 里是预装静态字体，无需此脚本。
set -euo pipefail

FONTS_DIR="${HOME}/.fonts"
INST_DIR="/tmp/linotype-fonts"
mkdir -p "$FONTS_DIR" "$INST_DIR"
# fonttools 兼容多种 pip 环境（CI runner / PEP 668 管理的系统 Python）
if ! python3 -c "import fontTools" 2>/dev/null; then
  python3 -m pip install --quiet --break-system-packages fonttools 2>/dev/null \
    || python3 -m pip install --quiet --user fonttools 2>/dev/null \
    || pip install --quiet fonttools
fi

dl() { curl -fsSL -o "$INST_DIR/$1" "https://github.com/google/fonts/raw/main/$2"; }
inst() { python3 -m fontTools.varLib.instancer "$INST_DIR/$1" $2 -o "$FONTS_DIR/$3" > /dev/null 2>&1; }

# Newsreader (wght 200-800 × opsz 6-72; Italic 是单独文件)
dl newsreader.ttf      "ofl/newsreader/Newsreader%5Bopsz%2Cwght%5D.ttf"
dl newsreader-ital.ttf "ofl/newsreader/Newsreader-Italic%5Bopsz%2Cwght%5D.ttf"
inst newsreader.ttf      "opsz=16 wght=400" "Newsreader-Regular.ttf"
inst newsreader.ttf      "opsz=16 wght=600" "Newsreader-SemiBold.ttf"
inst newsreader-ital.ttf "opsz=16 wght=400" "Newsreader-Italic.ttf"

# Playfair Display (wght 400-900)
dl playfair.ttf "ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"
inst playfair.ttf "wght=700" "PlayfairDisplay-Bold.ttf"

# Inter (opsz 14-32 × wght 100-900)
dl inter.ttf "ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf"
inst inter.ttf "opsz=14 wght=400" "Inter-Regular.ttf"
inst inter.ttf "opsz=14 wght=600" "Inter-SemiBold.ttf"

fc-cache -f "$FONTS_DIR"
echo "--- 已注册字体 ---"
fc-list | grep -iE "newsreader|playfair|inter" || { echo "❌ 字体注册失败"; exit 1; }
