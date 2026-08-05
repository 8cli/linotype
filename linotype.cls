% =====================================================================
% linotype.cls — 通用印刷排版文档类（LaTeX 引擎）
%
% 用法（配置驱动，不绑定具体报纸）:
%   \documentclass[
%     paper=a3,            % 纸张: a3 | a4 | letter (默认 a3)
%     landscape,           % 横版 (默认竖版)
%     plates=2,            % 每张纸的版数: 2 (A3 双版) | 1 (单版) (默认 2)
%     columns=3,           % 正文栏数 (默认 3)
%     bodyfont=<font>,     % 正文字体族名 (默认 Newsreader)
%     displayfont=<font>,  % 标题字体族名 (默认 Playfair Display)
%     sansfont=<font>,     % 无衬线小字字体族名 (默认 Inter)
%     fontpath=<path>,     % 字体文件目录 (默认 ./fonts)
%     ink=<hex>,           % 墨色 (默认 1A1A1A)
%     accent=<hex>,        % 强调色 (默认 8C1D18)
%     papercolor=<hex>,    % 纸色 (默认 FFFFFF)
%   ]{linotype}
%
% 版式组件（可选，按需使用）:
%   \masthead{刊名}{期号}{标语}     — 报头（双细线 + 刊名 + 期号 + 标语）
%   \sectionstrip{栏目}{日期}      — 内页眉题条
%   \kicker{眉题}                   — 眉题（强调色全大写）
%   \headline{标题}                 — 主标题（display 字体）
%   \subheadline{副标题}            — 次标题
%   \deck{导语}                     — 斜体导语
%   \byline{署名}                   — 署名
%   \storybody                      — 正文（按 columns 分栏）
%   \pullquote{引文}                — 引文框（上下细线）
%   \inbrief{标题}{条目1}{条目2}{条目3} — In Brief 摘要条（可 1-3 条）
%   \plate 环境                     — 单版容器（内容区固定高度）
%
% QA: LaTeX 原生 Overfull/Underfull 警告 = 溢出/空隙检测（编译期可见）
% =====================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{linotype}[2026/08/05 v1.1 Generic typesetting class]
\LoadClass[11pt]{article}

% 引擎检查（借鉴 modernnewspaper）: fontspec 依赖 XeLaTeX/LuaLaTeX
\RequirePackage{iftex}
\ifPDFTeX
  \ClassError{linotype}{pdfLaTeX is not supported}{Use XeLaTeX or LuaLaTeX for Unicode and fontspec support}
\fi

% 溢出检测哲学: 只报 Overfull（真溢出），静默欠满（badness ≤ 10000）。
% 欠满（内容少于版心）不是缺陷——报纸版式允许列尾空隙；只有溢出才需修复。
% 血泪: multicol 平衡/plate 版心盒的欠满必报 badness 10000，每条 plate 一条
% 噪音，把真溢出的 Overfull 淹没。全局 \vbadness=10000 过滤之。
\vbadness=10000

% ---------- 参数解析 ----------
% 配置通过 \linotypesetup（可选命令，build.py 生成）：
%   \linotypesetup{paper=a3,landscape,columns=3,plates=1,ink=1A1A1A,accent=8C1D18}
% 文档类不带选项（类选项与 geometry 键值冲突，弃用）。
\makeatletter
\RequirePackage{keyval}
\newif\if@landscape\@landscapefalse
\newif\if@twoplate\@twoplatefalse
\def\@papersize{a3}
\def\linotype@columns{3}
% 文档级公开宏（无 @）——文档正文里 @ 是 catcode 12，
% \linotype@columns 不能直接写，必须经此宏展开（展开在定义时已定格）。
\newcommand{\linotypecols}{\linotype@columns}
\def\@plates{1}
\def\@ink{1A1A1A}
\def\@accent{8C1D18}
\def\@papercolor{FFFFFF}
% 字体配置（族名）——fontconfig 自动匹配变体，用户给任意已装字体族名即可
\def\@bodyfont{Newsreader}
\def\@displayfont{Playfair Display}
\def\@sansfont{Inter}
\def\@fontpath{/home/yupeng/.fonts}
% 正文基准字号（autofit 的调整参数；所有原子按固定比例缩放，默认 9.5pt）
% 血泪: 原子字号硬编码时无法整体缩放——必须比例化，协调性才有数学保证。
\newlength{\linotype@bs}\setlength{\linotype@bs}{9.5pt}
% 主题: newspaper(默认) | magazine | brief
\def\@theme{newspaper}
% 显式设置 flag（theme 只填充未显式设置的项）
\newif\if@bodyfontset\newif\if@displayfontset\newif\if@sansfontset
\newif\if@inktextset\newif\if@accentset\newif\if@papercolorset

\define@key{linotype}{paper}{\def\@papersize{#1}}
\define@key{linotype}{landscape}[true]{\@landscapetrue}
\define@key{linotype}{portrait}[true]{\@landscapefalse}
\define@key{linotype}{columns}{\def\linotype@columns{#1}}
\define@key{linotype}{plates}{\def\@plates{#1}\ifstrequal{#1}{2}{\@twoplatetrue}{\@twoplatefalse}}
\define@key{linotype}{ink}{\def\@ink{#1}\@inktextsettrue}
\define@key{linotype}{accent}{\def\@accent{#1}\@accentsettrue}
\define@key{linotype}{papercolor}{\def\@papercolor{#1}\@papercolorsettrue}
\define@key{linotype}{bodyfont}{\def\@bodyfont{#1}\@bodyfontsettrue}
\define@key{linotype}{displayfont}{\def\@displayfont{#1}\@displayfontsettrue}
\define@key{linotype}{sansfont}{\def\@sansfont{#1}\@sansfontsettrue}
\define@key{linotype}{fontpath}{\def\@fontpath{#1}}
\define@key{linotype}{theme}{\def\@theme{#1}}
\define@key{linotype}{bodyfontsize}{\setlength{\linotype@bs}{#1}}

% 主题应用: 在 setkeys 后调用（此时所有显式 key 已解析）。
% 只填充"未显式设置"的项——显式 bodyfont/accent 优先于主题。
\newcommand{\linotype@applytheme}{%
  \ifnum\strcmp{\@theme}{magazine}=0
    % 杂志: Charter 正文（更紧凑的衬线）+ 深蓝强调
    \if@bodyfontset\else\def\@bodyfont{Bitstream Charter}\fi
    \if@displayfontset\else\def\@displayfont{Playfair Display}\fi
    \if@accentset\else\def\@accent{1B3A5C}\fi
    \if@inktextset\else\def\@ink{1A1A1A}\fi
  \else\ifnum\strcmp{\@theme}{brief}=0
    % 简报: 单色极简（强调色 = ink）
    \if@bodyfontset\else\def\@bodyfont{Newsreader}\fi
    \if@displayfontset\else\def\@displayfont{Playfair Display}\fi
    \if@accentset\else\def\@accent{1A1A1A}\fi
    \if@inktextset\else\def\@ink{1A1A1A}\fi
  \else
    % newspaper(默认): Newsreader + 深红强调
    \if@bodyfontset\else\def\@bodyfont{Newsreader}\fi
    \if@displayfontset\else\def\@displayfont{Playfair Display}\fi
    \if@accentset\else\def\@accent{8C1D18}\fi
    \if@inktextset\else\def\@ink{1A1A1A}\fi
  \fi\fi
}
\newcommand{\linotypesetup}[1]{%
  \setkeys{linotype}{#1}%
  \linotype@applytheme
  % 按最终 paper 尺寸设几何（必须在 \setkeys 后，\@papersize 已定）。
  % 血泪：etoolbox \ifstrequal{\@papersize}{a3} 永远 FALSE——
  % 其底层 \detokenize 不展开宏参数（"\@papersize"≠"a3"）。
  % 必须用 XeTeX 原语 \strcmp（完全展开参数后比较，实测可靠）。
  \ifnum\strcmp{\@papersize}{a4}=0
    \if@landscape\geometry{a4paper,landscape,margin=0mm}\else\geometry{a4paper,margin=0mm}\fi
  \else\ifnum\strcmp{\@papersize}{letter}=0
    \if@landscape\geometry{letterpaper,landscape,margin=0mm}\else\geometry{letterpaper,margin=0mm}\fi
  \else
    \if@landscape\geometry{a3paper,landscape,margin=0mm}\else\geometry{a3paper,margin=0mm}\fi
  \fi\fi
}
% 注: 类文件由内核 \@input 读取时自带 \makeatletter，全程 @ 为字母，
% 因此不能在这里 \makeatother —— 否则下方 \@ink/\@accent/\if@twoplate
% 等全部被拆成 \@ + 文本，报 "Missing number"（血的教训，勿复加）。

% ---------- 纸张几何 ----------
\RequirePackage{etoolbox}
\RequirePackage{geometry}
% 初始 geometry（\linotypesetup 会重设）；默认 A3 竖版
\geometry{a3paper,margin=0mm}
% 几何常量（setup 后由 \paperwidth/\paperheight 派生，无需手设）
% 纸张尺寸（mm）——用 \paperwidth/\paperheight（geometry 设置后可用）
\newlength{\paperW}\newlength{\paperH}
\AtBeginDocument{%
  \setlength{\paperW}{\paperwidth}%
  \setlength{\paperH}{\paperheight}%
}

% ---------- 基础包 ----------
\RequirePackage{fontspec}
\RequirePackage{xcolor}
\RequirePackage{multicol}
\RequirePackage{graphicx}
\RequirePackage{calc}
\RequirePackage{xstring}  % \StrDel: 族名去空格 → 文件名前缀
% 英文断字（CSS hyphens:auto 的对应物）——没有它英文不断字，
% 行数增多 ~25%，内容超出版心。核心组件。
\RequirePackage[english]{babel}

% ---------- 字体（配置化，AtBeginDocument 动态加载） ----------
% 血泪: \linotypesetup 在 preamble 调用，字体族名到那时才最终确定，
% 故 \newfontfamily 必须延迟到 AtBeginDocument（\@bodyfont 已定）。
% 加载方式: 族名 + fontconfig 自动查找变体（Regular/Bold/Italic）。
% 用户给族名即可用任意已装字体（fc-list 可见），无需知道文件名。
% fontpath 保留作兜底参数（默认字体已注册时无需关心）。
\AtBeginDocument{%
  \newfontfamily\fontbody{\@bodyfont}%
  \newfontfamily\fontdisplay{\@displayfont}%
  \newfontfamily\fontsans{\@sansfont}%
  \setmainfont{\@bodyfont}%
}

% ---------- 版面几何 ----------
% 版内容区: 内边距 上20/下16/左15/右15mm；硬边界 = 高−16mm
\newlength{\padTop}\setlength{\padTop}{20mm}
\newlength{\padBottom}\setlength{\padBottom}{16mm}
\newlength{\padSide}\setlength{\padSide}{15mm}
\newlength{\contentW}\newlength{\contentH}
\newbox\linotype@platebox  % plate 内容收集盒（vsplit 截断用）
\newlength{\colGap}\setlength{\colGap}{3.75mm}
\newlength{\colW}\newlength{\mainW}
\newlength{\boundary}
% ---------- 颜色（必须在 AtBeginDocument 定义：此时 preamble 的
% \linotypesetup 已执行，\@ink/\@accent 才是用户配置的最终值）----------
\AtBeginDocument{%
  \definecolor{ink}{HTML}{\@ink}%
  \definecolor{accent}{HTML}{\@accent}%
  \definecolor{paper}{HTML}{\@papercolor}%
  \color{ink}%
}

% 派生长度：依赖 \paperW/\paperH（geometry 设置后），放 AtBeginDocument
\AtBeginDocument{%
  \setlength{\paperW}{\paperwidth}%
  \setlength{\paperH}{\paperheight}%
  \if@twoplate
    \setlength{\contentW}{0.5\paperW - 2\padSide}%
  \else
    \setlength{\contentW}{\paperW - 2\padSide}%
  \fi
  \setlength{\contentH}{\paperH - \padTop - \padBottom}%
  \setlength{\colW}{0.3333\contentW}%
  \setlength{\mainW}{0.6666\contentW + \colGap}%
  \setlength{\boundary}{\paperH - \padBottom}%
  % 段落格式（依赖 \colGap）
  \setlength{\parindent}{1em}%
  \setlength{\parskip}{0pt}%
  \setlength{\columnsep}{\colGap}%
  \setlength{\multicolsep}{0pt}%
  \setlength{\premulticols}{0pt}%
  \setlength{\postmulticols}{0pt}%
  \setlength{\columnseprule}{0pt}%
}

% ---------- 版式原子 ----------
\newcommand{\hairrule}{\par\noindent\rule{\contentW}{0.4pt}\par}

% 报头元数据配置（借鉴 modernnewspaper 的 \Set* 风格）:
% 独立命令（非 keyval）——长文本含逗号时不会被 keyval 拆开。
\def\@tagline{AN INDEPENDENT NEWSPAPER OF WORLD AFFAIRS}
\newcommand{\SetTagline}[1]{\def\@tagline{#1}}
\newcommand{\SetMastheadFont}[1]{\def\@mastheadfont{#1}}  % 预留：报头字体族

% 报头：双细线 + 刊名(display 40pt) + 期号行 + 标语 + 双细线收尾
\newcommand{\masthead}[3]{%
  \noindent\rule{\contentW}{0.4pt}\\[1pt]
  \noindent\rule{\contentW}{0.4pt}\\[1.5mm]
  {\fontsans\fontsize{7.5pt}{9pt}\selectfont\addfontfeature{LetterSpace=10}%
  \color{accent}\textbf{\MakeUppercase{#2}}%
  \hfill\color{ink}\textbf{#3}}\\[1mm]
  \noindent\rule{\contentW}{0.4pt}\\[1pt]
  \noindent\rule{\contentW}{0.4pt}\\[2mm]
  \begin{center}
  {\fontdisplay\fontsize{40pt}{38pt}\selectfont\bfseries #1}\\[1.5mm]
  {\fontsans\fontsize{7pt}{9pt}\selectfont\addfontfeature{LetterSpace=34}%
  \color{ink}\MakeUppercase{\@tagline}}\\[1mm]
  \end{center}
  \noindent\rule{\contentW}{0.4pt}\\[1pt]
  \noindent\rule{\contentW}{0.4pt}\\[3mm]
}

% 内页眉题条
\newcommand{\sectionstrip}[2]{%
  \noindent\rule{\contentW}{0.4pt}\\[1pt]
  \noindent\rule{\contentW}{0.4pt}\\[1.5mm]
  {\fontsans\fontsize{8pt}{10pt}\selectfont\addfontfeature{LetterSpace=12}%
  \color{accent}\textbf{\MakeUppercase{#1}}%
  \hfill\color{ink}\MakeUppercase{#2}}\\[1mm]
  \noindent\rule{\contentW}{0.4pt}\\[1pt]
  \noindent\rule{\contentW}{0.4pt}\\[3mm]
}

% Kicker 眉题
\newcommand{\kicker}[1]{\par\noindent{\fontsans\fontsize{\dimexpr\linotype@bs*79/100\relax}{\dimexpr\linotype@bs*95/100\relax}\selectfont%
  \addfontfeature{LetterSpace=12}\color{accent}\textbf{\MakeUppercase{#1}}\par\vspace{0.8mm}}}

% 主标题
\newcommand{\headline}[1]{\par\noindent{\fontdisplay\fontsize{\dimexpr\linotype@bs*358/100\relax}{\dimexpr\linotype@bs*379/100\relax}\selectfont\bfseries#1\par\vspace{0.5mm}}}

% 跨栏标题（借鉴 papertex 的 \expandedtitle）: 全版宽，打破所有栏。
% 在进入 storycolumns 前调用，标题独占整行（宽 = \contentW）。
\newcommand{\expandedtitle}[1]{%
  \par\noindent{\fontdisplay\fontsize{26pt}{28pt}\selectfont\bfseries#1\par}%
  \noindent\rule{\contentW}{0.4pt}\par
  \vspace{0.8mm}%
}

% 副标题
\newcommand{\subheadline}[1]{\par\noindent{\fontdisplay\fontsize{\dimexpr\linotype@bs*158/100\relax}{\dimexpr\linotype@bs*179/100\relax}\selectfont#1\par\vspace{0.5mm}}}

% 导语
\newcommand{\deck}[1]{\par\noindent{\fontbody\fontsize{\dimexpr\linotype@bs*158/100\relax}{\dimexpr\linotype@bs*195/100\relax}\selectfont\itshape#1\par\vspace{0.5mm}}}

% 署名
\newcommand{\byline}[1]{\par\noindent{\fontsans\fontsize{\dimexpr\linotype@bs*84/100\relax}{\dimexpr\linotype@bs*100/100\relax}\selectfont%
  \addfontfeature{LetterSpace=8}\textbf{\MakeUppercase{#1}}\par\vspace{0.5mm}}}

% 正文（进入分栏环境前调用）
\newcommand{\storybody}{\fontbody\fontsize{\linotype@bs}{\dimexpr\linotype@bs*130/100\relax}\selectfont}

% 正文分栏环境：multicol + 版心栏高 + 溢出警告恢复
% 血泪1: multicol 栏高预算取 \@colht（= \textheight 整页 297mm）而非版心
% \contentH（261mm）→ 内容排满整页而非停在版心，双版时右版被推到下一页
% （空白首页 + 3 页）。必须显式设 \@colht\contentH 和 \@colroom\contentH
% （@colht 栏高预算、@colroom boxed 平衡基准，两者都须设）。
% 血泪2: multicol 的 \balance@columns 内部设 \vbadness\@M(10000) 和
% \vfuzz\maxdimen，\endmulticols 的环境 \endgroup 会回滚 —— 但为保证
% 显式恢复（防嵌套/变体），结束仍设回正常值。
% 注意: \@colht/\@colroom 是全局量，双版两 plate 共用 —— 每个 storycolumns
% 进入时都设，天然覆盖两个 plate；无残留副作用。
% storycolumns: 正文分栏环境（借鉴 papertex 的 news 环境——支持每版独立列数）
% 可选参数 [列数] 覆盖全局 \linotypecols（默认用全局）。
\newenvironment{storycolumns}[1][\linotypecols]{%
  % 版心栏高: multicol 栏高预算取 \@colht（=\textheight 整页 297mm）而非版心
  % \contentH（261mm）→ 内容排满整页而非停在版心。进入时设 \@colht/\@colroom
  % = \contentH，让多栏平衡到版心。
  % 血泪: \@colht/\@colroom 是页面级全局量！multicol 结束后必须恢复为
  % \textheight，否则后续 plate 的分页判断用错误的栏高（双版第二版被推走、
  % 空白首页）。
  \global\@colht\contentH%
  \global\@colroom\contentH%
  \begin{multicols}{#1}%
  \storybody
}{%
  \end{multicols}%
  \global\@colht\textheight%
  \global\@colroom\textheight%
  \vbadness=10000 \vfuzz=0.1pt%
}

% 主栏+侧栏布局（报纸经典: main 跨 2 栏 + aside 第 3 栏）
% CSS 版 P2-P4 用此布局（.main-col grid-column: 1/span 2 + .aside-col 第 3 栏），
% 内容在 9.5pt 下放得下 261mm 版心；而 3 等栏每栏窄 → 行数多 → 超高 105pt。
% 用法:
%   \begin{mainaside}
%     \mainstory{眉题}{标题}{导语}{署名}{body段...}   — 主栏（2 栏分栏）
%     \asidestory{标题}{body段...}                    — 侧栏（第 3 栏）
%     \asidestory{标题}{body段...}
%   \end{mainaside}
% 几何: main 宽 = 2×57.5 + 3.75 = 118.75mm; aside 宽 = 57.5mm
\newlength{\asideW}
\newenvironment{mainaside}{%
  \par\noindent%
  \setlength{\mainW}{0.6666\contentW + \colGap}%   % 2 栏 + 1 沟 = 118.75mm
  \setlength{\asideW}{0.3333\contentW - \colGap}%  % 1 栏 - 沟 = 57.5mm
  \begin{minipage}[t]{\mainW}%
    \setlength{\parindent}{1em}%
}{%
  \end{minipage}%
  \hspace{\colGap}%
  \begin{minipage}[t]{\asideW}%
    \setlength{\parindent}{1em}%
  \end{minipage}%
}

% 主栏故事: 2 栏分栏正文
\newcommand{\mainstory}[5]{%
  \kicker{#1}%
  \headline{#2}%
  \deck{#3}%
  \byline{#4}%
  \global\@colht\contentH%
  \global\@colroom\contentH%
  \begin{multicols}{2}%
    \storybody
    #5%
  \end{multicols}%
  \global\@colht\textheight%
  \global\@colroom\textheight%
}

% 侧栏故事: 单栏正文
\newcommand{\asidestory}[2]{%
  \subheadline{#1}%
  \par\noindent{\fontbody\fontsize{\dimexpr\linotype@bs*95/100\relax}{\dimexpr\linotype@bs*123/100\relax}\selectfont #2}%
  \vspace{1.5mm}%
}

% 引文框：上 accent 下 ink 细线，19pt 斜体
\newcommand{\pullquote}[1]{%
  \par\vspace{0.5mm}%
  \noindent\rule{\contentW}{0.4pt}%
  \vspace{0.8mm}\par
  {\fontbody\fontsize{\dimexpr\linotype@bs*200/100\relax}{\dimexpr\linotype@bs*221/100\relax}\selectfont\itshape#1\par}%
  \vspace{0.8mm}\par
  \noindent\rule{\contentW}{0.4pt}%
  \par\vspace{0.5mm}%
}

% In Brief 摘要条（3 条并排，参数: 标题 + 3 条内容）
\newcommand{\inbrief}[4]{%
  {\fontsans\fontsize{\dimexpr\linotype@bs*79/100\relax}{\dimexpr\linotype@bs*95/100\relax}\selectfont\addfontfeature{LetterSpace=12}\textbf{#1}}\\[0.5mm]
  \noindent\rule{\contentW}{0.4pt}\\[1.5mm]
  \begin{minipage}[t]{0.319\contentW}
  {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #2}
  \end{minipage}\hspace{0.02\contentW}%
  \begin{minipage}[t]{0.319\contentW}
  {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #3}
  \end{minipage}\hspace{0.02\contentW}%
  \begin{minipage}[t]{0.319\contentW}
  {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #4}
  \end{minipage}%
}

% ---------- 版（Plate）容器 ----------
% 固定版心高度，内容超出会 Overfull（编译期报错，不静默裁剪）
% 用法（build.py 生成）:
%   \begin{plate} 内容 \end{plate}         — 单版（一版一页）
%   \begin{plate} A \end{plate}%           — 双版并排（页内放两个）
%   \begin{plate} B \end{plate}\newpage
% 实现: 外层 版宽 minipage，内层内容盒（固定 \contentH）。
% \vspace 在 minipage 内第一行之前会吞掉，改用 \hrule 占位 0 高 +
% 显式 \vspace*。实际用验证过的嵌套模式。
\newenvironment{plate}{%
  % 注意: 开头只能 \noindent，不能 \par\noindent！
  % 1) \par 会把双版模式第二个 plate 推到下一行（minipage 需并排）
  % 2) \noindent 必须保留——minipage 的 \leavevmode 触发顶层段落，
  %    顶层 parindent(1em) + 整版宽 minipage 溢出恰好 1em（血泪：10.95pt Overfull）
  \noindent%
  \if@twoplate
    \begin{minipage}[t]{0.5\paperW}%
      \vspace*{\padTop}%
      \hspace{\padSide}%
  \else
    \begin{minipage}[t]{\paperW}%
      \vspace*{\padTop}%
      \hspace{\padSide}%
  \fi
      % 版心内容盒: vbox 收集 + \@colht\contentH 限高 + vsplit 截断兜底。
      % 血泪（2026-08-05 决定性发现）:
      %  1) 纯 \vbox 收集 + vsplit（旧方案）→ multicol 在 vbox 内 boxed 平衡到
      %     内容自然高（真实 P2 到 304mm），且 vsplit 无法切 multicol 整盒
      %     （只能全切或全留）→ 内容溢出到页面底部。
      %  2) 纯 \vtop to\contentH（中间方案）→ multicol 被 \@colht 限高到版心，
      %     但盒子超高时（内容自然高 > contentH）盒子 = 自然高 888pt → 超页面推走。
      % 正解（组合）: vbox 收集 + 显式 \@colht/\@colroom\contentH 让 multicol
      % 平衡到版心 + vsplit 截断兜底（内容仍超高时截到 contentH）。
      % 实测: 真实 P2 main-aside 从 304mm → 271mm，无溢出、无空白首页。
      \makeatletter
      \global\@colht\contentH%
      \global\@colroom\contentH%
      \makeatother
      \setbox\linotype@platebox=\vbox\bgroup
        \hsize\contentW
        \linewidth\contentW
        \textwidth\contentW
        \columnwidth\contentW
        \setlength{\parindent}{1em}%
        \setlength{\parskip}{0pt}%
        \setlength{\columnsep}{\colGap}%
        \setlength{\multicolsep}{0pt}%
        \setlength{\premulticols}{0pt}%
        \setlength{\postmulticols}{0pt}%
}{%
      \egroup
      % fill typeout（autofit 消费）: 总是输出内容高度，不只溢出时。
      % 格式: "Plate content: Xpt / contentH Ypt"（build.py 正则解析 → fill = X/Y）
      % 血泪: \dimexpr 表达式必须用 \relax 终结——空格会被跳过，
      % 后续的 "/" 会被当作除法运算符（"Missing number, treated as zero"）！
      \typeout{Plate content: \the\dimexpr\ht\linotype@platebox+\dp\linotype@platebox\relax / contentH \the\contentH}%
      % vsplit 兜底: 内容仍超高时截到版心（multicol 已被 @colht 限高，
      % 此分支主要处理非 multicol 内容的超高）
      \ifdim\dimexpr\ht\linotype@platebox+\dp\linotype@platebox>\contentH
        \typeout{Overfull plate: content \the\dimexpr\ht\linotype@platebox+\dp\linotype@platebox\relax > contentH \the\contentH}%
        \setbox\linotype@platebox=\vsplit\linotype@platebox to\dimexpr\contentH+2pt
      \fi
      \vbadness=10000
      \vbox to\contentH{\unvbox\linotype@platebox\vss}%
      \makeatletter
      \global\@colht\textheight%
      \global\@colroom\textheight%
      \makeatother
    \end{minipage}%
}
