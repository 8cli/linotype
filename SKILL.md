---
name: linotype
description: Use when the user asks to typeset, lay out, or print a newspaper, magazine, newsletter, or any multi-column print document (排版/印刷/报纸/杂志/多栏文档/生成 PDF). Generic LaTeX typesetting engine — config-driven, not bound to any publication.
---

# Linotype — 通用印刷排版引擎

## 概述

把任意内容（plates/*.md）排版成多栏印刷 PDF。核心是 **LaTeX 编译期溢出检测**：内容超版心 → Overfull 警告（编译时可见，优于 CSS 黑盒静默裁剪）。

**架构**：`plates/*.md`（内容）→ `build.py`（管线）→ `.tex` → `xelatex` → PDF + 编译日志。

**借鉴自成熟项目**：papertex（每版独立列数、跨栏标题）、modernnewspaper（`\Set*` 配置、引擎检查）、LiX（配置分层）。版心截断方案（vsplit + Overfull 警告）比上述项目更先进——内容超高时版面稳定不推页。

## 快速参考

```bash
# 1. 内容 → .tex + 自动版面调整（默认开启，见下方 autofit）
python3 build.py plates/ out.tex --docopts "paper=a3,landscape,columns=3,plates=2"
#    → autofit 自动编译迭代，收敛后直接产出 .tex + .pdf（无需手动编译）
#    → 溢出/太空自动调字号（8.5–11pt）与栏数（2–4）；纸张是硬约束不动
#    → 关闭自动调整（纯生成，需手动编译）:
#       python3 build.py plates/ out.tex --docopts "..." --no-autofit

# 2. 手动编译（--no-autofit 时；必须 xelatex，pdfLaTeX 会被类拒绝）
xelatex -interaction=nonstopmode -halt-on-error out.tex
#    → Overfull plate 警告 = 版心溢出检测（需修复或接受）
#    → Underfull \hbox = 行内空隙（轻微，可接受）

# 3. PDF 后处理检查（编译期 QA 的补充）
python3 pdfcheck.py out.pdf --log out.log --paper a3 --landscape --pages 2

# 4. 像素目检（可选，复用 CSS 时代工具 pixelcheck.py）
pdftoppm -png -r 60 out.pdf page
python3 ~/.claude/skills/linotype/scripts/pixelcheck.py page-1.png --layout auto
```

## 内容管线（plates/*.md 格式）

每版一个 `plates/pN.md`，标签行格式（**不是** markdown 标题）：

```
LAYOUT: main-aside        # 可选: ''(等宽多栏,默认) | main-aside(主栏2栏+侧栏1栏)
COLUMNS: 3                # 可选: 版独立列数（覆盖 --docopts 的全局 columns）
EXPANDEDTITLE: 跨栏标题    # 可选: 全版宽标题，打破所有栏
KICKER: 眉题
HEADLINE: 主标题
SUBHEADLINE: 副标题        # 可选
DECK: 导语
BYLINE: 署名
BODY:                     # 正文段（段间空行）
第一段...
第二段...
STORY-B: 副故事标题        # 可选，main-aside 布局的侧栏故事
副故事正文段...
STORY-C: 副故事标题        # 可选
PULLQUOTE: 引文            # 可选
BRIEFS:                   # 可选, In Brief 摘要条（3 条）
条目1...
条目2...
条目3...
```

**纪律**：只使用可核实的真实内容并标注信源（`Reuters reported` 等行内形式）；plates 是唯一事实源。

## 配置系统

### `\linotypesetup` 键值（build.py 的 --docopts 生成）

| 键 | 值 | 默认 | 说明 |
|---|---|---|---|
| `paper` | a3 / a4 / letter | a3 | 纸张 |
| `landscape` / `portrait` | — | portrait | 横/竖版 |
| `columns` | 2-4 | 3 | 全局栏数 |
| `plates` | 1 / 2 | 2 | 每页版数（2 = 双版并排） |
| `theme` | newspaper / magazine / brief | newspaper | 预置主题（字体+颜色） |
| `bodyfont` / `displayfont` / `sansfont` | 已装字体族名 | Newsreader / Playfair Display / Inter | 字体（fontconfig 自动匹配变体） |
| `bodyfontsize` | 长度 | 9.5pt | 正文基准字号（autofit 的调整参数；所有原子按固定比例缩放，协调性不变） |
| `ink` / `accent` / `papercolor` | hex | 1A1A1A / 8C1D18 / FFFFFF | 颜色 |

**主题**（显式 `bodyfont`/`accent` 优先于主题）：
- `newspaper`：Newsreader + Playfair + 深红强调（8C1D18）
- `magazine`：Bitstream Charter 正文 + 深蓝强调（1B3A5C）
- `brief`：单色极简（强调色 = ink）

### `\Set*` 命令（报头元数据，长文本含逗号时用独立命令）

```latex
\SetTagline{INDEPENDENT DAILY NEWS}   % 报头标语（默认 "AN INDEPENDENT NEWSPAPER OF WORLD AFFAIRS"）
```

## 版式原子（linotype.cls 提供）

| 命令 | 用途 |
|---|---|
| `\masthead{刊名}{期号}{标语}` | 报头（双细线 + 大刊名 + 期号 + 标语） |
| `\sectionstrip{栏目}{日期}` | 内页眉题条 |
| `\kicker{眉题}` | 眉题（强调色全大写） |
| `\headline{标题}` | 主标题（display 字体） |
| `\subheadline{副题}` | 次标题 |
| `\deck{导语}` | 斜体导语 |
| `\byline{署名}` | 署名 |
| `storycolumns` 环境 | 正文多栏（`[列数]` 可选覆盖全局） |
| `\pullquote{引文}` | 引文框（上下细线） |
| `\inbrief{标题}{条1}{条2}{条3}` | In Brief 摘要条（3 栏） |
| `\expandedtitle{标题}` | 跨栏标题（全版宽，打破所有栏，借鉴 papertex） |
| `mainaside` 环境 | 主栏 2 栏 + 侧栏 1 栏（报纸经典） |
| `\mainstory{眉题}{标题}{导语}{署名}{正文}` | mainaside 主栏故事 |
| `\asidestory{标题}{正文}` | mainaside 侧栏故事 |
| `plate` 环境 | 版容器（固定版心，超高 → Overfull 警告 + vsplit 截断） |

## QA 管线（强制，不通过不交付）

1. **Autofit 自动调整**（默认开启，`--no-autofit` 关闭）：内容溢出/太空时自动搜索收敛配置——
   - **边界**：字号 8.5–11pt（0.5pt 步进）+ 栏数 2–4；**纸张是硬约束，绝不动**
   - **方向**（multicol 平衡盒高 = 内容自然高/栏数，与 CSS 直觉相反）：溢出 → 缩字号 → 增栏数；太空 → 增字号 → 减栏数
   - **收敛**：0 Overfull 且最小利用率 ≥ 45%（太空容忍下界）。每轮输出迭代报告
   - **失败**：边界内无法放下 → 明确报告（历史最佳尝试 + 最满版利用率），退出码 1，PDF 仍保留供参考
   - 双版 + main-aside 的溢出（boxed multicol 硬限制）autofit 缩字号可缓解但未必收敛——诚实报告"无法放下"
2. **编译期检测**（--no-autofit 或手动编译时）：`Overfull plate: content Xpt > contentH Ypt` 警告 = 内容超版心。**必须**处理（修剪内容或调字号/版心）。
   - `Underfull \vbox` 已全局过滤（欠满非缺陷）
   - `Overfull \hbox` 微溢出 = 行内长词，可接受
3. **pdfcheck.py**：LOG OVERFLOW（Overfull plate > 0 → FAIL）、LOG ERROR、MEDIA BOX（纸张尺寸）、FONTS（≥3 种嵌入）、PAGES。退出码 0 = 通过。
4. **pixelcheck.py**（可选）：PDF → PNG 后检查列空白/底部溢出（版心底 ≤ 281mm）。
5. **run_tests.py**（回归，改过 build.py/linotype.cls 后必跑）：
   ```bash
   python3 ~/.claude/skills/linotype/tests/run_tests.py ~/news/latex
   ```
   覆盖：正向（编译/页数/字体）、负向（超长→Overfull 抓到）、转义、双版无空白首页、主题、autofit（溢出收敛/太空提升/边界失败/--no-autofit）。

## 环境

- **引擎**：xelatex（TeX Live）。pdfLaTeX 被类拒绝（fontspec 依赖）
- **字体**：fontconfig 族名加载（`fc-list` 可见的任意字体），默认 Newsreader / Playfair Display / Inter（`~/.fonts/` 已注册）
- **包**：geometry / multicol / fontspec / xcolor / babel(english) / keyval / etoolbox / calc / iftex / xstring

## 已知限制

- **双版 + main-aside 组合**：mainstory 的 multicol 在 minipage 内（boxed）不受 `\@colht` 限高，内容超高时排到页面底部（不推页、不出页面）。由 Overfull plate 警告检测；autofit 缩字号可缓解但未必收敛（mainstory 固定 2 栏，栏数旋钮无效）。单版模式无此问题（内容全在版心内）。
- **autofit 的栏数旋钮对 main-aside 无效**：mainstory 硬编码 multicol{2}（报纸经典布局），只有字号旋钮生效。
- **纯文字排版**：无图片/图表支持。

## 常见错误（血泪经验）

1. **不要用 pdfLaTeX** —— 类会拒绝（引擎检查）
2. **内容超高是正常状态**（内容密度变化）—— autofit 默认自动收敛；无法收敛时 Overfull 警告告诉你：修剪内容或调配置，不是 bug
3. **行距用 `\fontsize{size}{baselineskip}` 第二参数**，禁用 `\baselinestretch`（1.3 会变 1.56）
4. **英文断字必须 babel english** —— 否则行数 +25%，内容必溢出
5. **`\textbf\{...\}` 双转义** —— build.py 已修（先转义特殊字符再处理 markdown），手写 tex 别重复
6. **引号用 `` `` '' ``**（build.py 已转换中文弯引号），别用直引号
7. **plate 开头只能 `\noindent`**，`\par\noindent` 破坏双版并排
8. **pdfLaTeX 生成的 PDF 无字体嵌入** —— 用 xelatex 并 pdfcheck FONTS 验证
9. **`\dimexpr` 必须用 `\relax` 终结** —— 空格会被跳过，后续 `/` 被当作除法运算符（"Missing number, treated as zero"）
10. **测试/脚本里 build.py 记得 `--no-autofit`** —— autofit 默认开启会编译迭代（~3-35 秒），纯生成场景要显式关闭
11. **栏数对 multicol 盒高是 U 形曲线** —— 超长内容增栏数可能变差（实测 120 段 3→4 栏 244%→271%）；autofit 失败时报告历史最佳而非边界配置

## 何时使用 / 何时不用

- **Use when**：多栏印刷文档（报纸/杂志/简报/时事通讯），需要 PDF 输出、编译期溢出检测、配置驱动
- **When NOT**：需要图片/图表/装饰图形（纯文字排版）；单栏长文档（用 article/report）；HTML 交互输出（用 CSS）
