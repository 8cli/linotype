#!/usr/bin/env python3
"""linotype build.py — plates/*.md → LaTeX 自动生成器（通用排版内容管线）

用法:
    python3 build.py <plates目录> <输出.tex> [--class linotype] [--docopts "..."]
    python3 build.py plates/ newspaper.tex --docopts "paper=a3,landscape,plates=2,columns=3"
    python3 build.py plates/ newspaper.tex --docopts "paper=a4,portrait,plates=1,columns=3" --no-autofit

自动版面调整（默认开启，--no-autofit 关闭）:
    内容超高（Overfull plate）→ 自动缩字号（8.5–11pt, 0.5pt 步进）→ 减栏数（2–4）
    内容太空（版心利用率 < 45%）→ 自动增字号 → 增栏数
    纸张是硬约束（autofit 绝不动 paper/landscape/plates）。
    收敛条件: 0 Overfull 且最小利用率 ≥ 45%。到达边界仍溢出 → 失败报告（保留最小溢出配置的 PDF）。

输入: plates/pN.md, 每版固定结构:
    KICKER: ...
    HEADLINE: ...
    SUBHEADLINE: ...        (可选)
    DECK: ...
    BYLINE: ...
    BODY:                    (正文段, 段间空行)
    STORY-B:                 (可选副故事)
    HEADLINE: ...
    BODY: ...
    PULLQUOTE: ...           (可选)
    BRIEFS:                  (可选, 3 条, 以换行分隔)

输出: 一个 .tex, 每版一个 plate, 版间 \newpage; 组件按内容自动启用。
autofit 模式下同时产出编译好的 .pdf（收敛配置）。
"""
import argparse
import json
import os
import re
import subprocess
import sys

# ---------- autofit 边界（用户确认: 纸张是硬约束，只调字号+栏数+版心底边距） ----------
BS_MIN, BS_MAX = 8.5, 11.0                    # 正文字号边界（pt），二分搜索
BS_BINARY_EPS = 0.1                           # 二分字号精度（pt）
COLS_MIN, COLS_MAX = 2, 4                     # 栏数边界
BM_MIN, BM_MAX = 12.0, 16.0                   # 版心底边距边界（mm，第三旋钮: 溢出<一行时微调）
FILL_MIN = 0.95                               # 太空容忍下界（利用率 = 内容高/版心高；--docopts fill_min= 可覆盖）
MAX_AUTOFIT_ITERS = 16                        # 迭代硬上限（防意外死循环）
# 纸张竖版尺寸 (mm)，用于精确计算版心高（bottommargin 微调的量）
PAPER_H_MM = {'a3': 297, 'a4': 297, 'letter': 279}
PAPER_W_MM = {'a3': 420, 'a4': 210, 'letter': 216}

def strip_field(s: str) -> str:
    return s.strip()

def tex_escape(s: str) -> str:
    """转义 LaTeX 特殊字符（& % $ # _ { } 和 ~ ^），保留英文引号供排版。"""
    # 血泪（2026-08-05）: 必须先转义特殊字符（尤其 { }），再处理 markdown 加粗/斜体。
    # 若先做 **x**→\textbf{x} 再转义 {，会生成 \textbf\{x\}（花括号被二次转义），
    # LaTeX 渲染成字面 "{"（newspaper.tex 中已见 \textbf\{Oil Market Moves:\}）。
    # 血泪 #35: 反斜杠转义用占位符——正文含 \（路径/正则/LaTeX 敏感串）
    # → Undefined control sequence 编译失败。先占位 \x00，最后统一还原为
    # \textbackslash{}：若直接 replace，\textbackslash{} 的 { } 会被后续
    # { } 转义成 \{ \}（渲染字面 "{}"，实测 a\textbackslash\{\}b）。
    s = s.replace('\\', '\x00')
    s = s.replace('&', r'\&').replace('%', r'\%').replace('$', r'\$')
    s = s.replace('#', r'\#').replace('_', r'\_').replace('{', r'\{')
    s = s.replace('}', r'\}').replace('~', r'\textasciitilde{}')
    s = s.replace('^', r'\textasciicircum{}')
    # 中文弯引号 → LaTeX `` ''（英文直引号保留, 编译前由 tex 处理）
    s = s.replace('“', '``').replace('”', "''")
    # markdown 加粗 **x** → \textbf{x}（此时特殊字符已转义，花括号安全）
    s = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', s)
    # markdown 斜体 *x* → \textit{x}
    s = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'\\textit{\1}', s)
    # 还原反斜杠占位符（最后——\textbackslash{} 的 {} 不再经过 { } 转义）
    s = s.replace('\x00', r'\textbackslash{}')
    return s

def parse_plate(text: str) -> dict:
    """解析单个 plates/pN.md → 结构化 dict。"""
    p = {'kicker': '', 'headline': '', 'subheadline': '', 'deck': '',
         'byline': '', 'body': [], 'pullquote': '', 'briefs': [],
         'mainbriefs': [],  # 2026-08-07: 主栏底部补白简讯（MAINBRIEFS 段，main-aside 用）
         'stories': [], 'layout': '', 'columns': '', 'expanded': '',
         'image': '', 'imagewidth': '1.0', 'imagecaption': ''}  # 图片: IMAGE 路径 / IMAGEWIDTH 比例(0-1) / IMAGECAPTION 图注
    lines = text.split('\n')
    section = 'body'
    story = None
    for ln in lines:
        ln = ln.rstrip()
        up = ln.strip().upper()
        if up.startswith('LAYOUT:'):
            p['layout'] = strip_field(ln[7:]).lower(); section = 'meta'
        elif up.startswith('COLUMNS:'):
            p['columns'] = strip_field(ln[8:]); section = 'meta'
        elif up.startswith('EXPANDEDTITLE:') or up.startswith('EXPANDED:'):
            p['expanded'] = tex_escape(strip_field(ln.split(':', 1)[1])); section = 'meta'
        elif up.startswith('IMAGE:'):
            p['image'] = strip_field(ln.split(':', 1)[1]); section = 'meta'
        elif up.startswith('IMAGEWIDTH:'):
            p['imagewidth'] = strip_field(ln.split(':', 1)[1]); section = 'meta'
        elif up.startswith('IMAGECAPTION:') or up.startswith('IMAGECAPTION:'):
            p['imagecaption'] = tex_escape(strip_field(ln.split(':', 1)[1])); section = 'meta'
        elif up.startswith('KICKER:'):
            p['kicker'] = tex_escape(strip_field(ln[7:])); section = 'meta'
        elif up.startswith('HEADLINE:'):
            if section == 'story':
                # 副故事 headline
                if story: p['stories'].append(story)
                story = {'headline': strip_field(ln[9:]), 'byline': '', 'body': []}
                section = 'story'
            else:
                p['headline'] = tex_escape(strip_field(ln[9:])); section = 'meta'
        elif up.startswith('SUBHEADLINE:'):
            p['subheadline'] = tex_escape(strip_field(ln[12:])); section = 'meta'
        elif up.startswith('DECK:'):
            p['deck'] = tex_escape(strip_field(ln[5:])); section = 'meta'
        elif up.startswith('BYLINE:'):
            p['byline'] = tex_escape(strip_field(ln[7:])); section = 'meta'
        elif up.startswith('BYLINE-B:'):
            # 2026-08-07 用户要求: 副条(STORY-B)独立署名（日期/站点/记者）
            if story is not None:
                story['byline'] = tex_escape(strip_field(ln[9:])); section = 'story'
        elif up.startswith('PULLQUOTE:'):
            p['pullquote'] = tex_escape(strip_field(ln[10:])); section = 'meta'
        elif up.startswith('BRIEFS:'):
            section = 'briefs'
        elif up.startswith('MAINBRIEFS:'):
            # 2026-08-07: 主栏底部补白简讯段（P1 main-aside 用，前 2 条进
            # \mainstory 第 6/7 参 → 两栏底部）
            section = 'mainbriefs'
        elif up.startswith('STORY-B:') or up.startswith('STORY-C:'):
            if story: p['stories'].append(story)
            story = {'headline': tex_escape(strip_field(ln.split(':', 1)[1])), 'body': []}
            section = 'story'
        elif up.startswith('BODY:'):
            section = 'body'
        elif ln.strip() == '':
            continue
        else:
            if section == 'body':
                p['body'].append(tex_escape(strip_field(ln)))
            elif section == 'briefs':
                if ln.strip(): p['briefs'].append(tex_escape(strip_field(ln)))
            elif section == 'mainbriefs':
                if ln.strip(): p['mainbriefs'].append(tex_escape(strip_field(ln)))
            elif section == 'story' and story is not None:
                story['body'].append(tex_escape(strip_field(ln)))
    if story: p['stories'].append(story)
    return p

def render_plate(p: dict, idx: int) -> str:
    """渲染一个版 → LaTeX 片段。"""
    out = []
    out.append(f'% ===== P{idx} =====')
    out.append(r'\begin{plate}')
    if p['layout'] == 'main-aside':
        # 主栏+侧栏: 主 story 进 main 2 栏, 副 stories 进 aside 第 3 栏
        # 2026-08-05 顶层化重构: mainaside 已占满版心时，通栏内容（pullquote/inbrief）
        # 追加在外必超高（实测 pullquote 127pt / inbrief 122pt）——都移入栏内:
        #   pullquote → mainstory 正文末尾（栏内引文，宽度自适应 \linewidth）
        #   BRIEFS    → \asidebriefs（aside 栏底部单列条，进 aside 栏共享截断预算）
        body = _join_body(p['body'])
        if p['image']:
            body = r'\photo{' + p['image'] + '}{' + p['imagewidth'] + '}{' + p['imagecaption'] + '}' + r'\par ' + body
        if p['pullquote']:
            body += r'\par ' + r'\pullquote{' + p['pullquote'] + '}'
        out.append(r'\begin{mainaside}')
        # 2026-08-07: MAINBRIEFS 前 2 条 → \mainstory 第 6/7 参（主栏底部补白）
        mb = p['mainbriefs'] if p['mainbriefs'] else ['', '']
        mb_l = mb[0] if len(mb) > 0 else ''
        mb_r = mb[1] if len(mb) > 1 else ''
        out.append(r'\mainstory{' + p['kicker'] + '}{' + p['headline'] + '}{'
                   + p['deck'] + '}{' + p['byline'] + '}{' + body + '}'
                   + '{' + mb_l + '}{' + mb_r + '}')
        for st in p['stories']:
            st_body = _join_body(st['body'])
            out.append(r'\asidestory{' + st['headline'] + '}{' + st.get('byline', '')
                       + '}{' + st_body + '}')
        if p['briefs']:
            label = 'IN BRIEF'
            items = p['briefs'][:3]
            while len(items) < 3:
                items.append('')
            out.append(r'\asidebriefs{' + label + '}{' + items[0] + '}{' + items[1] + '}{' + items[2] + '}')
        out.append(r'\end{mainaside}')
    else:
        # 等宽多栏（默认）
        # 2026-08-06 血泪 #26: 版头必须包进 \plateheader（收集到独立盒），
        # storycolumns 的 @colht = contentH − 版头实际高度。此前版头直接
        # 排在 vbox 里，@colht 读 \ht\platebox（构造中=0）→ multicol 满版
        # → 版头+multicol 超 contentH → vsplit 切不动 multicol 整盒丢弃 →
        # 版面只剩版头（P3 双版 53.7mm，fill 却报 100%）。
        out.append(r'\begin{plateheader}')
        if p['kicker']:
            out.append(r'\kicker{' + p['kicker'] + '}')
        if p['headline']:
            out.append(r'\headline{' + p['headline'] + '}')
        if p['subheadline']:
            out.append(r'\subheadline{' + p['subheadline'] + '}')
        if p['deck']:
            out.append(r'\deck{' + p['deck'] + '}')
        if p['byline']:
            out.append(r'\byline{' + p['byline'] + '}')
        if p['expanded']:
            out.append(r'\expandedtitle{' + p['expanded'] + '}')
        if p['image']:
            out.append(r'\photo{' + p['image'] + '}{' + p['imagewidth'] + '}{' + p['imagecaption'] + '}')
        out.append(r'\end{plateheader}')
        # 2026-08-06 结构修复: pullquote/STORY-B/inbrief 全部移入 storycolumns
        # （multicol 内）——原先排在 multicol 外，版头 + multicol 满版 +
        # 版外内容 = 必超版心（P2 812.7pt > 742.6pt 溢出到页边，实测 285-295mm
        # 有墨迹）。multicol 平衡包含所有内容 + @colht 动态剩余空间 → 总高 = contentH。
        has_story = bool(p['body'] or p['pullquote'] or p['stories'] or p['briefs'])
        if has_story:
            col_opt = '[' + p['columns'] + ']' if p['columns'] else ''
            out.append(r'\begin{storycolumns}' + col_opt)
            if p['body']:
                out.append(r'\noindent ' + p['body'][0])
                for para in p['body'][1:]:
                    out.append('')
                    out.append(para)
            if p['pullquote']:
                out.append(r'\vspace{0.5mm}')
                out.append(r'\pullquote{' + p['pullquote'] + '}')
            # 副故事
            for st in p['stories']:
                if st['headline']:
                    out.append(r'\vspace{1mm}')
                    out.append(r'\subheadline{' + st['headline'] + '}')
                if st.get('byline'):
                    out.append(r'\storybyline{' + st['byline'] + '}')
                for para in st['body']:
                    out.append('')
                    out.append(r'\noindent ' + para if not para.startswith('\\noindent') else para)
            # In Brief（main-aside 已用 \asidebriefs，此处仅等宽布局进 multicol）
            # 2026-08-06: 支持 >3 条简讯——每 3 条一组多行堆叠
            if p['briefs']:
                label = 'IN BRIEF'
                for g in range(0, len(p['briefs']), 3):
                    items = p['briefs'][g:g + 3]
                    while len(items) < 3:
                        items.append('')
                    out.append(r'\vspace{1mm}')
                    out.append(r'\inbrief{' + label + '}{' + items[0] + '}{' + items[1] + '}{' + items[2] + '}')
            out.append(r'\end{storycolumns}')
        elif p['briefs'] and p['layout'] != 'main-aside':
            # body/pullquote/stories 全空但只有简讯（罕见）: 保持原外置渲染
            label = 'IN BRIEF'
            for g in range(0, len(p['briefs']), 3):
                items = p['briefs'][g:g + 3]
                while len(items) < 3:
                    items.append('')
                out.append(r'\vspace{1mm}')
                out.append(r'\inbrief{' + label + '}{' + items[0] + '}{' + items[1] + '}{' + items[2] + '}')
    out.append(r'\end{plate}%')  # 血泪 #34: % 吞换行防 2.51pt 版间空格胶水
    return '\n'.join(out)


def _join_body(paras: list) -> str:
    r"""正文段列表 → 单字符串（段间 \par，用于宏参数内分段）。"""
    return r'\par '.join(paras)


# ---------- autofit 辅助 ----------

def parse_docopts(docopts: str) -> dict:
    """解析 docopts 字符串 → dict。布尔键（如 landscape）值为 True。"""
    d = {}
    for part in docopts.split(','):
        part = part.strip()
        if not part:
            continue
        if '=' in part:
            k, v = part.split('=', 1)
            d[k.strip()] = v.strip()
        else:
            d[part] = True
    return d

def docopts_to_str(d: dict) -> str:
    """dict → docopts 字符串（autofit 每轮组装的最终配置）。"""
    parts = []
    for k, v in d.items():
        parts.append(k if v is True else f'{k}={v}')
    return ','.join(parts)

def generate_tex(plates_dir: str, docopts: str, clsname: str) -> tuple:
    """读 plates → 组装 tex 文本 + 版布局表。返回 (tex, layouts)。"""
    files = sorted([f for f in os.listdir(plates_dir) if f.endswith('.md')])
    if not files:
        raise SystemExit('错误: plates 目录无 .md 文件')

    out = [r'\documentclass{' + clsname + '}',
           r'\linotypesetup{' + docopts + '}',
           r'\begin{document}']
    plates = []
    for i, fname in enumerate(files, 1):
        text = open(os.path.join(plates_dir, fname), encoding='utf-8').read()
        p = parse_plate(text)
        plates.append(render_plate(p, i))
    if 'plates=2' in docopts:
        # 双版: 每页 2 个 plate 并排（按文件顺序两两配对: P1|P2, P3|P4）
        # 注: 报纸折叠语义（P1|P4, P2|P3）需要特定顺序的文件名——使用者按
        # 折叠序命名 plates 文件即可（如 p1=封面, p4=封底, 同 sheet 相邻）。
        for i in range(0, len(plates), 2):
            out.append(plates[i])
            if i + 1 < len(plates):
                out.append('%')
                out.append(plates[i + 1])
            out.append(r'\newpage')
            out.append('')
    else:
        for plate_tex in plates:
            out.append(plate_tex)
            out.append(r'\newpage')
            out.append('')
    out.append(r'\end{document}')

    # layout.json 数据（pixelcheck --layout auto 消费）: main-aside → multi; 其他 → single
    layouts = {}
    for i, fname in enumerate(files, 1):
        text = open(os.path.join(plates_dir, fname), encoding='utf-8').read()
        p = parse_plate(text)
        layouts[f'p{i}'] = 'multi' if p['layout'] == 'main-aside' else 'single'
    return '\n'.join(out), layouts

def write_tex(output: str, tex_text: str, layouts: dict, docopts: str = '') -> None:
    """写 .tex + layout.json（pixelcheck 消费）。

    2026-08-07 修复（pixelcheck 协议断裂）: sheets 必须按页分——
    A3 双版 2 页: front=[页1两版] back=[页2两版]；此前把 4 版全塞 front，
    pixelcheck resolve_layout 的 stem 匹配永远失败 → 回退像素启发式 →
    main-aside 版头右侧空白误报（P1 列2 82-101mm 假 FAIL，实测墨 9.5%）。
    """
    with open(output, 'w', encoding='utf-8') as f:
        f.write(tex_text)
    opts = parse_docopts(docopts)
    dual = opts.get('plates') == '2'
    plates = list(layouts.keys())
    if dual and len(plates) >= 4:
        sheets = {'front': plates[:2], 'back': plates[2:]}
    else:
        sheets = {'front': plates}
    layout_json = {'sheets': sheets, 'layout': layouts}
    out_dir = os.path.dirname(os.path.abspath(output))
    with open(os.path.join(out_dir, 'layout.json'), 'w', encoding='utf-8') as f:
        json.dump(layout_json, f, ensure_ascii=False, indent=1)

def compile_tex(output: str) -> str:
    """xelatex 编译 .tex，返回日志文本。

    cwd = 用户运行目录（linotype.cls 须在此，文档用法: 引擎目录运行 build.py）；
    产物（pdf/log/aux）经 -output-directory 导向 output 所在目录。
    """
    out_abs = os.path.abspath(output)
    out_dir = os.path.dirname(out_abs)
    tex_name = os.path.basename(out_abs)
    stem = os.path.splitext(tex_name)[0]
    # TEXINPUTS 锁定引擎目录优先（2026-08-06 血泪 #27）: Kpathsea 优先加载
    # tex 文件所在目录的 cls——产物目录残留旧版 linotype.cls 会静默覆盖
    # 引擎目录的新版（实测 plateheader undefined，编译用 daily 目录旧 cls）。
    # TEXINPUTS=引擎目录: 使引擎目录 cls 优先，末尾冒号补默认路径。
    env = dict(os.environ)
    env['TEXINPUTS'] = os.getcwd() + os.pathsep + env.get('TEXINPUTS', '')
    r = subprocess.run(
        ['xelatex', '-interaction=nonstopmode', '-halt-on-error',
         f'-output-directory={out_dir}', tex_name],
        cwd=os.getcwd(), env=env, capture_output=True, text=True, timeout=300)
    log_path = os.path.join(out_dir, stem + '.log')
    if os.path.exists(log_path):
        with open(log_path, encoding='utf-8', errors='replace') as f:
            return f.read()
    return r.stdout + r.stderr

def parse_feedback(log: str) -> tuple:
    """解析编译日志 → (overfull: bool, fills: list[float])。
    依赖 linotype.cls 的 plate 环境输出:
      "Plate content: Xpt/ contentH Ypt"（总是输出）→ fill = X/Y
      "Overfull plate: content Xpt> contentH Ypt, truncated Npt"（超高时）
      → 溢出判定：仅截断量 N > contentH 的 5% 视为严重溢出（需压字号/增栏）；
        微小截断（如 20pt = 2.7%）由 vsplit 兜底吸收，是设计内正常行为，
        不拖累全局字号（2026-08-06: P2 微超曾把 P3 拖到 91.6%）。
    返回所有版的 fill 列表（autofit 分别用 min 判太空、max 判溢出程度）。
    """
    overfull = False
    for m in re.finditer(
            r'Overfull plate: content [\d.]+pt\s*> contentH ([\d.]+)pt, truncated ([\d.]+)',
            log):
        content_h, truncated = float(m.group(1)), float(m.group(2))
        if truncated > content_h * 0.05:
            overfull = True
    # 血泪 #55: main/aside column 的 vsplit 截断也接入——P1 侧栏自然高
    # 792.4pt vsplit 截到 732.6pt（丢 59.8pt ≈ 21mm），但截断后 plate
    # content 723.7 < contentH → 不触发 Overfull plate → fill 97.4% 假
    # 达标（内容静默丢失）。截断量 > contentH 5% 即视为 overfull 触发
    # autofit 缩字号（截断是"装不下"，与 plate 级同一判定标准）。
    for m in re.finditer(
            r'Overfull (?:main|aside) column: 内容 ([\d.]+)pt\s*> contentH ([\d.]+)pt',
            log):
        content, content_h = float(m.group(1)), float(m.group(2))
        if content - content_h > content_h * 0.05:
            overfull = True
    fills = []
    for m in re.finditer(r'Plate content: ([\d.]+)pt/ contentH ([\d.]+)pt', log):
        content, content_h = float(m.group(1)), float(m.group(2))
        if content_h > 0:
            fills.append(content / content_h)
    return overfull, fills

def autofit(plates_dir: str, output: str, docopts: str, clsname: str) -> int:
    r"""自动版面调整（二分搜索版）: 生成 → 编译 → 二分找最大不溢出字号 → 收敛/兜底。

    算法（升级 2026-08-05，借鉴 tcolorbox fitting 库的 lowerfitdim/upperfitdim
    二分搜索，而非逐档步进）:
      1. bodyfontsize（主旋钮）: 在 [8.5, 11]pt 区间二分找**最大不溢出**字号
         （0.1pt 精度，~5 次编译/档；字号单调 → 无振荡）
      2. columns（次旋钮）: 溢出到字号下限 → 增栏；太空到字号上限 → 减栏
         （multicol 平衡盒高 = 内容自然高/N，栏多→矮，实测 60 段 8.5pt:
         2栏=1038 / 3栏=927 / 4栏=872pt；注意超长内容是 U 形曲线，失败报历史最佳）
      3. bottommargin（第三旋钮）: 溢出 < 一行（~15pt）时微调版心底边距
         [12, 16]mm —— 差一点场景的最优解（替代 \enlargethispage，后者对
         固定 \contentH 的 plate 盒子无效）
    收敛: 0 Overfull 且 min_fill ≥ FILL_MIN。返回 0=收敛; 1=边界内无法放下。
    """
    opts = parse_docopts(docopts)
    try:
        fill_min = float(opts.get('fill_min', str(FILL_MIN)))
    except ValueError:
        fill_min = FILL_MIN
    try:
        cols = int(opts.get('columns', '3'))
    except ValueError:
        cols = 3
    cols = max(COLS_MIN, min(COLS_MAX, cols))
    base = {k: v for k, v in opts.items() if k not in ('columns', 'bodyfontsize', 'bottommargin', 'fill_min')}
    # 版心高（mm）: 精确计算 bottommargin 微调量（纸张尺寸 × 横竖版）
    paper = str(base.get('paper', 'a3'))
    landscape = bool(base.get('landscape'))
    paper_h_mm = PAPER_W_MM.get(paper, 420) if landscape else PAPER_H_MM.get(paper, 297)

    print('=== autofit: 自动版面调整（二分搜索，--no-autofit 关闭）===')
    attempts = []  # (cols, bs, bm, overfull, min_fill, max_fill)
    it = 0
    bm = BM_MAX  # bottommargin 第三旋钮（mm），初始 16（默认版心）

    def compile_once(c: int, bs: float, bm_mm: float) -> tuple:
        """编译一次，返回 (overfull, fills, cur_docopts)。"""
        nonlocal it
        it += 1
        d = dict(base)
        d['columns'] = str(c)
        d['bodyfontsize'] = f'{bs:g}pt'
        d['bottommargin'] = f'{bm_mm:g}mm'
        cur = docopts_to_str(d)
        tex_text, layouts = generate_tex(plates_dir, cur, clsname)
        write_tex(output, tex_text, layouts, cur)
        try:
            log = compile_tex(output)
        except FileNotFoundError:
            print('错误: xelatex 不可用（autofit 需编译迭代）；请安装 TeX Live，或用 --no-autofit 纯生成')
            raise SystemExit(1)
        overfull, fills = parse_feedback(log)
        min_fill = min(fills) if fills else None
        max_fill = max(fills) if fills else None
        attempts.append((c, bs, bm_mm, overfull, min_fill, max_fill))
        if overfull:
            state = f'溢出(最大 {max_fill * 100:.0f}%)'
        elif min_fill is not None and min_fill < fill_min:
            state = f'太空(最小 {min_fill * 100:.0f}%)'
        else:
            state = f'达标(最小 {min_fill * 100:.0f}%)' if min_fill is not None else '达标'
        print(f'  迭代 {it}: columns={c}, bodyfontsize={bs:g}pt, bottommargin={bm_mm:g}mm — {state}')
        return overfull, fills, cur

    def is_converged(overfull: bool, fills: list) -> bool:
        return not overfull and (not fills or min(fills) >= fill_min)

    def report_failure() -> int:
        """边界内无法放下: 报告历史最低溢出尝试（U 形曲线 → 非边界配置）。"""
        all_ov = [a for a in attempts if a[3]]
        if all_ov:
            best = min(all_ov, key=lambda a: (a[5] if a[5] is not None else 0))
            print(f'  ❌ 边界内无法放下（字号 {BS_MIN:g}pt 最小、栏数 {COLS_MAX} 最大、版心 {BM_MIN:g}mm 最小均已试）')
            print(f'     最低溢出尝试: columns={best[0]}, bodyfontsize={best[1]:g}pt, bottommargin={best[2]:g}mm, 最满版 {best[5]*100:.0f}%')
        else:
            ok = [a for a in attempts if not a[3] and a[4] is not None]
            best = max(ok, key=lambda a: a[4])
            print(f'  ❌ 边界内无法放下: columns={best[0]}, bodyfontsize={best[1]:g}pt, bottommargin={best[2]:g}mm')
            print(f'     历史最佳: 最小利用率 {best[4]*100:.0f}% — 内容仍未达标')
        print('     请修剪内容，或手动换更大纸张（autofit 不动纸张）。已保留对应配置的 PDF（含 Overfull 警告）。')
        return 1

    # —— 黄金路径: 初始配置（用户指定的栏数 + 默认字号/版心）直接试 ——
    overfull, fills, cur = compile_once(cols, 9.5, bm)
    if is_converged(overfull, fills):
        print(f'  ✅ 收敛 — 最终配置: {cur}')
        return 0

    prev_bs, warm_done = 9.5, True  # 9.5 已在黄金路径试过
    while it < MAX_AUTOFIT_ITERS:
        # —— 字号二分: 找 [BS_MIN, BS_MAX] 内最大不溢出字号（0.1pt 精度）——
        lo, hi = BS_MIN, BS_MAX
        best_bs, best_fills, best_cur, best_over = None, None, None, None
        # warm start: 栏数改变后先试上一档最终字号（省迭代；方向可能翻转须重测）
        if not warm_done:
            overfull, fills, cur = compile_once(cols, prev_bs, bm)
            if is_converged(overfull, fills) and min(fills) >= 0.9:
                print(f'  ✅ 收敛 — 最终配置: {cur}')
                return 0
            if overfull:
                hi = prev_bs
                # prev_bs == BS_MIN 时 warm 即下限确认（避免随后重复编译确认）
                if prev_bs <= BS_MIN + 0.01:
                    best_bs, best_fills, best_cur, best_over = prev_bs, fills, cur, True
            else:
                lo = prev_bs
                best_bs, best_fills, best_cur, best_over = prev_bs, fills, cur, False
            warm_done = True
        while hi - lo >= BS_BINARY_EPS and it < MAX_AUTOFIT_ITERS:
            mid = round((lo + hi) / 2, 2)
            if best_bs is not None and abs(mid - best_bs) < 0.01:
                mid = round(mid + 0.05, 2)  # 避开已试点的边界抖动
            overfull, fills, cur = compile_once(cols, mid, bm)
            if overfull:
                hi = mid
            else:
                lo = mid
                best_bs, best_fills, best_cur, best_over = mid, fills, cur, False
        if best_bs is None:
            # 全溢出（8.5 都放不下）: 确认下限
            overfull, fills, cur = compile_once(cols, BS_MIN, bm)
        else:
            # 2026-08-06 修复：统一重编译 lo（最终配置）。此前 best_bs == lo
            # 时用内存缓存 fills 判定收敛，out.log/out.pdf 却停在最后一次实际
            # 编译（二分上界试探，可能溢出）——demand/visual 误读溢出数据
            # （实测迭代 5 达标 10.84pt，out.log 却是迭代 6 的 10.92pt 溢出
            # 106%，parse_demand 报 P2/P3/P4 严重溢出假 FAIL）。
            overfull, fills, cur = compile_once(cols, lo, bm)
        prev_bs = lo

        if is_converged(overfull, fills):
            print(f'  ✅ 收敛 — 最终配置: {cur}')
            return 0
        if overfull:
            # 溢出方向: 字号已到下限 → 增栏 → 版心微调 → 失败
            if cols < COLS_MAX:
                cols += 1
                warm_done = False
                continue
            max_fill = max(fills) if fills else 1.0
            content_h_mm = paper_h_mm - 20 - bm
            overflow_mm = (max_fill - 1.0) * content_h_mm
            need_mm = overflow_mm + 0.5  # 0.5mm 余量
            if bm > BM_MIN and need_mm < (bm - BM_MIN):
                bm = max(BM_MIN, round(bm - need_mm, 1))
                warm_done = False  # 版心变化 → 重新 warm start（省重新二分）
                continue
            return report_failure()
        else:
            # 太空: 最大字号仍 fill < 下限 → 减栏 → 接受（内容天然短）
            if cols > COLS_MIN:
                cols -= 1
                warm_done = False
                continue
            print(f'  ⚠️ 内容天然短: 已达边界 columns={cols}(最小), bodyfontsize={BS_MAX:g}pt(最大) — 接受当前配置（不强行填满）')
            return 0
    print(f'  ⚠️ 达到迭代上限 {MAX_AUTOFIT_ITERS}，接受当前配置')
    return 1 if attempts and attempts[-1][3] else 0


def visual_check(output: str, docopts: str, pixelcheck: str = '') -> int:
    """视觉验收闭环（--visual，借鉴 PaperFit 渲染→诊断→建议）:
    渲染 PDF → PNG → pixelcheck 列空白/溢出诊断 → 视觉报告 + 修复建议。

    返回 0 = 视觉验收通过（无空白带）; 1 = 有空白带（报告位置 + 建议）。
    """
    pdf = os.path.splitext(output)[0] + '.pdf'
    if not os.path.exists(pdf):
        print('⚠️ 视觉验收跳过: 无 PDF（--no-autofit 未编译？先编译或去掉 --no-autofit）')
        return 0
    if not pixelcheck:
        # 默认在仓库/skill 的 scripts/ 找
        for cand in (os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts', 'pixelcheck.py'),
                     os.path.expanduser('~/.claude/skills/linotype/scripts/pixelcheck.py')):
            if os.path.exists(cand):
                pixelcheck = cand
                break
    if not pixelcheck or not os.path.exists(pixelcheck):
        print('⚠️ 视觉验收跳过: 未找到 pixelcheck.py（--pixelcheck PATH 指定）')
        return 0

    out_abs = os.path.abspath(output)
    out_dir = os.path.dirname(out_abs)
    stem = os.path.splitext(os.path.basename(out_abs))[0]
    layout_json = os.path.join(out_dir, 'layout.json')
    opts = parse_docopts(docopts)
    dual = opts.get('plates') == '2'

    print('\n=== 视觉验收（渲染 → 像素诊断）===')
    # 1. 渲染 PDF → PNG（110dpi → pxmm = 4.331）
    try:
        subprocess.run(['pdftoppm', '-png', '-r', '110', pdf, os.path.join(out_dir, stem + '-v')],
                       check=True, capture_output=True, timeout=300)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print('⚠️ 渲染失败: pdftoppm 不可用？')
        return 0
    import glob
    pngs = sorted(glob.glob(os.path.join(out_dir, stem + '-v-*.png')))
    if not pngs:
        print('⚠️ 渲染失败: 无 PNG 输出')
        return 0

    # 2. 每页 pixelcheck 诊断
    issues = []
    for png in pngs:
        cmd = ['python3', pixelcheck, png, '--pxmm', '4.331', '--layout-file', layout_json]
        if dual:
            cmd += ['--half', 'both']
        else:
            cmd += ['--full']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        out = (r.stdout or '') + (r.stderr or '')
        page = os.path.basename(png).replace(stem + '-v-', '').replace('.png', '')
        if 'FAIL' in out:
            # 提取空白带位置（只匹配 pixelcheck 报告行，避免 argparse help 误入）
            gaps = [ln.strip() for ln in out.splitlines()
                    if re.match(r'^\s*(列\d+|[左右]半版|整页):', ln)]
            issues.append((page, gaps))
            print(f'  [FAIL] 第 {page} 页: {len(gaps)} 处空白带')
            for g in gaps[:4]:
                print(f'    {g}')
        else:
            print(f'  [PASS] 第 {page} 页: 无空白带')

    # 3. 视觉报告 + 修复建议
    if issues:
        print('\n  ❌ 视觉验收未通过: 存在列内空白带')
        print('  修复建议:')
        print('    - 空白带在版底 → 内容偏少: autofit 已尽量增大字号/减栏数，可补充内容或接受留白')
        print('    - 空白带在栏中 → 栏平衡问题: 检查该版内容分布，或手动调字号')
        return 1
    print('\n  ✅ 视觉验收通过: 各版无异常空白带')
    return 0


# ---------- linotype demand 输出（imposer 需求-供给协议；--demand 时启用） ----------
TOPIC_BY_PLATE = {0: "world/military", 1: "ai/tech", 2: "space", 3: "tech"}
MIN_KIND_BY_PLATE = {0: "independent", 1: "company", 2: "agency", 3: "tech-media"}


def estimate_requests(fill: float, content_h: float, plate_idx: int, fill_min: float = FILL_MIN) -> list[dict]:
    """按 fill 缺口估算补稿需求（规格: type/words/min_kind/topic）。

    fill_min 为太空容忍下界（--docopts fill_min= 覆盖）；fill ≥ fill_min 不发单。
    """
    if fill >= fill_min:
        return []
    deficit = (fill_min - fill) * content_h
    topic = TOPIC_BY_PLATE.get(plate_idx, "world")
    min_kind = MIN_KIND_BY_PLATE.get(plate_idx, "china-official")
    # 估算: 简讯 60-90 字 ≈ 26-40pt; 中篇 250-400 字 ≈ 110-175pt; 深度 400-600 字 ≈ 175-260pt
    if deficit < 100:
        return [{"type": "brief", "count": max(1, int(deficit // 33)), "words": [60, 90],
                 "topic": topic, "min_kind": min_kind}]
    if deficit < 300:
        return [{"type": "main", "count": 1, "words": [250, 400], "topic": topic, "min_kind": min_kind},
                {"type": "brief", "count": max(1, int((deficit - 140) // 33)), "words": [60, 90],
                 "topic": topic, "min_kind": min_kind}]
    return [{"type": "deep_dive", "count": 1, "words": [400, 600], "topic": topic, "min_kind": "thinktank"},
            {"type": "brief", "count": max(1, int((deficit - 200) // 33)), "words": [60, 90],
             "topic": topic, "min_kind": min_kind}]


def write_demand(log_path: str, out_dir: str, fill_min: float = FILL_MIN) -> str:
    """从编译日志读每版 content/fill → 估算补稿需求 → 写 demand.json。
    返回 demand.json 路径；无需求/日志缺失/溢出返回 None。"""
    if not os.path.exists(log_path):
        return None
    log_text = open(log_path, encoding="utf-8", errors="replace").read()
    # 2026-08-06 修复（血泪 #41）: 必须按 truncated > 5% 判定溢出拒单——
    # 原 re.search("Overfull plate") 只要出现字样就拒单，P4 微超 33.7pt
    # （<5% 阈值 37.1pt，autofit 已容忍）会误杀其他版的需求单（P2 76.9%
    # 补稿需求被吞，闭环不触发）。
    for m in re.finditer(
            r'Overfull plate: content [\d.]+pt\s*> contentH ([\d.]+)pt, truncated ([\d.]+)',
            log_text):
        content_h, truncated = float(m.group(1)), float(m.group(2))
        if truncated > content_h * 0.05:
            return None  # 严重溢出: autofit 未收敛，不发补稿单（应先修内容）
    pairs = re.findall(r"Plate content: ([\d.]+)pt/ contentH ([\d.]+)pt", log_text)
    if not pairs:
        return None
    plates = {}
    for i, (content, content_h) in enumerate(pairs):
        content, content_h = float(content), float(content_h)
        fill = content / content_h if content_h else 1.0
        reqs = estimate_requests(fill, content_h, i, fill_min)
        if reqs:
            plates[f"P{i+1}"] = {"fill": round(fill, 3),
                                  "deficit_pt": round((fill_min - fill) * content_h, 1),
                                  "requests": reqs}
    if not plates:
        return None
    path = os.path.join(out_dir, "demand.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"plates": plates}, f, ensure_ascii=False, indent=2)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description='plates/*.md → LaTeX 生成器（默认自动版面调整）')
    ap.add_argument('plates_dir', help='plates/ 目录')
    ap.add_argument('output', help='输出 .tex 路径')
    ap.add_argument('--docopts', default='paper=a3,landscape,plates=2,columns=3',
                    help='linotype.cls 选项（逗号分隔）')
    ap.add_argument('--class', dest='clsname', default='linotype',
                    help='文档类名（默认 linotype）')
    ap.add_argument('--theme', default='',
                    help='主题: newspaper|magazine|brief（追加到 docopts）')
    ap.add_argument('--no-autofit', action='store_true',
                    help='关闭自动版面调整（默认开启: 溢出/太空自动调字号栏数，纸张不动）')
    ap.add_argument('--visual', action='store_true',
                    help='视觉验收闭环: autofit 收敛后渲染 PDF → pixelcheck 诊断列空白（借鉴 PaperFit）')
    ap.add_argument('--pixelcheck', default='',
                    help='pixelcheck.py 路径（--visual 时；默认自动探测 scripts/ 或 skill 目录）')
    ap.add_argument('--demand', action='store_true',
                    help='autofit 收敛后输出 demand.json（imposer 按单补稿）')
    args = ap.parse_args()
    if args.theme and f'theme={args.theme}' not in args.docopts:
        args.docopts = args.docopts.rstrip(',') + f',theme={args.theme}'

    code = 0
    if args.no_autofit:
        tex_text, layouts = generate_tex(args.plates_dir, args.docopts, args.clsname)
        write_tex(args.output, tex_text, layouts, args.docopts)
        n = len([f for f in os.listdir(args.plates_dir) if f.endswith('.md')])
        print(f'已生成 {args.output} ({n} 版, --no-autofit)')
    else:
        code = autofit(args.plates_dir, args.output, args.docopts, args.clsname)
        if args.demand and code == 0:
            out_dir = os.path.dirname(os.path.abspath(args.output))
            fill_min = FILL_MIN
            for kv in args.docopts.split(','):
                if kv.strip().startswith('fill_min='):
                    try:
                        fill_min = float(kv.split('=', 1)[1])
                    except ValueError:
                        pass
            dpath = write_demand(os.path.splitext(args.output)[0] + '.log', out_dir, fill_min)
            if dpath:
                print(f'  📋 demand.json 已输出: {dpath} (imposer 按单补稿)')
            else:
                # 血泪 #53: 无需求时清空旧 demand.json（write_demand 返回 None
                # 不覆盖 → 残留旧补稿单，SKILL.md 闭环步骤 7 以 demand.json 判续
                # 白跑一轮。实测 P2 实际 98.2% 达标但旧文件报 93.8%）
                stale = os.path.join(out_dir, 'demand.json')
                if os.path.exists(stale):
                    os.remove(stale)
                print('  📋 demand.json: 无需求（版面全部达标，旧补稿单已清空）')
    if args.visual:
        vc = visual_check(args.output, args.docopts, args.pixelcheck)
        if vc != 0:
            code = vc
    return code

if __name__ == '__main__':
    sys.exit(main())
