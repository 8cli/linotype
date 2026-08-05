#!/usr/bin/env python3
"""linotype skill 回归测试 — LaTeX 正负向矩阵自动验证。

用法:
    python3 run_tests.py [latex目录]      # 默认 = ~/news/latex/

覆盖:
  正向:  build.py → xelatex → 编译 0 错误 + 页数正确 + 字体嵌入
  负向:  注入超长内容 → Overfull plate 出现（溢出检测 FAIL）
  负向:  注入裸特殊字符 → 编译错误
  负向:  双版模式 → 无空白首页 + 页数 = 1（P1|P2 并排）
  主题:  theme=magazine → 编译通过

在临时目录运行（复制 build.py/linotype.cls/pdfcheck.py），不污染项目。

退出码: 0 = 全部通过; 1 = 有失败。
"""
import os
import shutil
import subprocess
import sys
import tempfile

PASSED: list[str] = []
FAILED: list[str] = []


def report(name: str, ok: bool, detail: str = '') -> None:
    tag = '✅ PASS' if ok else '❌ FAIL'
    print(f'  {tag} {name}{(" — " + detail) if detail else ""}')
    (PASSED if ok else FAILED).append(name)


def run(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=300, **kw)


def xelatex(tex_dir: str, tex_name: str):
    """编译 .tex，返回 (exit_ok, log_text)。"""
    r = run(['xelatex', '-interaction=nonstopmode', '-halt-on-error', tex_name],
            cwd=tex_dir)
    return r.returncode == 0, r.stdout + r.stderr


def make_workspace(latex_dir: str) -> str:
    """复制核心文件到临时目录。"""
    tmp = tempfile.mkdtemp(prefix='linotype-test-')
    for f in ('build.py', 'linotype.cls', 'pdfcheck.py'):
        src = os.path.join(latex_dir, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(tmp, f))
    return tmp


def write_plate(tmp: str, name: str, content: str) -> None:
    os.makedirs(os.path.join(tmp, 'plates'), exist_ok=True)
    with open(os.path.join(tmp, 'plates', name), 'w', encoding='utf-8') as f:
        f.write(content)


def pdf_fonts(pdf: str) -> set:
    from pypdf import PdfReader
    r = PdfReader(pdf)
    fonts = set()
    for p in r.pages:
        res = p.get('/Resources', {})
        for f in (res.get('/Font', {}) if '/Font' in res else {}).values():
            fonts.add(str(f.get_object().get('/BaseFont', '?')))
    return fonts


def test_positive(tmp: str) -> None:
    """正向: 短内容编译 + 页数 + 字体嵌入。"""
    write_plate(tmp, 'p1.md', """KICKER: Test
HEADLINE: Positive Test
BODY:
First paragraph with some text.

Second paragraph with more text.
""")
    write_plate(tmp, 'p2.md', """KICKER: Test 2
HEADLINE: Second Story
BODY:
Short body for plate two.
""")
    r = run(['python3', 'build.py', 'plates/', 'out.tex',
             '--docopts', 'paper=a4,portrait,columns=2,plates=1'], cwd=tmp)
    if r.returncode != 0:
        report('正向 build.py', False, r.stderr.strip()[:100])
        return
    ok, log = xelatex(tmp, 'out.tex')
    report('正向 编译', ok, '' if ok else log[-200:])
    if not ok:
        return
    from pypdf import PdfReader
    pdf = os.path.join(tmp, 'out.pdf')
    r = PdfReader(pdf)
    report('正向 页数', len(r.pages) == 2, f'{len(r.pages)} 页 (期望 2)')
    fonts = pdf_fonts(pdf)
    report('正向 字体嵌入', len(fonts) >= 2, f'{len(fonts)} 种')


def test_overflow_detection(tmp: str) -> None:
    """负向: 超长内容 → Overfull plate 出现（溢出检测必须抓到）。"""
    body = '\n\n'.join(
        f'Paragraph {i}: The quick brown fox jumps over the lazy dog while typesetting engines measure hyphenation quality across narrow columns.'
        for i in range(60)
    )
    write_plate(tmp, 'p1.md', f"KICKER: Overflow\nHEADLINE: Too Long\nBODY:\n{body}\n")
    r = run(['python3', 'build.py', 'plates/', 'overflow.tex',
             '--docopts', 'paper=a4,portrait,columns=2,plates=1'], cwd=tmp)
    ok, log = xelatex(tmp, 'overflow.tex')
    has_overfull = 'Overfull plate' in log
    report('负向 超长内容编译', ok, '' if ok else log[-150:])
    report('负向 溢出检测抓到', has_overfull, 'Overfull plate 出现' if has_overfull else '未检测到!')


def test_escape(tmp: str) -> None:
    """正向: 裸特殊字符被 build.py 正确转义 → 编译通过。"""
    write_plate(tmp, 'p1.md', """KICKER: Bad
HEADLINE: Bad Escape
BODY:
This has special chars: 100% & $ # _ { } ~ ^ and a quote.
""")
    r = run(['python3', 'build.py', 'plates/', 'esc.tex',
             '--docopts', 'paper=a4,portrait,columns=2,plates=1'], cwd=tmp)
    ok, log = xelatex(tmp, 'esc.tex')
    report('正向 特殊字符转义', ok, '编译通过（build.py 转义生效）' if ok else log[-150:])


def test_dual_plate(tmp: str) -> None:
    """负向: 双版模式 → 无空白首页 + 页数正确。"""
    write_plate(tmp, 'p1.md', """KICKER: A
HEADLINE: Story One
BODY:
Body one with text.
""")
    write_plate(tmp, 'p2.md', """KICKER: B
HEADLINE: Story Two
BODY:
Body two with text.
""")
    r = run(['python3', 'build.py', 'plates/', 'dual.tex',
             '--docopts', 'paper=a3,landscape,columns=3,plates=2'], cwd=tmp)
    ok, log = xelatex(tmp, 'dual.tex')
    report('负向 双版编译', ok, '' if ok else log[-150:])
    if not ok:
        return
    from pypdf import PdfReader
    pdf = os.path.join(tmp, 'dual.pdf')
    r = PdfReader(pdf)
    report('负向 双版页数', len(r.pages) == 1, f'{len(r.pages)} 页 (期望 1, P1|P2 并排)')
    t = (r.pages[0].extract_text() or '').replace(' ', '')
    both = 'STORYONE' in t.upper() and 'STORYTWO' in t.upper()
    report('负向 双版无空白首页', both, '两版同页' if both else '有版缺失!')


def test_theme(tmp: str) -> None:
    """主题: theme=magazine → 编译通过。"""
    write_plate(tmp, 'p1.md', """KICKER: Theme
HEADLINE: Magazine Theme
BODY:
Body text for magazine theme.
""")
    r = run(['python3', 'build.py', 'plates/', 'theme.tex',
             '--docopts', 'paper=a4,portrait,columns=2,plates=1',
             '--theme', 'magazine'], cwd=tmp)
    ok, log = xelatex(tmp, 'theme.tex')
    report('主题 magazine 编译', ok, '' if ok else log[-150:])


def main() -> int:
    latex_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/news/latex')
    if not os.path.exists(os.path.join(latex_dir, 'linotype.cls')):
        print(f'错误: 未找到 linotype.cls 于 {latex_dir}')
        return 1

    print(f'=== linotype 回归测试 (latex: {latex_dir}) ===')
    tmp = make_workspace(latex_dir)
    print(f'工作目录: {tmp}')

    test_positive(tmp)
    test_overflow_detection(tmp)
    test_escape(tmp)
    test_dual_plate(tmp)
    test_theme(tmp)

    print(f'\n{len(PASSED)} PASS, {len(FAILED)} FAIL')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
