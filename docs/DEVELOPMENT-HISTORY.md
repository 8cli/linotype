# Linotype Development History

The full debug-and-design journey behind the engine. Every entry records a **root cause, the fix, and the measurable evidence** — read this before touching `linotype.cls` or `build.py`, so you don't repeat a two-hour debugging session.

> Timeline: 2026-08-04 (LaTeX migration) → 2026-08-05 (autofit + four-direction release). All measurements below are real compile-time or pixel-level numbers.

---

## Phase 0 — Why LaTeX (the strategic decision)

The skill originally rendered HTML/CSS in Chromium (Puppeteer). It produced beautiful pages but had a fatal flaw: **overflow was a black box** — content that didn't fit was silently clipped by the browser, and the only way to detect it was pixel-level post-analysis (`audit.js` 14 checks).

The user pushed toward LaTeX: *"人类几十年都在用latex排版，latex必然有其优势！"* The evaluation (2026-08-05) confirmed LaTeX is the right call for print-grade multi-column work:

| Dimension | LaTeX | Typst | CSS Paged Media |
|---|---|---|---|
| Column **balancing** | ★★★★★ `multicol` 30-yr `balance@columns` | ★★ **columns not height-balanced** (official docs) | ★★★ weak |
| Micro-typography (hyphenation, kerning) | ★★★★★ Knuth-Plass | ★★★★ | ★★ |
| Compile-time overflow signal | ★★★★ native warnings | ★★★★ programmable asserts | ★ none |
| Fixed-viewport no-push | ★★★ (against the design philosophy — we fight it) | ★★★★ native boxes | ★★★★ native |
| Ecosystem maturity | ★★★★★ | ★★ | ★★★ |

**The honest tradeoff**: LaTeX wins decisively on print quality + column balancing + compile-time warnings, but it *fights* the "fixed viewport, no page push" requirement (LaTeX's philosophy is flowing pagination). Typst's native boxes would have been easier there, but its missing column balancing is a dealbreaker for newspapers. **The 22 lessons in ARCHITECTURE.md are the price of winning that fight.**

---

## Phase 1 — The plate-viewport battle (the core problem)

### The three-mechanism solution (2026-08-05, decisive)

Goal: keep multi-column content inside a **fixed content area**, never push to a new page, and report overflow at compile time.

Each simpler approach failed in production, with measured evidence:

| Approach | Failure (measured) |
|---|---|
| `vbox` collect + `vsplit` only | multicol balances to the content's *natural* height (real P2 reached 304mm — past the 297mm page!); `vsplit` cannot cut a multicol block (all-or-nothing) |
| `\vtop to \contentH` only | "to" is *at-least*: overfull box keeps natural height (888pt) and pushes the plate to a blank next page |
| `\@colht\contentH` alone | works for top-level multicol; inner (boxed) multicol ignores it (multicol.sty:760 `\if@boxedmulticols\else`) |

**Winner**: `vbox` collection + explicit `\@colht/\@colroom\contentH` (multicol balances to the viewport) + `vsplit` truncation fallback + `\vss` residual absorption. Real content went **304mm overflow → 151–222mm**, entirely inside the 281mm viewport, zero warnings.

### Key measurements along the way

```
real P2 main-aside:  304mm (natural) → 271mm (top-level multicol fix) → 151–222mm (final, single-plate)
column balance probe: left 429.6pt / right 430.0pt (0.4pt off — manual vsplit, Phase 3)
```

---

## Phase 2 — Autofit: from manual decisions to bounded search

User request: replace the "human decides" overflow loop with **automatic configuration search** — bounded (no unlimited column/font tweaks), harmonious (no weird gaps or overly dense pages).

### Decisions (user-confirmed via AskUserQuestion)

- Knobs: `bodyfontsize` 8.5–11pt + `columns` 2–4 + `bottommargin` 12–16mm. **Paper is a hard constraint** — never auto-changed.
- Two-way: overflow → shrink; sparse → grow. **Default on**, `--no-autofit` disables.

### The column-count surprise (opposite to CSS intuition)

Measured (60 paragraphs, 8.5pt): **2-col 1038pt → 3-col 927pt → 4-col 872pt** — more columns = *shorter* content, because multicol balances `natural height / N` and narrow columns hyphenate more efficiently.

**Caveat — the U-shaped curve**: for very long content the curve inverts (measured 120 paragraphs: 3-col 244% → 4-col 271% worse). Autofit records every attempt and reports the **historical best** on failure, never the boundary config.

### Algorithm upgrade: greedy steps → binary search

The first autofit used 0.5pt greedy steps (worst 5 compiles/pass). Upgraded to **binary search over font size** (inspired by tcolorbox's `tcbfitdim`): for a fixed column count, find the largest non-overflowing font at 0.1pt precision (~5 compiles, monotone → no oscillation). Warm start retries the previous font when a knob changes (measured 51-para case: 14 → 9 compiles). The `bottommargin` knob handles overflow < 1 line (the architectural equivalent of `\enlargethispage`, which cannot work on fixed-`\contentH` plates).

### Autofit measured outcomes

| Scenario | Result |
|---|---|
| 50 paragraphs overflow | 8 compiles → 4-col 8.5pt, fill 100%, 0 Overfull |
| 2 paragraphs sparse | boundary accept (no forced fill) |
| 120 paragraphs | 9 compiles → honest fail (3-col 8.5pt = 244%, U-curve optimum) |
| real single-plate | 1 compile, golden path, config unchanged |
| **51 paragraphs (barely over)** | **bottommargin 16→12.7mm converges** (3rd knob saves the day) |

---

## Phase 3 — The top-level refactor (fixing the last structural defect)

### The bug

Dual-plate + `main-aside` overflowed 111% even at minimum font. Three linked root causes:

1. **boxed multicol skips the height cap** — mainstory's multicol runs inside a minipage → `\ifinner` → boxed mode → skips `\@colroom` cap (multicol.sty:760) → typesets to natural height.
2. **plate's `vsplit` cannot cut a boxed multicol** — all-or-nothing.
3. **legacy mainaside structural flaw** — `\asidestory` calls all ran *inside* the main minipage (the aside minipage was empty!), so aside content piled into the main column.

### The fix (collection-based architecture)

```
mainstory: content set at target column width → vbox → vsplit halves → parallel vtop
asidestory: render to tmpbox → append to asidecol
mainaside end: truncate maincol/asidecol to viewport → \hbox{main vtop | aside vtop}
```

Plus two overflow discoveries:
- **full-width content after a full plate always overflows** (measured pullquote +127pt, inbrief +122pt) → pullquote moved into mainstory body (`\linewidth`-adaptive quote); BRIEFS become `\asidebriefs` (aside-column stack).
- **`\vtop to` ht reference-point offset** — parallel measurement exceeds target by ~5.5pt → use natural-height vtop (column-end gaps are legal underfill).

**Measured result**: 111% overflow → **0 Overfull**, fill 89–99%, content bottom 256/280mm < 281mm. Regression went 20 → 25 tests.

---

## Phase 4 — Four-direction release

### A. Image support

`IMAGE:` / `IMAGEWIDTH:` / `IMAGECAPTION:` → `\photo` atom. The image box flows into the plate vbox → height **measured precisely** (oversized 4000px-tall image → `Overfull plate` 2730pt > 742pt, never silently dropped). Strictly better than papertex's estimate-and-skip (`1.5×width + 50pt` vs `\page@free`).

### B. Repo engineering

- **GitHub Actions CI** — the first run FAILED (see variable-font saga below); now green, 25/25 + sample 5/5.
- **3 new themes** — `financial` (deep green), `sport` (vivid orange + Inter headlines), `literary` (deep brown + Charter). The `\ifnum` theme chain needed 5 closing `\fi`s after inserting 3 branches — one missing `\fi` caused "Incomplete \ifnum" (a classic TeX punctuation error, caught by test compile).
- **PDF/A archival** — documented (Ghostscript conversion; XeLaTeX has no native PDF/A).

### C → already covered in Phase 3.

### D. Visual acceptance loop (`--visual`)

Inspired by PaperFit: after autofit converges, render PDF → `pixelcheck.py` column-gap diagnostics → fix suggestions. Measured: real single-plate P1 flagged a 106mm bottom band (fill 49% passes the ≥45% floor, yet visually sparse) — the visual gate catches what the fill metric tolerates.

---

## Phase 5 — The CI variable-font saga (don't repeat this)

**Symptom**: GitHub Actions failed with `xdvipdfmx:fatal: Invalid font: -1 (0)` on every test.

**Root cause chain**:
1. The CI workflow downloaded fonts from `google/fonts` GitHub URLs.
2. **google/fonts is now all-variable-font** — the `static/` directories 404, only `*.ttf` variable fonts exist.
3. **xdvipdfmx (XeLaTeX's PDF driver) rejects variable fonts** — reproduced locally with the exact same `Invalid font: -1` error.

**Fix** (`scripts/ci-install-fonts.sh`): download official variable TTFs → instantiate static weights via `python3 -m fontTools.varLib.instancer` (e.g. `Newsreader.ttf` + `opsz=16 wght=400` → `Newsreader-Regular.ttf`) → `fc-cache`. Verified locally in an isolated `$HOME` (6 fonts registered, static fonts compile clean). CI green.

**Related**: PEP 668 (Debian's "externally managed" Python) blocks bare `pip install` on modern runners — the workflow uses a tolerant chain `--break-system-packages → --user → pip`. Safe in CI (ephemeral runners); local dev should use `venv` instead.

---

## Bug log (chronological, 22 entries)

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | `Missing number` in class | `\makeatother` closed `@` catcode early | never `\makeatother` in a class file |
| 2 | `\ifstrequal` always FALSE | etoolbox doesn't expand macro args | XeTeX `\strcmp` |
| 3 | `\textbf\{` double-escape | markdown bold processed before `{` escaping | escape specials first |
| 4 | `\inbrief` ignored #1 | hardcoded "IN BRIEF" | use #1 |
| 5 | blank first page | multicol took `\@colht` (whole page) | `\@colht\contentH` + restore |
| 6 | `#` in `\newenvironment` comment | `#` is a parameter char | use `%` |
| 7 | blank-band false positives | pixelcheck didn't know layout | build.py emits layout.json |
| 8 | plate overflow past page | multicol natural-height balance | combo vbox+@colht+vsplit |
| 9 | autofit oscillation (10 iters) | shared plates/ polluted fills in tests | isolated af_plates dir |
| 10 | column direction wrong | CSS intuition (more cols = taller) | measured: more cols = shorter |
| 11 | boundary report wrong | U-curve (3→4 cols worse) | report historical best |
| 12 | fake convergence | warm-start overflow marked converged | track real overfull state |
| 13 | main-aside 111% overflow | boxed multicol + legacy mainaside flaw | collection-based vsplit refactor |
| 14 | +127pt after mainaside | pullquote appended full-width | move into mainstory body |
| 15 | +122pt after mainaside | inbrief appended full-width | `\asidebriefs` in aside column |
| 16 | hbox 748 > 742 | `\vtop to` ht offset 5.5pt | natural-height vtop |
| 17 | financial theme failed | missing `\fi` after 3 theme inserts | 5 closing `\fi`s |
| 18 | CI `Invalid font: -1` | variable fonts + xdvipdfmx | instancer static instances |
| 19 | CI pypdf missing | PEP 668 blocked pip | tolerant install chain |
| 20 | image not generated | stale build.py in test dir | sync files |
| 21 | oversized image silent | (would have been) estimate-and-skip | image box flows into plate vbox |
| 22 | SyntaxWarning | `\p` in docstring | raw docstring |

---

## Phase 6 — 2026-08-06: imposer integration fixes (demand-supply hardening)

The demand-supply loop with imposer (real newspaper production) exposed deep TeX semantics beyond Phase 1-4. All measured in real P1-P4 builds.

### Bug log (chronological, 23-33)

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 23 | P3 dual-plate body silently vanished (53.7mm, fill 100%) | `\ht\platebox` reads 0 during vbox construction → `@colht` full-page → header+multicol overflows → vsplit cuts multicol whole-box (all-or-nothing) → body dropped | `\plateheader` collects header to box (`\global\setbox` + `\unvcopy`); storycolumns `@colht = contentH − header − 4pt`; vsplit skips multicol plates |
| 24 | `\begingroup/\endgroup` rolls back `\setbox`/`\newif` | LaTeX env wraps groups; headerbox height read as 0, multicol flag lost | `\global\setbox` + `\global\@linotype@multicoltrue` |
| 25 | `plateheader undefined` in real build | Kpathsea loads stale cls from output dir (TEXINPUTS) | `TEXINPUTS=engine-dir:` in compile_tex |
| 26 | mainaside horizontal overflow 10.6pt/plate | mainW = 0.6666c + g (wrong); should be 2c/3 − g/3 | corrected width formulas |
| 27 | 1.67pt inter-plate gap | `\end{plate}` newline read as space token | `\end{plate}%` |
| 28 | fill 199% phantom | vsplit phantom dp on hbox-parallel vbox | measure natural height via `\unvcopy` |
| 29 | main-aside main column 66mm blank | colH cap `(contentH−60)/2` — single-column visual height ≠ half; header actually 213pt not 60pt | colH = min(natural/2, contentH − header); DECK truncated 250→120 chars |
| 30 | P1 bottom margin 10mm overflow | cap 355 too long (287mm > 281mm viewport) | cap 340 → 723pt ≈ 97.4% |
| 31 | `\topskip` 11pt pushed every plate down 3.9mm | plate is first box on page; topskip glue inserted | `\setlength{\topskip}{0pt}` |
| 32 | aside column silently truncated 49.8pt (fill 97.4% fake) | `Overfull aside column` signal not consumed by parse_feedback | parse (main\|aside) column truncation >5% as overfull |
| 33 | demand.json stale after convergence | write_demand returns None without overwriting | remove stale file when no demand |

### What changed (measured)

```
P1 fill: 84% → 97.8%   P2: 89% → 97.8%   P3: 59% → 98.6%   P4: 56% → 95.9%
top margin: 23.8 → 19.9mm (design 20)   bottom: 12.2 → 20.6-21.2mm (design 16)
aside truncation: 49.8pt → 0
P1 main column bottom: 193.7 → 254.5mm (blank eliminated)
```

---

## What survives

- **22 LaTeX lessons** → ARCHITECTURE.md
- **25 regression tests** → tests/run_tests.py (positive/negative matrix incl. autofit, main-aside structural, image)
- **8 pressure scenarios** → tests/scenarios.md
- **Every measurement above** is reproducible: run `build.py` on the examples or the test suite.

The design debt we chose to accept: no text-wrap images, autofit doesn't scale image width, and the column knob is a U-curve for extreme content (honest failure reporting instead of silent damage).
