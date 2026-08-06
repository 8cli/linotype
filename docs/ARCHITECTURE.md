# Linotype Architecture

This document records the engine's key design decisions and the LaTeX lessons behind them. It is the reference for anyone extending `linotype.cls` — read it before touching the plate container or multicol code.

## Core challenge: fixed viewport, no page push

Newspaper plates have a **fixed content area**. When content exceeds it, a real newspaper does not push the story to a new page — the editor trims or re-sets it. Linotype reproduces this discipline at compile time:

- content is typeset into a **fixed-height `plate`**;
- if it overflows, the engine reports `Overfull plate: content Xpt > contentH Ypt` and **truncates at the boundary** (`vsplit`), keeping the page stable.

No surveyed project (LiX, modernnewspaper, papertex, CTAN `newspaper`) does this. All of them let overflow spill or push to a new page.

## The three-mechanism solution

The plate environment combines three mechanisms:

```
\setbox\linotype@platebox=\vbox\bgroup     % 1. vbox collection (fixed width)
  ... \hsize\contentW ...                  %    multicol runs inside
\egroup
\ifdim \ht\linotype@platebox+\dp\linotype@platebox > \contentH
  \typeout{Overfull plate: ...}            % 2. height budget via \@colht\contentH
  \setbox\linotype@platebox=\vsplit ... to\contentH   % 3. truncation fallback
\fi
\vbox to\contentH{\unvbox\linotype@platebox\vss}      %    + \vss absorbs residual
```

Why all three? Each simpler approach failed in production:

| Approach | Failure |
|---|---|
| `vbox` collect + `vsplit` only | multicol balances to the content's *natural* height (real page 2 reached 304mm); `vsplit` cannot split a multicol box — all or nothing |
| `\vtop to \contentH` only | "to" is *at-least* semantics: an overfull box takes its natural height (888pt) and pushes the plate to a blank next page |
| `\@colht\contentH` alone | works for top-level multicol, but inner (boxed) multicol ignores it (see below) |

The winning combination: `vbox` collection + explicit `\@colht/\@colroom\contentH` so multicol **balances to the viewport**, + `vsplit` as a truncation backstop + `\vss` to absorb residual height. Real content went from 304mm overflow to 151–222mm — entirely inside the 281mm viewport, zero warnings.

## LaTeX lessons (blood, sweat & tears)

1. **babel english hyphenation is mandatory** — without it, line counts grow ~25% and content overflows.
2. **Line spacing is the 2nd argument of `\fontsize{size}{baselineskip}`** — never `\baselinestretch` (1.3 quietly becomes 1.56).
3. **multicol takes its column height from `\@colht` (the whole page), not the viewport** — set `\@colht\contentH` on entry and restore `\textheight` on exit. `\@colroom` is the boxed-balance basis; set both.
4. **`\vtop to` is *at-least* semantics** — underfull boxes stretch, overfull boxes keep natural height. Use `vbox` collect + `vsplit` fallback.
5. **minipage height parameters absorb overflow silently (`\vss`)** — the plate box must `vsplit` explicitly.
6. **multicol boxed mode skips the `\@colht` cap** (`\if@boxedmulticols` at multicol.sty:753) — dual-plate/nested content can overrun; caught by the Overfull warning. This is the documented dual-plate + `main-aside` limitation.
7. **etoolbox `\ifstrequal` does not expand macro arguments** — `\ifstrequal{\@papersize}{a3}` is always FALSE. Use XeTeX's `\strcmp`.
8. **`\@columns` collides with internal LaTeX macros** — renamed to `\linotype@columns`, wrapped as document-level `\linotypecols`.
9. **Quotes: `` `` '' ``** — an unclosed quote silently swallows content.
10. **A class file has `@` as a letter for its whole life** (kernel `\@input`) — never add `\makeatother`.
11. **`\textbf\{` double-escaping** — escape special characters *first*, then process Markdown bold. `build.py` does this; hand-written TeX must not repeat it.
12. **Font loading defers to `\AtBeginDocument`** — the family names are only final after `\linotypesetup` runs in the preamble.
13. **No `#` inside `\newenvironment` definitions** (even in comments) — it is a parameter character; "Illegal parameter number" awaits.
14. **`\dimexpr` must be terminated with `\relax`** — a space is *skipped* (separator), so a following `/` is parsed as division ("Missing number, treated as zero"). `\the\dimexpr A+B\relax / text` works; `\space` does not.
15. **multicol box height = natural height(N) / N — more columns = shorter content** (opposite to CSS intuition). CSS flows text into wider columns → fewer lines; LaTeX *balances* N columns so height ≈ natural/N (measured: 60 paragraphs at 8.5pt → 2-col 1038, 3-col 927, 4-col 872pt). But for very long content the curve is U-shaped (measured 120 paragraphs: 3-col 244% → 4-col 271% worse) — autofit reports the historical best, never the boundary config.
16. **boxed multicol is a hard limit; manual `vsplit` columns are the fix** — boxed mode skips `\@colroom` and `vsplit` cannot cut a multicol block (all or nothing). Solution: typeset content at the target column width → `vbox` → `vsplit` dynamically half → parallel `\vtop`. Measured balance: 429.6/430.0pt.
17. **`\vtop to` has an ht reference-point offset** — side-by-side measurement exceeds the target by ~5.5pt (first-line baseline). Parallel containers use natural-height `\vtop`; column-end gaps are legal underfill in newspaper layout.
18. **full-width content after a full plate always overflows** — in main-aside, pullquote/inbrief appended after the plate overran by a measured +127/+122pt. Fix: move them *inside* the columns (column-width `\linewidth` quote; `\asidebriefs` aside stack).
19. **binary search for the largest non-overflowing font** — inspired by tcolorbox's `tcbfitdim` lower/upper bounds. Font height is monotone → no oscillation; 0.1pt precision in ~5 compiles. Warm start (retry previous font when a knob changes) cuts ~5 compiles per knob change; direction may flip after a knob change — always retest.
20. **autofit's bottom-margin knob replaces `\enlargethispage`** — the LaTeX-native command cannot enlarge a fixed-`\contentH` plate box; instead autofit shrinks `bottommargin` (12–16mm) when overflow < 1 line, the architectural equivalent.
21. **image height is measured, not estimated** — papertex estimates `1.5×width + 50pt` against `\page@free` and silently skips tight images. Linotype flows the image box into the plate vbox → precise height → oversized → `Overfull plate`, never silently dropped.
22. **xdvipdfmx rejects variable fonts** (`Invalid font: -1`) — google/fonts is now all-variable; CI must instantiate static weights via fonttools `varLib.instancer`. Local static TTFs are unaffected.

## Content pipeline

`build.py` parses `plates/*.md` field labels (`KICKER:`/`HEADLINE:`/`BODY:`/…), escapes LaTeX special characters, renders each plate with the layout atoms implied by its fields, and emits:

- one `.tex` (with `\linotypesetup{docopts}` generated from `--docopts`);
- a `layout.json` consumed by `pixelcheck.py --layout auto` (per-plate `single`/`multi` layout semantics).

Dual-plate mode pairs files in order (P1|P2, P3|P4). Newspaper fold semantics (P1|P4 on the same sheet) are achieved by naming files in fold order.

## Autofit — automatic layout adjustment

`build.py` runs a **compile → feedback → adjust** loop by default (`--no-autofit` disables it). Feedback comes from two `\typeout` lines per plate:

```
Plate content: 739.56503pt/ contentH 742.61694pt     % always emitted
Overfull plate: content 782.05089pt> contentH 742.61694pt   % only on overflow
```

### Bounds (user-confirmed)

| Knob | Range | Step | Notes |
|---|---|---|---|
| `bodyfontsize` | 8.5–11pt | binary (0.1pt precision) | primary knob (~5% per 0.5pt) |
| `columns` | 2–4 | 1 | secondary knob (~6–11%) |
| `bottommargin` | 12–16mm | ~0.1mm | tertiary knob — micro-adjusts the viewport when overflow < 1 line |
| paper / landscape / plates | — | — | **hard constraints**, never auto-changed |

### The column-count relationship (opposite to CSS intuition)

CSS flows text into wider columns → fewer lines → shorter content. LaTeX `multicol` **balances N columns**: `\balance@columns` starts from `natural height / N` (multicol.sty) and, in boxed mode, skips the `\@colroom` cap. Since natural height grows sub-linearly with N (narrower columns hyphenate more efficiently), the balanced box height is:

```
box height ≈ natural height(N) / N   →   more columns = shorter content
```

Measured (60 paragraphs, 8.5pt): 2-col 1038pt → 3-col 927pt → 4-col 872pt.

**Caveat — the U-shaped curve**: for very long content, natural height grows super-linearly past the balance point (measured 120 paragraphs: 3-col 244% → 4-col 271%), so adding columns can *worsen* overflow. Autofit records every attempt and reports the historical best on failure, never the boundary configuration.

### Binary search (inspired by tcolorbox `tcbfitdim`)

```
golden path: compile user config → converged? → done (no search)
loop:
  binary-search font in [8.5, 11] for the LARGEST non-overflowing size
    (0.1pt precision, ~5 compiles; font height is monotone → no oscillation)
  converged? (0 Overfull and min fill ≥ 0.45) → ✅
  overflow at font floor:  add column → shrink bottom margin (< 1 line) → ❌ report best
  sparse at font ceiling:  drop column → ✅ accept (content is naturally short)
  warm start: when a knob changes, retry the previous pass's font first
```

Monotone in each direction, so no oscillation; worst case ~9 compiles (~30s), hard-capped at 16. The bottom-margin knob is the architectural equivalent of `\enlargethispage` (which cannot work here — plate boxes have fixed `\contentH`).

### The main-aside fix: manual vsplit columns (top-level refactor)

Dual-plate + `main-aside` was the engine's one structural defect: the mainstory multicol runs inside a minipage (boxed mode), which skips the `\@colroom` cap (multicol.sty:760) — content typesets to its natural height and the plate's `vsplit` cannot cut a boxed multicol block. Measured: real P2–P4 overflowed 111% even at minimum font.

The 2026-08-05 top-level refactor replaces the minipage-inner multicol with **manual vsplit columns**:

```
content set at target column width (halfW) → vbox
colH = min(natural/2, (contentH − header)/2)      % balanced, bounded
left  = vsplit(mainbox, colH); right = vsplit(mainbox, colH)
\hbox to mainW{ top{left} \hfil top{right} }   % box-parallel is legal (only multicol is boxed-restricted)
```

Verified: left/right balance at 429.6/430.0pt (0.4pt off). Overrunning content truncates at the budget with an `Overfull mainstory` warning. Two more fixes fell out of the same refactor:
- **full-width content after a full plate always overflows** (measured pullquote +127pt, inbrief +122pt) → pullquote moved into the mainstory body (column-width `\linewidth` quote); BRIEFS become `\asidebriefs`, a single-column stack in the aside.
- **`\vtop to` ht reference-point offset** — side-by-side measurement exceeds the target by ~5.5pt (first-line baseline); parallel containers use natural-height `\vtop` (column-end gaps are legal underfill in newspaper layout).

Result: real dual-plate main-aside content goes 111% overflow → **0 Overfull**, fill 89–99%, content bottom 256/280mm < 281mm viewport. Regression 25/25.

## Image support (`\photo`)

`IMAGE:` / `IMAGEWIDTH:` / `IMAGECAPTION:` fields render as `\photo{path}{width-factor}{caption}` — `\includegraphics[width=factor×\linewidth,keepaspectratio]` in a framed, captioned box. The image box flows directly into the plate vbox, so its height is **measured precisely** by the existing overflow machinery (oversized image → `Overfull plate`, never silently skipped). This is strictly better than papertex's approach (`1.5×width + 50pt` estimate vs `\page@free`, skip-if-tight): we measure, not estimate.

## Visual acceptance loop (`--visual`)

Borrowed from PaperFit: after autofit converges, `--visual` renders the PDF to PNGs (110dpi), runs `pixelcheck.py --layout-file layout.json` per page, and reports column-gap diagnostics with fix suggestions:
- blank band at the page bottom → content is sparse (autofit already grew font / dropped columns; add content or accept)
- blank band mid-column → balance issue (review that plate's content distribution)

The report is a **gate**, not an auto-fixer: it surfaces visual problems the compile-time fill metric tolerates (e.g. fill 49% passes the ≥45% floor, yet a 106mm bottom band is visually sparse).

## QA layers

| Layer | What | Failure mode |
|---|---|---|
| Compile-time | `Overfull plate` warnings from the class | content exceeds viewport — trim or re-configure |
| Compile-time | `Underfull` — globally filtered via `\vbadness=10000` | not a defect (sparse pages are legal) |
| Post-process | `pdfcheck.py` — log scan, MediaBox, embedded fonts ≥3, page count | any structural mismatch |
| Pixel-level | `pixelcheck.py` — column-gap analysis of rendered PNG | blank bands in production pages |
| Regression | `tests/run_tests.py` — positive/negative matrix (10 tests) | any pipeline regression |

## PDF/A archival output

XeLaTeX does not emit native PDF/A. For archival-grade output, convert with Ghostscript after the build:

```bash
gs -dPDFA=2 -dBATCH -dNOPAUSE -sProcessColorModel=DeviceRGB    -sDEVICE=pdfwrite -sOutputFile=out-pdfa.pdf out.pdf
```

A future `pdfcheck.py --pdfa` check can verify the `OutputIntent` entry.

## Additional lessons (2026-08-06, imposer integration, 23-30)

23. **`\ht` of a box being constructed reads the previous value (or 0)** — `@colht` derived from `\ht\platebox` during vbox construction is garbage. Collect headers into a separate measured box.
24. **LaTeX environment `\begin/\end` wraps `\begingroup/\endgroup`** — `\setbox` and `\newif` assignments inside are rolled back at end. Use `\global`.
25. **Kpathsea loads the .cls next to the .tex, not your working dir** — stale class files in output dirs silently shadow the engine's. Set `TEXINPUTS=engine-dir:`.
26. **main-aside width**: main = 2c/3 − g/3, aside = c/3 − 2g/3 (sum = contentW exactly). The naive `0.6666c + g` overflows 10.6pt.
27. **`\end{plate}` newline is a space token** — `%` after it, or plates gain 2.51pt inter-gap glue.
28. **vsplit phantom depth on hbox-parallel vboxes** — `\ht+\dp` after vsplit of a two-column hbox over-reports (fill 199%!). Measure natural height via `\unvcopy`.
29. **Two side-by-side columns have the visual height of ONE column** — the main-aside main column budget is `contentH − header`, not half. The header is real (213pt with 250-char deck), not a 60pt assumption.
30. **`\topskip` (11pt from article class) glues before the first box on a page** — a plate as first element gains 3.9mm top offset, shrinking the bottom margin. `\setlength{\topskip}{0pt}`.
31. **vsplit truncation of side columns is silent** — `Overfull aside column` must feed autofit (truncation >5% = overfull), or fill reports a fake healthy number.

## Known limitations (accepted)

- Pure text: no images/figures yet.
- Dual-plate + `main-aside`: the aside's multicol runs in a minipage (boxed mode) and is not capped by `\@colht`; overflow is caught by the Overfull warning. Single-plate mode is fully bounded.
- Font sizes are fixed per atom; themes change fonts and colors only.
