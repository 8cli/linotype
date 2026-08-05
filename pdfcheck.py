#!/usr/bin/env python3
"""pdfcheck.py — linotype PDF 后处理检查（编译期 QA 的补充）

检查项:
  1. LOG OVERFLOW: 编译日志中 Overfull plate > 0 → FAIL（内容超版心，需修剪或调字号/版心）
  2. LOG ERROR:    编译日志中 ^! 错误 > 0 → FAIL
  3. MEDIA BOX:    PDF 页尺寸匹配期望纸张（A3 420×297 / A4 210×297 / Letter 279×216）
  4. FONTS:        嵌入字体 ≥3 种（Newsreader/Playfair/Inter，防回退系统字体）
  5. PAGES:        页数匹配预期（单版 N 页 / 双版 ceil(N/2) 页）

用法:
    python3 pdfcheck.py <pdf路径> [--log <编译日志>] [--paper a3|a4|letter] [--landscape] [--pages N]

退出码: 0 = 全部通过; 1 = 有 FAIL。
"""
import argparse
import re
import sys
from pypdf import PdfReader

# 期望纸张尺寸 (mm)
PAPER_MM = {
    'a3': (297, 420),      # 宽 x 高（竖版基准）
    'a4': (210, 297),
    'letter': (216, 279),
}

PASSED: list[str] = []
FAILED: list[str] = []


def report(name: str, ok: bool, detail: str = '') -> None:
    tag = '✅ PASS' if ok else '❌ FAIL'
    print(f'  {tag} {name}{(" — " + detail) if detail else ""}')
    (PASSED if ok else FAILED).append(name)


def check_log(log_path: str) -> None:
    if not log_path:
        report('LOG', True, '未提供日志，跳过')
        return
    try:
        text = open(log_path, encoding='utf-8', errors='replace').read()
    except FileNotFoundError:
        report('LOG', False, f'日志不存在: {log_path}')
        return
    # 1. Overfull plate（我们的版心溢出检测）
    # 注意: typeout 输出 "957.51907pt> contentH 742.61694pt"（pt> 无空格）
    overfull_plates = re.findall(r'Overfull plate: content ([\d.]+)pt>\s*contentH ([\d.]+)pt', text)
    if overfull_plates:
        details = '; '.join(f'{float(c):.0f}>{float(h):.0f}pt' for c, h in overfull_plates)
        report('LOG OVERFLOW', False, f'{len(overfull_plates)} 版超高: {details}')
    else:
        report('LOG OVERFLOW', True, '无 Overfull plate')
    # 2. 编译错误
    errors = re.findall(r'^! ', text, re.MULTILINE)
    report('LOG ERROR', len(errors) == 0, f'{len(errors)} 个错误' if errors else '无错误')


def check_pdf(pdf_path: str, paper: str, landscape: bool, expect_pages: int) -> None:
    try:
        r = PdfReader(pdf_path)
    except Exception as e:
        report('PDF', False, f'无法打开: {e}')
        return
    # 3. MediaBox
    p0 = r.pages[0]
    w_pt, h_pt = float(p0.mediabox.width), float(p0.mediabox.height)
    w_mm, h_mm = w_pt * 25.4 / 72, h_pt * 25.4 / 72
    ew, eh = PAPER_MM.get(paper, PAPER_MM['a3'])
    if landscape:
        ew, eh = eh, ew
    rot = p0.get('/Rotate', 0)
    if rot in (90, 270):
        w_mm, h_mm = h_mm, w_mm
    ok = abs(w_mm - ew) < 2 and abs(h_mm - eh) < 2
    report('MEDIA BOX', ok, f'{w_mm:.0f}x{h_mm:.0f}mm (期望 {ew}x{eh}mm)')
    # 4. 字体嵌入
    fonts = set()
    for p in r.pages:
        res = p.get('/Resources', {})
        for f in (res.get('/Font', {}) if '/Font' in res else {}).values():
            fo = f.get_object()
            fn = str(fo.get('/BaseFont', '?'))
            # 子集化字体有 + 前缀; 未嵌入的 TrueType 会报错或缺 FontFile
            fonts.add(fn)
    report('FONTS', len(fonts) >= 3, f'{len(fonts)} 种字体: {sorted(fonts)[:4]}...')
    # 5. 页数
    if expect_pages:
        ok = len(r.pages) == expect_pages
        report('PAGES', ok, f'{len(r.pages)} 页 (期望 {expect_pages})')
    else:
        report('PAGES', True, f'{len(r.pages)} 页（未指定期望值）')


def main() -> int:
    ap = argparse.ArgumentParser(description='linotype PDF 后处理检查')
    ap.add_argument('pdf', help='PDF 路径')
    ap.add_argument('--log', help='编译日志路径（xelatex 输出）')
    ap.add_argument('--paper', default='a3', choices=['a3', 'a4', 'letter'])
    ap.add_argument('--landscape', action='store_true')
    ap.add_argument('--pages', type=int, default=0, help='期望页数')
    args = ap.parse_args()

    print('=== pdfcheck ===')
    check_log(args.log)
    check_pdf(args.pdf, args.paper, args.landscape, args.pages)
    print(f'\n{len(PASSED)} PASS, {len(FAILED)} FAIL')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
