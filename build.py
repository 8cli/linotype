#!/usr/bin/env python3
"""linotype build.py — plates/*.md → LaTeX 自动生成器（通用排版内容管线）

用法:
    python3 build.py <plates目录> <输出.tex> [--class linotype] [--docopts "..."]
    python3 build.py plates/ newspaper.tex --docopts "paper=a3,landscape,plates=2,columns=3"

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
"""
import argparse
import json
import os
import re
import sys

def strip_field(s: str) -> str:
    return s.strip()

def tex_escape(s: str) -> str:
    """转义 LaTeX 特殊字符（& % $ # _ { } 和 ~ ^），保留英文引号供排版。"""
    # 血泪（2026-08-05）: 必须先转义特殊字符（尤其 { }），再处理 markdown 加粗/斜体。
    # 若先做 **x**→\textbf{x} 再转义 {，会生成 \textbf\{x\}（花括号被二次转义），
    # LaTeX 渲染成字面 "{"（newspaper.tex 中已见 \textbf\{Oil Market Moves:\}）。
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
    return s

def parse_plate(text: str) -> dict:
    """解析单个 plates/pN.md → 结构化 dict。"""
    p = {'kicker': '', 'headline': '', 'subheadline': '', 'deck': '',
         'byline': '', 'body': [], 'pullquote': '', 'briefs': [],
         'stories': [], 'layout': '', 'columns': '', 'expanded': ''}  # layout: ''(等宽多栏) | 'main-aside'; columns: 版独立栏数; expanded: 跨栏标题
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
        elif up.startswith('KICKER:'):
            p['kicker'] = tex_escape(strip_field(ln[7:])); section = 'meta'
        elif up.startswith('HEADLINE:'):
            if section == 'story':
                # 副故事 headline
                if story: p['stories'].append(story)
                story = {'headline': strip_field(ln[9:]), 'body': []}
                section = 'story'
            else:
                p['headline'] = tex_escape(strip_field(ln[9:])); section = 'meta'
        elif up.startswith('SUBHEADLINE:'):
            p['subheadline'] = tex_escape(strip_field(ln[12:])); section = 'meta'
        elif up.startswith('DECK:'):
            p['deck'] = tex_escape(strip_field(ln[5:])); section = 'meta'
        elif up.startswith('BYLINE:'):
            p['byline'] = tex_escape(strip_field(ln[7:])); section = 'meta'
        elif up.startswith('PULLQUOTE:'):
            p['pullquote'] = tex_escape(strip_field(ln[10:])); section = 'meta'
        elif up.startswith('BRIEFS:'):
            section = 'briefs'
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
        body = _join_body(p['body'])
        out.append(r'\begin{mainaside}')
        out.append(r'\mainstory{' + p['kicker'] + '}{' + p['headline'] + '}{'
                   + p['deck'] + '}{' + p['byline'] + '}{' + body + '}')
        for st in p['stories']:
            st_body = _join_body(st['body'])
            out.append(r'\asidestory{' + st['headline'] + '}{' + st_body + '}')
        out.append(r'\end{mainaside}')
        if p['pullquote']:
            out.append(r'\vspace{0.5mm}')
            out.append(r'\pullquote{' + p['pullquote'] + '}')
    else:
        # 等宽多栏（默认）
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
        if p['body']:
            col_opt = '[' + p['columns'] + ']' if p['columns'] else ''
            out.append(r'\begin{storycolumns}' + col_opt)
            out.append(r'\noindent ' + p['body'][0])
            for para in p['body'][1:]:
                out.append('')
                out.append(para)
            out.append(r'\end{storycolumns}')
        if p['pullquote']:
            out.append(r'\vspace{0.5mm}')
            out.append(r'\pullquote{' + p['pullquote'] + '}')
        # 副故事
        for st in p['stories']:
            if st['headline']:
                out.append(r'\vspace{1mm}')
                out.append(r'\subheadline{' + st['headline'] + '}')
            for para in st['body']:
                out.append('')
                out.append(r'\noindent ' + para if not para.startswith('\\noindent') else para)
    # In Brief
    if p['briefs']:
        label = 'IN BRIEF'
        items = p['briefs'][:3]
        while len(items) < 3:
            items.append('')
        out.append(r'\vspace{1mm}')
        out.append(r'\inbrief{' + label + '}{' + items[0] + '}{' + items[1] + '}{' + items[2] + '}')
    out.append(r'\end{plate}')
    return '\n'.join(out)


def _join_body(paras: list) -> str:
    r"""正文段列表 → 单字符串（段间 \par，用于宏参数内分段）。"""
    return r'\par '.join(paras)

def main() -> int:
    ap = argparse.ArgumentParser(description='plates/*.md → LaTeX 生成器')
    ap.add_argument('plates_dir', help='plates/ 目录')
    ap.add_argument('output', help='输出 .tex 路径')
    ap.add_argument('--docopts', default='paper=a3,landscape,plates=2,columns=3',
                    help='linotype.cls 选项（逗号分隔）')
    ap.add_argument('--class', dest='clsname', default='linotype',
                    help='文档类名（默认 linotype）')
    ap.add_argument('--theme', default='',
                    help='主题: newspaper|magazine|brief（追加到 docopts）')
    args = ap.parse_args()
    if args.theme and f'theme={args.theme}' not in args.docopts:
        args.docopts = args.docopts.rstrip(',') + f',theme={args.theme}'

    # 读 plates（按文件名排序）
    files = sorted([f for f in os.listdir(args.plates_dir) if f.endswith('.md')])
    if not files:
        print('错误: plates 目录无 .md 文件')
        return 1

    out = [r'\documentclass{' + args.clsname + '}',
           r'\linotypesetup{' + args.docopts + '}',
           r'\begin{document}']
    # 版组织: 默认每页 1 版（单版模式）；双版时每页 2 版并排
    plates = []
    for i, fname in enumerate(files, 1):
        text = open(os.path.join(args.plates_dir, fname), encoding='utf-8').read()
        p = parse_plate(text)
        plates.append(render_plate(p, i))
    if 'plates=2' in args.docopts:
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

    tex = '\n'.join(out)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(tex)
    print(f'已生成 {args.output} ({len(files)} 版)')
    # 生成 layout.json（pixelcheck --layout auto 消费）: 每版布局类型
    # main-aside → multi(多栏网格); 其他 → single(等宽多栏)
    layouts = {}
    for i, fname in enumerate(files, 1):
        text = open(os.path.join(args.plates_dir, fname), encoding='utf-8').read()
        p = parse_plate(text)
        layouts[f'p{i}'] = 'multi' if p['layout'] == 'main-aside' else 'single'
    layout_json = {
        'sheets': {'front': list(layouts.keys())},
        'layout': layouts,
    }
    out_dir = os.path.dirname(os.path.abspath(args.output))
    with open(os.path.join(out_dir, 'layout.json'), 'w', encoding='utf-8') as f:
        json.dump(layout_json, f, ensure_ascii=False, indent=1)
    print(f'已生成 layout.json ({len(layouts)} 版布局)')
    return 0

if __name__ == '__main__':
    sys.exit(main())
