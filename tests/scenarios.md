# Linotype 压力测试场景

> 5 个测试场景，覆盖 linotype 通用排版 skill 的核心管线（LaTeX 引擎）、纪律约束、错误恢复与边界情况。
> 每个场景独立可执行，包含完整的前置条件、任务描述、预期行为和通过标准。
> 引擎：xelatex（pdfLaTeX 会被类拒绝）。管线：plates/*.md → build.py → xelatex → pdfcheck。

---

## Scenario 1: Basic Typesetting（基本排版流程）

**类型**：Happy path · 完整管线验证

**描述**：用户提供多版内容素材，要求排版成多栏 PDF。Agent 应执行完整管线——内容解析、tex 生成、编译、QA、交付。

**前置条件**：`~/news/latex/` 有 build.py / linotype.cls / pdfcheck.py；`~/news/plates/` 有 plates/*.md。

**任务**：
1. `python3 build.py plates/ out.tex --docopts "paper=a3,landscape,columns=3,plates=2"`
2. `xelatex -interaction=nonstopmode -halt-on-error out.tex`
3. `python3 pdfcheck.py out.pdf --log out.log --paper a3 --landscape --pages N`

**预期**：
- build.py 生成 .tex 无报错
- 编译 0 错误，输出 PDF
- pdfcheck 无 FAIL（或仅有 LOG OVERFLOW = 内容超高，需裁剪内容）

**通过标准**：PDF 生成、页数正确、字体嵌入 ≥3 种、MediaBox 正确。

---

## Scenario 2: Content Overflow（内容溢出检测）

**类型**：负向 · QA 可信度验证

**描述**：内容超过版心时，必须被编译期检测到（Overfull plate 警告），而不是静默裁剪或推页。

**前置条件**：临时 plates 目录，含超长内容（≥60 段）。

**任务**：用超长内容生成 + 编译，检查日志。

**预期**：
- 日志出现 `Overfull plate: content Xpt > contentH Ypt`
- 编译仍成功（PDF 生成，内容截断到版心，不推页）

**通过标准**：Overfull 警告出现 = 溢出检测工作；无空白首页 = 版面稳定。

---

## Scenario 3: Configuration Matrix（配置矩阵）

**类型**：边界 · 通用性验证

**描述**：不同 paper × columns × plates 组合都能正确编译，证明 skill 不绑定单一配置。

**前置条件**：短内容 plates（1-2 版）。

**任务**：跑以下组合并验证：
- `paper=a4,portrait,columns=2,plates=1` → 页数 = 版数
- `paper=letter,landscape,columns=4,plates=1` → 页数 = 版数
- `paper=a3,landscape,columns=3,plates=2` → 页数 = ceil(版数/2)
- `--theme magazine` → 编译通过（Bitstream Charter 正文）

**预期**：全部编译 0 错误，页数正确，MediaBox 匹配纸张。

**通过标准**：矩阵全绿 = 配置驱动有效。

---

## Scenario 4: Theme & Font Config（主题与字体配置）

**类型**：正向 · 配置化验证

**描述**：主题系统和字体配置化应让用户换字体/配色而不改内容。

**前置条件**：系统已装 Newsreader/Playfair/Inter（~/.fonts/ 注册），fc-list 可见。

**任务**：
1. `--theme magazine` → Charter 正文 + 深蓝强调
2. `--theme brief` → 单色极简
3. `bodyfont=Bitstream Charter` 显式覆盖 → 优先于主题
4. `\SetTagline{...}` → 报头标语可定制

**预期**：各主题编译通过，PDF 嵌入对应字体（pdfcheck FONTS 验证）。

**通过标准**：字体/颜色随配置变化 = 配置化有效。

---

## Scenario 5: Error Recovery（错误恢复）

**类型**：负向 · 引擎纪律

**描述**：错误输入应产生明确诊断，不静默失败。

**前置条件**：任意 plates 目录。

**任务**：
1. 用 **pdflatex** 编译 → 应被类拒绝（`Class linotype Error: pdfLaTeX is not supported`）
2. plates 含裸特殊字符（`100% & $`）→ build.py 转义 → 编译通过
3. 编译日志有 `^!` 错误 → pdfcheck LOG ERROR 应 FAIL

**预期**：引擎检查生效、转义生效、错误可检测。

**通过标准**：三类错误都得到明确诊断 = 引擎纪律良好。

---

## 场景纪律（所有场景适用）

- 只使用可核实内容并标注信源（plates 是唯一事实源）
- 内容超高（Overfull）是**正常检测信号**——修剪内容或调配置，不是 bug
- 欠满（Underfull）已全局过滤（`\vbadness=10000`），报纸版式允许列尾空隙
- 双版 + main-aside 组合的内容超高由 Overfull 检测覆盖（multicol boxed 硬限制，已文档化）
