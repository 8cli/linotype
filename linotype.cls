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
% 血泪 #54: 禁用 \topskip——article 默认 11pt，plate 是页面第一个盒子
% （minipage[t] 首元素是 \vspace* 的 0 高 \hrule），页面级 \topskip 胶 =
% 11pt − 0 = 11pt（3.88mm）插在纸顶与 minipage 之间 → 每条版整体下移，
% 顶边距实际 23.8mm（设计 20）、底边距 12.2mm（设计 16），上下 24/12
% 违反"上 20/下 16、左右 15"设计契约且底边小于左右。所有页面都以
% plate 开头，\topskip=0 安全（multicol 用 \@colht 与 topskip 无关）。
\setlength{\topskip}{0pt}

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
\define@key{linotype}{bottommargin}{\def\@bottommargin{#1}}

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
  \else\ifnum\strcmp{\@theme}{financial}=0
    % 金融: 深绿强调（华尔街日报风）
    \if@bodyfontset\else\def\@bodyfont{Newsreader}\fi
    \if@displayfontset\else\def\@displayfont{Playfair Display}\fi
    \if@accentset\else\def\@accent{0F5132}\fi
    \if@inktextset\else\def\@ink{1A1A1A}\fi
  \else\ifnum\strcmp{\@theme}{sport}=0
    % 体育: 高对比亮橙 + 无衬线标题（动感）
    \if@bodyfontset\else\def\@bodyfont{Newsreader}\fi
    \if@displayfontset\else\def\@displayfont{Inter}\fi
    \if@accentset\else\def\@accent{E64A19}\fi
    \if@inktextset\else\def\@ink{1A1A1A}\fi
  \else\ifnum\strcmp{\@theme}{literary}=0
    % 文学: 深棕 + 衬线（书卷气）
    \if@bodyfontset\else\def\@bodyfont{Bitstream Charter}\fi
    \if@displayfontset\else\def\@displayfont{Playfair Display}\fi
    \if@accentset\else\def\@accent{5D4037}\fi
    \if@inktextset\else\def\@ink{1A1A1A}\fi
  \else
    % newspaper(默认): Newsreader + 深红强调
    \if@bodyfontset\else\def\@bodyfont{Newsreader}\fi
    \if@displayfontset\else\def\@displayfont{Playfair Display}\fi
    \if@accentset\else\def\@accent{8C1D18}\fi
    \if@inktextset\else\def\@ink{1A1A1A}\fi
  \fi\fi\fi\fi\fi
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
% 版内容区: 内边距 上20/下16(可调 bottommargin)/左15/右15mm；硬边界 = 高−下边距
% bottommargin: 版心底边距（autofit 的第三旋钮，边界 12-16mm）——溢出 < 一行时
% 微调版心而非动字号（\enlargethispage 对固定 \contentH 的 plate 盒子无效）
\def\@bottommargin{16mm}
\newlength{\padTop}\setlength{\padTop}{20mm}
\newlength{\padBottom}
\newlength{\padSide}\setlength{\padSide}{15mm}
\newlength{\contentW}\newlength{\contentH}
\newbox\linotype@platebox  % plate 内容收集盒（vsplit 截断用）
% mainstory 手动 vsplit 两栏用的盒/长度（2026-08-05 顶层化重构）
\newbox\linotype@mainbox    % 正文收集盒（按半宽排）
\newbox\linotype@splitbox   % vsplit 切出的左栏
\newbox\linotype@asidebox   % asidestory 内容盒
\newbox\linotype@headerbox  % mainstory 报头收集盒（量高度用）
\newlength\linotype@halfW   % 半栏宽 = (mainW - colGap)/2
\newlength\linotype@colH    % 每栏高度预算（vtop 栏高）
\newlength\linotype@splitH  % vsplit 切分高度（内容平衡 = 正文自然高/2）
\newlength\linotype@headerH % mainstory 报头高度
\newlength\linotype@spaceleft % 主栏补白剩余空间（colH − 正文栏高 − 最小间隔）
\newbox\linotype@briefbox  % 主栏左补白简讯盒（先测高再 vsplit 截断）
\newbox\linotype@briefboxR % 主栏右补白简讯盒（独立——\def 执行时才 \unvbox，
                           % 共用一盒会被 rightbrief 覆盖 → 两栏都显示右简讯）
\newbox\linotype@cutbox    % vsplit 截断后的简讯（剩余丢弃）
\newbox\linotype@maincol    % mainaside 主栏收集盒（2026-08-05 顶层化重构）
\newbox\linotype@asidecol   % mainaside 侧栏收集盒
\newbox\linotype@tmpbox     % 渲染临时盒
\newlength\linotype@topused  % 版顶已占高度（\dateline 日期线记录；mainaside/版头预算减掉）
\newlength\linotype@plateH   % 本版实际版心预算 = contentH − topused（mainaside 用）
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
  % bottommargin key 在 AtBeginDocument 才落地（\padBottom 此时最终确定）
  \setlength{\padBottom}{\@bottommargin}%
  \setlength{\contentH}{\paperH - \padTop - \padBottom}%
  \setlength{\colW}{0.3333\contentW}%
  \setlength{\mainW}{\dimexpr 0.6666\contentW - 0.3333\colGap\relax}%  % 2c/3 − g/3（血泪 #28: 原 +g 致每版水平溢出 10.6pt、两栏不对称）
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

% 内页眉题条（2026-08-07 修 strut bug: \rule+\\ 段落行带 strut → 规则对间距
% 5.1mm；改 \offinterlineskip + \hbox 行，规则对 0.5mm，几何精确）
\newcommand{\sectionstrip}[2]{%
  \par\noindent{\offinterlineskip
    \hbox{\vrule width\contentW height0.4pt}%
    \vskip1pt
    \hbox{\vrule width\contentW height0.4pt}%
    \vskip1.5mm
    \hbox to\contentW{{\fontsans\fontsize{8pt}{10pt}\selectfont\addfontfeature{LetterSpace=12}%
      \color{accent}\textbf{\MakeUppercase{#1}}}\hfil
      {\fontsans\fontsize{8pt}{10pt}\selectfont\addfontfeature{LetterSpace=12}%
      \color{ink}\MakeUppercase{#2}}}%
    \vskip1mm
    \hbox{\vrule width\contentW height0.4pt}%
    \vskip1pt
    \hbox{\vrule width\contentW height0.4pt}%
    \vskip3mm
  }%
}

% 版次日期线（第一版页顶，2026-08-07 用户要求: 每份报纸第一版加出版日期以便识别）:
% 双细线 + 居中日期（LetterSpace 14 全大写）+ 双细线收尾，形如迷你报头日期线。
% 高度记录到 \linotype@topused——mainaside/版头的版心预算必须减掉它:
% 日期线 + 满版 mainaside 若不减预算，plate vsplit 切不动 mainaside 整盒
% （只能全切或全留）→ 整个主栏被静默丢弃，只剩日期线。先排进临时盒量高、
% 再 \unvbox 输出（量高和渲染同一盒，高度精确）。
% 血泪（2026-08-07 probe）: 不能 \begin{center}（trivlist \topsep 把日期行推下
% 8mm、块高虚增 3×）；不能 \rule + \\（\leavevmode 段落行带 strut，规则对间距
% 5.1mm 而非 0.5mm）——\offinterlineskip + \hbox 行（无 strut）+ \hfil 居中，
% 几何精确可控（总高 ~6.7mm），且 \vbox 内量高与渲染同一盒。
\newcommand{\dateline}[1]{%
  \setbox\linotype@tmpbox=\vbox{%
    \offinterlineskip
    \hbox{\vrule width\contentW height0.4pt}%
    \vskip1pt
    \hbox{\vrule width\contentW height0.4pt}%
    \vskip1.5mm
    \hbox to\contentW{\hfil{\fontsans\fontsize{8pt}{10pt}\selectfont
      \addfontfeature{LetterSpace=14}\color{ink}\MakeUppercase{#1}}\hfil}%
    \vskip1mm
    \hbox{\vrule width\contentW height0.4pt}%
    \vskip1pt
    \hbox{\vrule width\contentW height0.4pt}%
    \vskip3mm
  }%
  \global\linotype@topused=\dimexpr\ht\linotype@tmpbox+\dp\linotype@tmpbox\relax
  \par\noindent\unvbox\linotype@tmpbox
}

% Kicker 眉题
\newcommand{\kicker}[1]{\par\noindent{\fontsans\fontsize{\dimexpr\linotype@bs*79/100\relax}{\dimexpr\linotype@bs*95/100\relax}\selectfont%
  \addfontfeature{LetterSpace=12}\color{accent}\textbf{\MakeUppercase{#1}}\par\vspace{0.8mm}}}

% 主标题
\newcommand{\headline}[1]{\par\noindent{\fontdisplay\fontsize{\dimexpr\linotype@bs*358/100\relax}{\dimexpr\linotype@bs*379/100\relax}\selectfont\bfseries#1\par\vspace{0.5mm}}}

% 跨栏标题（借鉴 papertex 的 \expandedtitle）: 全版宽，打破所有栏。
% 在进入 storycolumns 前调用，标题独占整行（宽 = \contentW）。
\newcommand{\expandedtitle}[1]{%
  % 比例化字号（血泪 #36）: 原固定 26pt——bodyfontsize 8.5→11pt 时正文
  % 原子线性缩放而跨栏标题纹丝不动（比例 3.06×→2.36×），autofit 缩字后
  % 标题视觉比例失调。26pt/9.5pt ≈ 274%。
  \par\noindent{\fontdisplay\fontsize{\dimexpr\linotype@bs*274/100\relax}{\dimexpr\linotype@bs*295/100\relax}\selectfont\bfseries#1\par}%
  \noindent\rule{\contentW}{0.4pt}\par
  \vspace{0.8mm}%
}

% 副标题
\newcommand{\subheadline}[1]{\par\noindent{\fontdisplay\fontsize{\dimexpr\linotype@bs*158/100\relax}{\dimexpr\linotype@bs*179/100\relax}\selectfont#1\par\vspace{0.5mm}}}
% 副条署名（2026-08-07 用户要求: 日期/站点/记者）——等宽多栏 STORY-B 用，
% 与 \byline 同款小字但更紧凑（栏窄）。侧栏由 \asidestory 内嵌渲染。
\newcommand{\storybyline}[1]{\par\noindent{\fontsans\fontsize{\dimexpr\linotype@bs*76/100\relax}{\dimexpr\linotype@bs*91/100\relax}\selectfont #1\par\vspace{0.5mm}}}

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
% 版头收集盒（2026-08-06 修复——血泪 #26）:
% 版头(kicker/headline/deck/byline)收集到独立盒，storycolumns 的 @colht =
% contentH − 版头实际高度。此前 @colht 用 \ht\linotype@platebox（vbox 构造中
% 读 =0）→ multicol 用满 contentH → 版头+multicol 超 contentH → vsplit 兜底
% 触发 → vsplit 切不动 multicol 整盒（血泪 #5）→ 整盒被丢弃 → 版面只剩版头
% （P3 双版实测 53.7mm，fill 却报 100%）。\plateheader 使版头高度可测。
\newenvironment{plateheader}{%
  % \global\setbox 关键（血泪 #26）: LaTeX 环境 \begin/\end 包 \begingroup/
  % \endgroup，\setbox 赋值在 \endgroup 时回滚 → storycolumns 读 headerbox=0
  % （版头高丢失 → @colht 满版 → vsplit 触发 → multicol 整盒被丢）。
  % \global 使赋值跨组保留。\unvcopy 而非 \unvbox（后者解包后清空盒寄存器）。
  \global\setbox\linotype@headerbox=\vbox\bgroup
    \hsize\contentW \linewidth\contentW \textwidth\contentW \columnwidth\contentW
}{%
  \egroup
  \unvcopy\linotype@headerbox
}

\newif\if@linotype@multicol  % platebox 含 multicol → vsplit 兜底跳过
\newenvironment{storycolumns}[1][\linotypecols]{%
  % 版心栏高: multicol 栏高预算取 \@colht/\@colroom = contentH − 版头实际高度
  % （\linotype@headerbox，\plateheader 收集）→ 多栏平衡到剩余空间，
  % 版头 + 多栏恰好填满版心。
  % 血泪: \@colht/\@colroom 是页面级全局量！multicol 结束后必须恢复为
  % \textheight，否则后续 plate 的分页判断用错误的栏高（双版第二版被推走、
  % 空白首页）。
  % 4pt 余量: multicol 平衡后盒高可能比 @colht 高 2-3pt（balance 溢出）。
  % 血泪 #26: vsplit 对 multicol 整盒是全切——plate 的 vsplit 兜底必须
  % 跳过含 multicol 的版（\if@linotype@multicol），否则超高时整盒被丢、
  % fill 虚高（745/742.6=100.3% 假达标）。multicol 超高时自然溢出 +
  % Overfull 报告 → autofit 缩字号（正确信号，不静默）。
  \global\@linotype@multicoltrue  % \global: \newif 的 true 是 \let 赋值，
                                  % \begin/\end 的 \begingroup 回滚 → plate 端
                                  % 读 false → vsplit 误触发丢 multicol
  \global\@colht\dimexpr\contentH-\linotype@topused-\ht\linotype@headerbox-\dp\linotype@headerbox-4pt\relax
  \global\@colroom\dimexpr\contentH-\linotype@topused-\ht\linotype@headerbox-\dp\linotype@headerbox-4pt\relax
  \begin{multicols}{#1}%
  \storybody
}{%
  \end{multicols}%
  \global\@colht\textheight%
  \global\@colroom\textheight%
  \vbadness=10000 \vfuzz=0.1pt%
}

% 主栏+侧栏布局（报纸经典: main 跨 2 栏 + aside 第 3 栏）
% 2026-08-05 顶层化重构: 收集式架构——mainstory/asidestory 渲染到各自的收集盒，
% 环境结束时统一 vsplit 截断到版心并并排输出。彻底解决:
%  1) 旧 minipage 结构缺陷: asidestory 全排在 main minipage 内（aside 空）→ main 超高
%  2) multicol boxed 限制: mainstory 手动 vsplit 两栏（绕开 boxed，实测平衡 429.6/430.0）
% 几何: main 宽 = 2×57.5 + 3.75 = 118.75mm; aside 宽 = 57.5mm
\newlength{\asideW}
\newenvironment{mainaside}{%
  \par\noindent%
  \setlength{\mainW}{\dimexpr 0.6666\contentW - 0.3333\colGap\relax}%  % 2c/3 − g/3 = 118.75mm（血泪 #28: 原 +g 溢出）
  \setlength{\asideW}{\dimexpr 0.3333\contentW - 0.6666\colGap\relax}% % c/3 − 2g/3 = 57.5mm
  % 版心预算（2026-08-07）: contentH − 版顶已占（\dateline 日期线）——否则
  % 日期线 + 满版 mainaside 超 contentH，plate vsplit 切不动整盒全丢。
  \setlength{\linotype@plateH}{\dimexpr\contentH-\linotype@topused\relax}%
  \global\setbox\linotype@maincol=\vbox{}%          % 清空收集盒
  \global\setbox\linotype@asidecol=\vbox{}%
}{%
  % main 栏截断到版心（防 header + 两栏 > plateH 的残余溢出）
  \ifdim\dimexpr\ht\linotype@maincol+\dp\linotype@maincol\relax>\linotype@plateH
    \typeout{Overfull main column: 内容 \the\dimexpr\ht\linotype@maincol+\dp\linotype@maincol\relax > plateH \the\linotype@plateH，截断}%
    \setbox\linotype@maincol=\vsplit\linotype@maincol to\dimexpr\linotype@plateH-10pt\relax
  \fi
  % aside 栏截断到版心（多 story 累计超高的兜底）
  \ifdim\dimexpr\ht\linotype@asidecol+\dp\linotype@asidecol>\linotype@plateH
    \typeout{Overfull aside column: 内容 \the\dimexpr\ht\linotype@asidecol+\dp\linotype@asidecol\relax > plateH \the\linotype@plateH，截断}%
    \setbox\linotype@asidecol=\vsplit\linotype@asidecol to\dimexpr\linotype@plateH-10pt\relax
  \fi
  % 并排输出: vtop 自然高（不用 to\contentH——vtop to 的 ht 参考点偏移导致
  % hbox 总高超 5.5pt，且报纸允许列尾空隙=欠满，无需强制填满）
  \par\noindent\hbox to\contentW{%
    \vtop{\hsize\mainW \linewidth\mainW\unvbox\linotype@maincol}%
    \hspace{\colGap}%
    \vtop{\hsize\asideW \linewidth\asideW\unvbox\linotype@asidecol}%
  }%
  \par\vspace{0.5mm}%
}

% 主栏故事: 手动 vsplit 两栏（2026-08-05 顶层化重构）
% 血泪: multicol 在 minipage 内（boxed）跳过 \@colroom 封顶（multicol.sty:760），
% 内容超高排自然高，且 plate 的 vsplit 切不动内嵌 multicol 整盒 → 溢出页面底。
% 解法: 内容按半宽排进 vbox，\vsplit 动态切半（probe 实测左右栏 429.6/430.0pt
% 平衡），超高时截断到版心预算 + Overfull 警告——完全绕开 boxed 限制。
% 渲染结果追加进 \linotype@maincol（mainaside 结束统一截断并排）。
% 栏底补白简讯（2026-08-07 用户要求: P1 主栏底部空 37-41mm——主条 340 词
% 自然高/2 = 481pt < colH 上限 598pt，\vss 留白；报纸标准做法是栏底补白）。
% #1 = 单条简讯文本（build.py 已转义，可含 \textbf{标题:}）；空参自动跳过。
% 排进 vtop 的 \vss 之后 → 内容顶对齐、简讯底对齐（补白不占正文空间）。
\newcommand{\mainbrief}[1]{%
  \ifx\empty#1\empty\else
    \par\vspace{0.6mm}%
    \noindent{\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #1\par}%
  \fi
}
\newcommand{\mainstory}[7]{%
  % 版头收集到独立盒（测实际高度；\storybody 设字体防 \deck/\byline 继承默认 11pt）
  \global\setbox\linotype@headerbox=\vbox{%
    \hsize\mainW \linewidth\mainW
    \storybody
    \kicker{#1}%
    \headline{#2}%
    \deck{#3}%
    \byline{#4}%
  }%
  \setbox\linotype@tmpbox=\vbox{%
    \hsize\mainW \linewidth\mainW
    \unvcopy\linotype@headerbox
    % 正文按半宽排: halfW = (mainW - colGap)/2（两栏 + 沟 = mainW）
    \setlength{\linotype@halfW}{0.5\dimexpr\mainW-\colGap\relax}%
    \setbox\linotype@mainbox=\vbox{%
      \hsize\linotype@halfW \linewidth\linotype@halfW
      \storybody
      #5%
    }%
    % 切分高度: 平衡（正文自然高/2）——两栏内容量相等（vsplit 切行界）
    \setlength{\linotype@splitH}{0.5\dimexpr\ht\linotype@mainbox+\dp\linotype@mainbox\relax}%
    % 栏高（vtop to）: 无栏底补白时 = splitH（血泪 #49: 原上限把单栏算成
    % 总高一半 → 主栏底部空 66mm；min(正文/2, contentH−版头) 让短正文栏高
    % = 正文/2，主栏欠满但平衡）。
    % 有栏底补白（#6/#7 非空，2026-08-07）时: 栏高 = contentH − 版头——
    % 正文 + \vss 弹性填充 + \mainbrief 贴底，正好填满；切分仍按正文/2
    % （内容平衡），vss 吸收剩余空间。
    \ifx\empty#6\empty
      \ifx\empty#7\empty
        \setlength{\linotype@colH}{\linotype@splitH}%
        \setlength{\linotype@colH}{\minof{\linotype@colH}{\dimexpr\contentH-\linotype@topused-\ht\linotype@headerbox-\dp\linotype@headerbox\relax}}%
      \else
        % 预留 12pt: vtop 的 dp（简讯末行 descender）溢出 colH，实测 ~10pt，
        % 触发 main column vsplit 截断切掉简讯末行；预留后 版头+colH+dp ≤ contentH
        \setlength{\linotype@colH}{\dimexpr\contentH-\linotype@topused-\ht\linotype@headerbox-\dp\linotype@headerbox-12pt\relax}%
      \fi
    \else
      \setlength{\linotype@colH}{\dimexpr\contentH-\linotype@topused-\ht\linotype@headerbox-\dp\linotype@headerbox-12pt\relax}%
    \fi
    % vsplit 切两栏（按 splitH 内容平衡切分，超高 → Overfull 警告）
    \setbox\linotype@splitbox=\vsplit\linotype@mainbox to\linotype@splitH
    \ifdim\dimexpr\ht\linotype@mainbox+\dp\linotype@mainbox>\linotype@splitH
      \typeout{Overfull mainstory: 内容超高，截断 \the\dimexpr\ht\linotype@mainbox+\dp\linotype@mainbox-\linotype@splitH\relax}%  % 血泪 #37: \the 已含 pt，再拼 pt 变 744.34ptpt
      \setbox\linotype@mainbox=\vsplit\linotype@mainbox to\linotype@splitH
    \fi
    % 并排两栏（vtop to colH 固定栏高）。
    % 栏底补白（#6/#7，2026-08-07 重构——血泪: 纯 \vss\mainbrief 在
    % 正文+简讯 > colH 时 vss 压到 0，简讯紧贴正文最后一行（视觉重叠））。
    % 正确做法: 简讯盒先测高 → vsplit 截断到剩余空间（colH − 正文栏高 −
    % 3mm 最小间隔）→ vtop 里 \vskip 3mm plus 1fil（最小间隔 + 弹性贴底）。
    % 空间足够 → 简讯贴底；空间不足 → 截断不溢出，绝不与正文重叠。
    \ifx\empty#6\empty
      \def\linotype@leftbrief{}%
    \else
      \setbox\linotype@briefbox=\vbox{\hsize\linotype@halfW \linewidth\linotype@halfW \storybody\mainbrief{#6}}%
      \setlength{\linotype@spaceleft}{\dimexpr\linotype@colH-\ht\linotype@splitbox-\dp\linotype@splitbox-3mm\relax}%
      \ifdim\dimexpr\ht\linotype@briefbox+\dp\linotype@briefbox>\linotype@spaceleft
        % 血泪 #46 类（2026-08-07）: \setbox\A=\B 中 \B 是盒号整数不合法——
        % RHS 需 \box 前缀（\box\B 引用盒）；\linotype@cutbox 是 \chardef 整数
        \setbox\linotype@cutbox=\vsplit\linotype@briefbox to\linotype@spaceleft
        \setbox\linotype@briefbox=\box\linotype@cutbox
      \fi
      \def\linotype@leftbrief{\vskip 3mm plus 1fil\unvbox\linotype@briefbox}%
    \fi
    \ifx\empty#7\empty
      \def\linotype@rightbrief{}%
    \else
      \setbox\linotype@briefboxR=\vbox{\hsize\linotype@halfW \linewidth\linotype@halfW \storybody\mainbrief{#7}}%
      \setlength{\linotype@spaceleft}{\dimexpr\linotype@colH-\ht\linotype@mainbox-\dp\linotype@mainbox-3mm\relax}%
      \ifdim\dimexpr\ht\linotype@briefboxR+\dp\linotype@briefboxR>\linotype@spaceleft
        \setbox\linotype@cutbox=\vsplit\linotype@briefboxR to\linotype@spaceleft
        \setbox\linotype@briefboxR=\box\linotype@cutbox
      \fi
      \def\linotype@rightbrief{\vskip 3mm plus 1fil\unvbox\linotype@briefboxR}%
    \fi
    \par\noindent\hbox to\mainW{%
      \vtop to\linotype@colH{\hsize\linotype@halfW \linewidth\linotype@halfW \storybody\unvbox\linotype@splitbox\linotype@leftbrief}%
      \hfil
      \vtop to\linotype@colH{\hsize\linotype@halfW \linewidth\linotype@halfW \storybody\unvbox\linotype@mainbox\linotype@rightbrief}%
    }%
    \par\vspace{1mm}%
  }%
  \global\setbox\linotype@maincol=\vbox{\unvbox\linotype@maincol\unvbox\linotype@tmpbox}%
}

% 侧栏故事: 渲染到临时盒 → 追加进 \linotype@asidecol（mainaside 结束统一截断）
% 2026-08-07: 3 参 {标题}{署名}{正文}——副条带日期/站点/记者（BYLINE-B）
\newcommand{\asidestory}[3]{%
  \setbox\linotype@tmpbox=\vbox{%
    \hsize\asideW \linewidth\asideW
    \subheadline{#1}%
    \par\noindent{\fontsans\fontsize{\dimexpr\linotype@bs*74/100\relax}{\dimexpr\linotype@bs*89/100\relax}\selectfont #2}\par\vspace{0.5mm}%
    \par\noindent{\fontbody\fontsize{\dimexpr\linotype@bs*95/100\relax}{\dimexpr\linotype@bs*123/100\relax}\selectfont #3}%
    \vspace{1.5mm}%
  }%
  \global\setbox\linotype@asidecol=\vbox{\unvbox\linotype@asidecol\unvbox\linotype@tmpbox}%
}


% 侧栏 In Brief 摘要条（main-aside 布局用）: 单列堆叠 3 条，宽度自适应 \asideW
% 2026-08-05: 通栏 \inbrief 在 mainaside 外必超高（mainaside 已占满版心）——移入 aside 栏
\newcommand{\asidebriefs}[4]{%
  \setbox\linotype@tmpbox=\vbox{%
    \hsize\asideW \linewidth\asideW
    \vspace{0.5mm}%
    {\fontsans\fontsize{\dimexpr\linotype@bs*79/100\relax}{\dimexpr\linotype@bs*95/100\relax}\selectfont\addfontfeature{LetterSpace=12}\textbf{#1}}\\[0.5mm]
    \noindent\rule{\asideW}{0.4pt}\\[1mm]
    {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #2}\par\vspace{0.8mm}%
    {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #3}\par\vspace{0.8mm}%
    {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #4}%
  }%
  \global\setbox\linotype@asidecol=\vbox{\unvbox\linotype@asidecol\unvbox\linotype@tmpbox}%
}

% 图片（2026-08-05 新增，借鉴 papertex \image）:
%   \photo{路径}{宽度比例}{图注}    — 宽度 = 比例 × \linewidth，高度由纵横比决定
%   \photo{img.jpg}{1.0}{图注文字}   — 全版宽图
%   \photo{img.jpg}{0.5}{图注文字}   — 半版宽图
% 图片 box 直接进 plate vbox → 高度天然计入溢出检测（图片过大 → Overfull，
% 不静默、不跳过——比 papertex 的 \page@free 估算+跳过更精确）。
% 图注: 小字居中 + 上下细线（仿 papertex \papertex@pictureCaption）。
\newcommand{\photo}[3]{%
  \par\vspace{1mm}%
  \noindent\rule{\linewidth}{0.4pt}%
  \vspace{1mm}\par
  \begin{center}
  \includegraphics[width=\dimexpr#2\linewidth\relax,keepaspectratio]{#1}%
  \end{center}
  \vspace{0.8mm}\par
  {\fontsans\fontsize{\dimexpr\linotype@bs*74/100\relax}{\dimexpr\linotype@bs*89/100\relax}\selectfont
  \addfontfeature{LetterSpace=4}\color{accent}\textbf{\MakeUppercase{#3}}}%
  \vspace{0.8mm}\par
  \noindent\rule{\linewidth}{0.4pt}%
  \par\vspace{1mm}%
}

% 引文框：上 accent 下 ink 细线，19pt 斜体
% 宽度自适应 \linewidth（contentW 上下文=全版引文；halfW 正文盒内=栏内引文）
\newcommand{\pullquote}[1]{%
  \par\vspace{0.5mm}%
  \noindent\rule{\linewidth}{0.4pt}%
  \vspace{0.8mm}\par
  {\fontbody\fontsize{\dimexpr\linotype@bs*200/100\relax}{\dimexpr\linotype@bs*221/100\relax}\selectfont\itshape#1\par}%
  \vspace{0.8mm}\par
  \noindent\rule{\linewidth}{0.4pt}%
  \par\vspace{0.5mm}%
}

% In Brief 摘要条（3 条并排，参数: 标题 + 3 条内容）
% In Brief 摘要条: 栏宽自适应（2026-08-06 修复——血泪 #25）。
% 原设计是"通栏 3 栏并排"（minipage 0.319\contentW ×3），只适合全版宽；
% 移入 storycolumns 列内（\linewidth≈60mm）后 3 个并排 = 178mm 巨盒，
% multicol 无法平衡 → 整盒静默消失（P3 正文丢失，Overfull 348pt）。
% 修复: \linewidth < 0.6\contentW 时按单列堆叠（同 \asidebriefs），
% 通栏上下文保留 3 栏并排。multicol 列内 \linewidth = 列宽（自适应），
% 侧栏渲染 \linewidth=\asideW（自适应）。
\newcommand{\inbrief}[4]{%
  {\fontsans\fontsize{\dimexpr\linotype@bs*79/100\relax}{\dimexpr\linotype@bs*95/100\relax}\selectfont\addfontfeature{LetterSpace=12}\textbf{#1}}\\[0.5mm]
  \noindent\rule{\linewidth}{0.4pt}\\[1.5mm]
  \ifdim\dimexpr\linewidth\relax<0.6\dimexpr\contentW\relax
    % 栏内模式: 单列堆叠（brief 各占一行）
    {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #2}\par\vspace{0.8mm}%
    {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #3}\par\vspace{0.8mm}%
    {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #4}\par
  \else
    % 通栏模式: 3 栏并排
    \begin{minipage}[t]{0.319\linewidth}
    {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #2}
    \end{minipage}\hspace{0.02\linewidth}%
    \begin{minipage}[t]{0.319\linewidth}
    {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #3}
    \end{minipage}\hspace{0.02\linewidth}%
    \begin{minipage}[t]{0.319\linewidth}
    {\fontbody\fontsize{\dimexpr\linotype@bs*89/100\relax}{\dimexpr\linotype@bs*115/100\relax}\selectfont #4}
    \end{minipage}%
  \fi
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
        \global\linotype@topused=0pt%  % 2026-08-07: 版顶占用（\dateline）每版重置
        \setlength{\parindent}{1em}%
        \setlength{\parskip}{0pt}%
        \setlength{\columnsep}{\colGap}%
        \setlength{\multicolsep}{0pt}%
        \setlength{\premulticols}{0pt}%
        \setlength{\postmulticols}{0pt}%
}{%
      \egroup
      % vsplit 兜底: 内容超高时截到版心（血泪 #26: vsplit 对 multicol 整盒
      % 是全切——一旦触发，multicol 内容整体被丢，只剩版头、fill 虚高假
      % 达标）。含 multicol 的版（\if@linotype@multicol）跳过 vsplit：超高
      % 时自然溢出 + 下方 Overfull 报告 → autofit 缩字号（正确信号）。
      % 纯段落版（main-aside 侧栏等）vsplit 正常截断（可分割，安全）。
      % 阈值 contentH+5pt: 2-3pt 微超（multicol balance 溢出）不触发。
      \if@linotype@multicol\else
        \ifdim\dimexpr\ht\linotype@platebox+\dp\linotype@platebox>\dimexpr\contentH+5pt\relax
          \setbox\linotype@platebox=\vsplit\linotype@platebox to\dimexpr\contentH+2pt\relax
        \fi
      \fi
      \global\@linotype@multicolfalse
      % 自然高计量（血泪 #50）: vsplit 后的 \ht+\dp 含幻影 dp（vsplit 对含
      % hbox 两栏的 vbox 切分时，切不动的内容变成幻影 dp——P1 mainaside
      % 749.4pt 微超 6.8pt 触发 vsplit，fill 虚报 1479pt=199%）。
      % 正确: \unvcopy 后量自然高（真实渲染高度）。
      \setbox\@tempboxa=\vbox{\unvcopy\linotype@platebox}%
      % Overfull 判定（2026-08-06 修复）: 报告真实超量（自然高 − contentH）
      \ifdim\dimexpr\ht\@tempboxa+\dp\@tempboxa>\contentH
        \typeout{Overfull plate: content \the\dimexpr\ht\@tempboxa+\dp\@tempboxa\relax\space> contentH \the\contentH, truncated \the\dimexpr\ht\@tempboxa+\dp\@tempboxa-\contentH\relax}%
      \fi
      % fill typeout（autofit 消费）: 自然高（血泪 #50，幻影免疫）。
      \typeout{Plate content: \the\dimexpr\ht\@tempboxa+\dp\@tempboxa\relax / contentH \the\contentH}%
      \vbadness=10000
      \vbox to\contentH{\unvbox\linotype@platebox\vss}%
      \makeatletter
      \global\@colht\textheight%
      \global\@colroom\textheight%
      \makeatother
    \end{minipage}%
}
