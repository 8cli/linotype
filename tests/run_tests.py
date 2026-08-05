#!/usr/bin/env python3
"""linotype skill 回归测试 — LaTeX 正负向矩阵自动验证。

用法:
    python3 run_tests.py [latex目录]      # 默认 = ~/news/latex/

覆盖:
  正向:  build.py --no-autofit → xelatex → 编译 0 错误 + 页数正确 + 字体嵌入
  负向:  注入超长内容 → Overfull plate 出现（溢出检测 FAIL）
  负向:  注入裸特殊字符 → 编译错误
  负向:  双版模式 → 无空白首页 + 页数 = 1（P1|P2 并排）
  主题:  theme=magazine → 编译通过
  autofit: 溢出收敛 / 太空提升 / 边界失败 / --no-autofit 纯生成

在临时目录运行（复制 build.py/linotype.cls/pdfcheck.py），不污染项目。

退出码: 0 = 全部通过; 1 = 有失败。
"""
import os
import re
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
             '--docopts', 'paper=a4,portrait,columns=2,plates=1', '--no-autofit'], cwd=tmp)
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
             '--docopts', 'paper=a4,portrait,columns=2,plates=1', '--no-autofit'], cwd=tmp)
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
             '--docopts', 'paper=a4,portrait,columns=2,plates=1', '--no-autofit'], cwd=tmp)
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
             '--docopts', 'paper=a3,landscape,columns=3,plates=2', '--no-autofit'], cwd=tmp)
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
             '--theme', 'magazine', '--no-autofit'], cwd=tmp)
    ok, log = xelatex(tmp, 'theme.tex')
    report('主题 magazine 编译', ok, '' if ok else log[-150:])


def _long_body(n: int) -> str:
    return '\n\n'.join(
        f'Paragraph {i}: The quick brown fox jumps over the lazy dog while typesetting engines measure hyphenation quality across narrow columns.'
        for i in range(n))


def _run_autofit(tmp: str, body: str, docopts: str, out: str):
    """运行 build.py（默认 autofit），返回 (exit_code, stdout)。

    用独立 plates 目录（af_plates/）——共享 plates/ 会被其他测试的
    残留 p*.md 污染（build.py 读目录内所有 .md，污染导致 fill 误判）。
    """
    af_dir = os.path.join(tmp, 'af_plates')
    os.makedirs(af_dir, exist_ok=True)
    for f in os.listdir(af_dir):
        os.remove(os.path.join(af_dir, f))
    with open(os.path.join(af_dir, 'p1.md'), 'w', encoding='utf-8') as f:
        f.write(f'KICKER: Auto\nHEADLINE: Autofit Test\nBODY:\n{body}\n')
    r = run(['python3', 'build.py', af_dir, out,
             '--docopts', docopts], cwd=tmp)
    return r.returncode, r.stdout + r.stderr


def test_autofit_overflow(tmp: str) -> None:
    """autofit 溢出收敛: 超长内容 → 自动缩字号/增栏数 → 0 Overfull + 收敛。"""
    code, out = _run_autofit(tmp, _long_body(50),
                             'paper=a4,portrait,columns=3,plates=1', 'af_over.tex')
    report('autofit 溢出收敛(退出码0)', code == 0, f'exit={code}')
    report('autofit 溢出收敛(报告)', '✅ 收敛' in out,
           '找到收敛' if '✅ 收敛' in out else out[-200:])
    if os.path.exists(os.path.join(tmp, 'af_over.log')):
        log = open(os.path.join(tmp, 'af_over.log'), encoding='utf-8').read()
        report('autofit 溢出收敛(0 Overfull)', 'Overfull plate' not in log,
               '无溢出' if 'Overfull plate' not in log else '仍有溢出!')


def test_autofit_sparse(tmp: str) -> None:
    """autofit 太空: 极短内容 → 增大字号/减栏数 → fill 提升或边界接受（不崩溃）。"""
    body = '\n\n'.join('Short paragraph number %d.' % i for i in range(2))
    code, out = _run_autofit(tmp, body,
                             'paper=a4,portrait,columns=4,plates=1', 'af_sparse.tex')
    report('autofit 太空(不崩溃)', code == 0, f'exit={code}')
    report('autofit 太空(调整发生)', ('bodyfontsize=11pt' in out or 'columns=2' in out),
           '已调字号/栏数' if ('bodyfontsize=11pt' in out or 'columns=2' in out) else out[-150:])
    report('autofit 太空(有界接受)', '接受当前配置' in out or '✅ 收敛' in out,
           '边界接受' if '接受当前配置' in out else ('收敛' if '✅ 收敛' in out else out[-150:]))


def test_autofit_boundary(tmp: str) -> None:
    """autofit 边界失败: 极长内容 → 到达边界 → 明确失败报告（不崩溃）。"""
    code, out = _run_autofit(tmp, _long_body(120),
                             'paper=a4,portrait,columns=2,plates=1', 'af_bound.tex')
    report('autofit 边界(明确失败)', code == 1 and '边界内无法放下' in out,
           f'exit={code}' if code == 1 else f'exit={code}, {out[-150:]}')
    report('autofit 边界(报告最优)', '最低溢出尝试' in out or '历史最佳' in out,
           '有最优报告' if ('最低溢出尝试' in out or '历史最佳' in out) else out[-150:])


def test_autofit_disable(tmp: str) -> None:
    """--no-autofit: 纯生成（不编译），行为与旧版一致。"""
    write_plate(tmp, 'p1.md', 'KICKER: Plain\nHEADLINE: No Autofit\nBODY:\nPlain body.\n')
    r = run(['python3', 'build.py', 'plates/', 'plain.tex',
             '--docopts', 'paper=a4,portrait,columns=2,plates=1',
             '--no-autofit'], cwd=tmp)
    report('--no-autofit 纯生成', r.returncode == 0, f'exit={r.returncode}')
    tex_ok = os.path.exists(os.path.join(tmp, 'plain.tex'))
    pdf_ok = os.path.exists(os.path.join(tmp, 'plain.pdf'))
    report('--no-autofit 无编译', tex_ok and not pdf_ok,
           '有 .tex 无 .pdf' if tex_ok and not pdf_ok else '行为不符!')


def test_mainaside_structural(tmp: str) -> None:
    """C 顶层化重构: main-aside 布局双版 → 0 Overfull（结构性缺陷修复，此前 111% 溢出）。"""
    write_plate(tmp, 'p1.md', """LAYOUT: main-aside
KICKER: Main Story
HEADLINE: Lead Story with Lots of Content
DECK: A substantial deck that adds context.
BYLINE: Linotype QA
BODY:
Paragraph 0: The quick brown fox jumps over the lazy dog while typesetting engines measure hyphenation quality across narrow columns in a dual-plate main-aside layout.
Paragraph 1: Second paragraph with additional detail to increase the natural height of the main story column.
Paragraph 2: Third paragraph continues with more words so the content genuinely stresses the column budget.
STORY-B: Sidebar One
Sidebar content for the first aside story with a few sentences of text.
STORY-C: Sidebar Two
More sidebar content for the second aside story.
BRIEFS:
**Brief One:** First brief item text.
**Brief Two:** Second brief item text.
**Brief Three:** Third brief item text.
""")
    r = run(['python3', 'build.py', 'plates/', 'ma.tex',
             '--docopts', 'paper=a3,landscape,columns=3,plates=1', '--no-autofit'], cwd=tmp)
    ok, log = xelatex(tmp, 'ma.tex')
    report('C main-aside 编译', ok, '' if ok else log[-150:])
    if not ok:
        return
    log_text = open(os.path.join(tmp, 'ma.log'), encoding='utf-8').read()
    overfull = 'Overfull plate' in log_text
    report('C main-aside 0 Overfull', not overfull,
           '无溢出' if not overfull else '仍有溢出!(结构性缺陷未修)')


def test_image_support(tmp: str) -> None:
    """A 图片支持: IMAGE 字段 → \photo 生成 + 正常图编译 + 超大图溢出检测。"""
    # 创建测试图（用 PIL 或纯色 PPM）
    from PIL import Image
    Image.new('RGB', (200, 150), (180, 40, 30)).save(os.path.join(tmp, 'img.jpg'), quality=85)
    Image.new('RGB', (200, 1000), (30, 80, 180)).save(os.path.join(tmp, 'huge.jpg'), quality=80)
    write_plate(tmp, 'p1.md', """KICKER: Photo
HEADLINE: Image Test
IMAGE: img.jpg
IMAGEWIDTH: 1.0
IMAGECAPTION: Test caption
BODY:
Body text after the image.
""")
    r = run(['python3', 'build.py', 'plates/', 'img.tex',
             '--docopts', 'paper=a4,portrait,columns=2,plates=1', '--no-autofit'], cwd=tmp)
    tex = open(os.path.join(tmp, 'img.tex'), encoding='utf-8').read()
    report('A 图片字段生成', r.returncode == 0 and r'\photo{img.jpg}' in tex,
           'photo 生成' if r'\photo{img.jpg}' in tex else '未生成!')
    ok, log = xelatex(tmp, 'img.tex')
    report('A 正常图编译', ok, '' if ok else log[-150:])
    # 超大图 → Overfull（图片过大不静默）
    write_plate(tmp, 'p1.md', """KICKER: Photo
HEADLINE: Huge Image
IMAGE: huge.jpg
IMAGEWIDTH: 1.0
BODY:
Body text.
""")
    run(['python3', 'build.py', 'plates/', 'huge.tex',
         '--docopts', 'paper=a4,portrait,columns=2,plates=1', '--no-autofit'], cwd=tmp)
    ok2, log2 = xelatex(tmp, 'huge.tex')
    log_text = open(os.path.join(tmp, 'huge.log'), encoding='utf-8').read()
    report('A 超大图溢出检测', 'Overfull plate' in log_text,
           '检测到' if 'Overfull plate' in log_text else '未检测到!')


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
    test_autofit_overflow(tmp)
    test_autofit_sparse(tmp)
    test_autofit_boundary(tmp)
    test_autofit_disable(tmp)
    test_mainaside_structural(tmp)
    test_image_support(tmp)

    print(f'\n{len(PASSED)} PASS, {len(FAILED)} FAIL')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
