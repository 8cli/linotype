#!/usr/bin/env python3
"""
linotype pixelcheck — 像素级版面空白检测

audit.js 的 FILL 只检查"最深油墨位置"，会漏掉列内空白带（例如多列 balance
后最后一列底部悬空）。本工具对渲染出的页面截图做逐列墨量分析，
找出"看起来排满、实际有空白带"的列。

感知 A3 双版布局：A3 横版页面左半=P1、右半=P4（或 P2/P3）。每半版先
自动检测布局类型（--layout auto）：

- 单栏堆叠布局（P1）: 通栏报头/标题/摘要/署名自上而下堆叠，后接 3 栏
  CSS-balanced 正文与通栏引语/简报。标题、摘要末行左对齐，右侧存在局部
  白空（~87-101mm、~116-128mm），但栏间无贯穿到底的白线 → 按 1 栏分析
  （无假阳性）。
- 多栏网格布局（P2/P3/P4）: 主栏(网格列 1-2) + 侧栏(网格列 3)，栏间有
  固定垂直白沟（3.75mm，x=133.75-137.5mm）自页头下方贯穿到底 → 按
  --cols 栏分析。

检测方式: 在每半版的内容区（已去 15mm 左右边距）等分处取 1.5mm 半宽竖条，
自上而下按 2mm 分段；若任一栏间边界竖条的空带比例 ≥ 0.9（即存在贯穿栏间
白线），判定为多栏网格，否则为单栏堆叠。

用法:
    python3 pixelcheck.py front.png            # A3 双版, 左右各 3 栏, 20-281mm, 自动检测
    python3 pixelcheck.py front.png --half left   # 只看左半版
    python3 pixelcheck.py page.png --cols 4    # 单版页改 4 栏
    python3 pixelcheck.py page.png --full      # 整页当一版分析 (非 A3 双版)
    python3 pixelcheck.py front.png --layout single  # 强制单栏堆叠分析
    python3 pixelcheck.py front.png --layout multi   # 强制多栏网格分析

参数:
    --half {both,left,right}  分析哪半版 (默认 both; --full 时忽略)
    --full                    整页当单版分析, 忽略半版划分
    --pxmm FLOAT              像素/毫米换算 (默认 3.545, 1489px/420mm)
    --cols INT                每版列数 (默认 3)
    --layout {auto,single,multi}  布局检测 (默认 auto):
        auto    逐版检测: 栏间边界竖条空带比例 ≥ 0.9 → 多栏; 否则单栏
        single  强制 1 栏分析 (通栏堆叠版式)
        multi   强制按 --cols 栏分析 (网格版式)
    --bands INT               空白带分析粒度 mm (默认 5)
    --ink FLOAT               判定"有墨"阈值, 带内墨比例 > 阈值视为有内容 (默认 0.005)
    --top FLOAT               分析起点 mm (默认 20, 内容区上缘)
    --bottom FLOAT            分析终点 mm (默认 281, 内容区底界)
    --min-gap FLOAT           报告的最小空白带长度 mm (默认 8)

注: 多栏等分基于每半版的内容区（已去 15mm 左右边距），因此栏位约为
15-75/75-135/135-195mm（此前是 0-70/70-140/140-210mm）。若真实栏数与
--cols 不符（例如 2 栏版式用了默认 --cols 3），栏位会错位 — 请用 --cols
指定实际栏数。空页回退为单栏（无空白带 → PASS）。
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image


def dark_mask(a: np.ndarray) -> np.ndarray:
    """RGBA 数组 → 布尔掩码: alpha>=200 且 0.2126r+0.7152g+0.0722b < 150 的深色像素。"""
    r = a[..., 0]
    g = a[..., 1]
    b = a[..., 2]
    alpha = a[..., 3] if a.shape[2] >= 4 else np.full(a.shape[:2], 255.0)
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return (alpha >= 200) & (lum < 150)


def content_extent(a: np.ndarray, x0_px: int, x1_px: int,
                   top_px: int, bot_px: int) -> tuple:
    """扫描 [x0_px, x1_px) 内实际有墨的 x 范围, 返回 (cx0, cx1)。

    某 x 列在 top_px..bot_px 内累计 ≥2 个深色像素即算"有墨"; 同时要求该列
    至少一侧相邻列也有墨, 以滤掉孤立的 1px 竖线（如版面中线折痕/裁切线）。
    cx0 = 首个有墨列, cx1 = 末个有墨列 + 1; 全空白时回退 (x0_px, x1_px)。
    """
    dark = dark_mask(a)
    ink = dark[top_px:bot_px, x0_px:x1_px].sum(axis=0) >= 2
    neighbor = np.zeros_like(ink)
    neighbor[1:] |= ink[:-1]
    neighbor[:-1] |= ink[1:]
    ink = ink & neighbor
    xs = np.flatnonzero(ink)
    if xs.size == 0:
        return x0_px, x1_px
    return x0_px + int(xs[0]), x0_px + int(xs[-1]) + 1


def detect_layout(a: np.ndarray, cx0_px: int, cx1_px: int, top_px: int, bot_px: int,
                  pxmm: float, cols: int) -> str:
    """检测 [cx0_px, cx1_px) 内容区是"多栏网格"还是"单栏堆叠"布局。

    对每个内部栏间边界 (1..cols-1 等分处) 取 1.5mm 半宽竖条, 自 top_px
    到 bot_px 按 2mm 分段; 若某边界竖条的空带比例 ≥ 0.9 (贯穿栏间白线)
    → "multi", 否则 "single"。空区（无任何油墨）→ "single"。
    """
    if cols <= 1 or cx1_px - cx0_px <= 0:
        return "single"
    dark = dark_mask(a)
    if not dark[top_px:bot_px, cx0_px:cx1_px].any():
        return "single"  # 空版: 无内容亦无栏间白线
    half_px = max(1, int(1.5 * pxmm))
    band_px = max(1, int(2.0 * pxmm))
    for c in range(1, cols):
        boundary_px = cx0_px + (cx1_px - cx0_px) * c / cols
        s0 = int(boundary_px - half_px)
        s1 = int(boundary_px + half_px) + 1
        if s1 <= s0:
            s1 = s0 + 1
        strip = dark[top_px:bot_px, s0:s1]
        total = 0
        empty = 0
        for y0 in range(0, strip.shape[0], band_px):
            total += 1
            if not strip[y0:y0 + band_px].any():
                empty += 1
        if total > 0 and empty / total >= 0.9:
            return "multi"
    return "single"


def load_layout(path: str):
    """读取 layout.json (audit.js 输出: {sheets:{front:[p1,p4],back:[p2,p3]}, layout:{p1:'single',...}})。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def resolve_layout(args, zone_name: str):
    """auto 模式下从 layout.json 解析该半版的布局类型; 返回 ('single'|'multi'|None, 来源说明)。

    layout.json 由 audit.js 用 DOM 语义判断生成 (P1 lead-cols 堆叠→single; P2-P4 aside-col 网格→multi),
    比像素 white_fraction 启发式可靠——消除了 P4 文字渗入 gutter 导致误判单栏的缺陷。
    """
    if args.layout_file:
        path = args.layout_file
    else:
        stem = os.path.splitext(os.path.basename(args.image))[0]
        path = os.path.join(os.path.dirname(os.path.abspath(args.image)), "layout.json")
    data = load_layout(path)
    if not data:
        return None, "像素启发式(layout.json 缺失)"
    sheets = data.get("sheets", {})
    layout = data.get("layout", {})
    stem = os.path.splitext(os.path.basename(args.image))[0]
    if stem not in sheets or zone_name not in ("左半版", "右半版"):
        return None, "像素启发式(无匹配布局表)"
    idx = 0 if zone_name == "左半版" else 1
    plates = sheets[stem]
    if idx >= len(plates):
        return None, "像素启发式(布局表缺版)"
    pid = plates[idx]
    val = layout.get(pid)
    if val not in ("single", "multi"):
        return None, f"像素启发式({pid} 布局未知)"
    return val, f"layout.json[{pid}]"


def analyze(a: np.ndarray, x0_px: int, x1_px: int, top_px: int, bot_px: int,
            pxmm: float, cols: int, bands_mm: int, ink_th: float,
            min_gap: float) -> list:
    """分析 [x0_px, x1_px) 区域内按 cols 栏划分的空白带。返回 (列, 起mm, 止mm, 长mm) 列表。"""
    col_w_px = (x1_px - x0_px) / cols
    band_px = max(1, int(bands_mm * pxmm))
    band_ink = ink_th * bands_mm  # 5mm 带内的墨比例阈值
    issues = []
    for c in range(cols):
        x0 = x0_px + int(c * col_w_px)
        x1 = x0_px + int((c + 1) * col_w_px)
        gap_start = None
        for y in range(top_px, bot_px, band_px):
            band = a[y : y + band_px, x0:x1]
            if band.size == 0:
                continue
            ratio = (band < 1.0).mean()
            mm = y / pxmm
            if ratio <= band_ink:
                if gap_start is None:
                    gap_start = mm
            else:
                if gap_start is not None and mm - gap_start >= min_gap:
                    issues.append((c, gap_start, mm, mm - gap_start))
                gap_start = None
        if gap_start is not None and bot_px / pxmm - gap_start >= min_gap:
            issues.append((c, gap_start, bot_px / pxmm, bot_px / pxmm - gap_start))
    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--half", choices=["both", "left", "right"], default="both")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--pxmm", type=float, default=3.545)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--layout", choices=["auto", "single", "multi"], default="auto")
    ap.add_argument("--bands", type=int, default=5)
    ap.add_argument("--ink", type=float, default=0.005)
    ap.add_argument("--top", type=float, default=20.0)
    ap.add_argument("--bottom", type=float, default=281.0)
    ap.add_argument("--min-gap", type=float, default=8.0)
    ap.add_argument("--layout-file", default=None,
                    help="audit.js 输出的 layout.json 路径 (默认自动探测 image 同目录; auto 模式优先于像素启发式)")
    args = ap.parse_args()

    img = Image.open(args.image).convert("RGBA")
    rgba = np.asarray(img).astype(np.float32)
    gray = np.asarray(img.convert("L")).astype(np.float32) / 255.0
    h, w = gray.shape
    pxmm = args.pxmm
    top_px, bot_px = int(args.top * pxmm), int(args.bottom * pxmm)
    print(f"页面 {w}x{h}px = {w/pxmm:.1f}x{h/pxmm:.1f}mm, 每版 {args.cols} 栏, "
          f"分析 {args.top}-{args.bottom}mm")

    zones = []
    if args.full:
        zones = [("整页", 0, w)]
    else:
        half = w // 2
        if args.half in ("both", "left"):
            zones.append(("左半版", 0, half))
        if args.half in ("both", "right"):
            zones.append(("右半版", half, w))

    all_issues = []
    for name, x0, x1 in zones:
        cx0, cx1 = content_extent(rgba, x0, x1, top_px, bot_px)
        blank = not dark_mask(rgba)[top_px:bot_px, cx0:cx1].any()
        src = ""
        if blank:
            det, eff_cols = "single", 1
        elif args.layout == "single":
            det, eff_cols = "single", 1
        elif args.layout == "multi":
            det, eff_cols = "multi", args.cols
        else:
            # auto: 优先 layout.json (DOM 语义), 缺失/不匹配时回退像素启发式
            det, src = resolve_layout(args, name)
            if det is None:
                det = detect_layout(rgba, cx0, cx1, top_px, bot_px, pxmm, args.cols)
            eff_cols = 1 if det == "single" else args.cols
        if det == "single":
            print(f"  → 检测为单栏堆叠布局，使用 1 栏分析{('（' + src + '）') if src else ''}")
        else:
            print(f"  → 检测为多栏网格布局，使用 {eff_cols} 栏分析{('（' + src + '）') if src else ''}")
        if blank:
            print(f"[PASS] {name}: 各列在 {args.top}–{args.bottom}mm 内无空白带")
            continue
        issues = analyze(gray, cx0, cx1, top_px, bot_px, pxmm, eff_cols,
                         args.bands, args.ink, args.min_gap)
        if issues:
            print(f"[FAIL] {name}: {len(issues)} 处列内空白带 (>= {args.min_gap}mm):")
            for c, s, e, g in issues:
                print(f"  列{c+1}: {s:.1f}–{e:.1f}mm (空白 {g:.1f}mm)")
            all_issues.extend(issues)
        else:
            print(f"[PASS] {name}: 各列在 {args.top}–{args.bottom}mm 内无空白带")

    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main())
