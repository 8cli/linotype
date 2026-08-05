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
| `bodyfontsize` | 8.5–11pt | 0.5pt | primary knob (~5% per step) |
| `columns` | 2–4 | 1 | secondary knob (~6–11%) |
| paper / landscape / plates | — | — | **hard constraints**, never auto-changed |

### The column-count relationship (opposite to CSS intuition)

CSS flows text into wider columns → fewer lines → shorter content. LaTeX `multicol` **balances N columns**: `\balance@columns` starts from `natural height / N` (multicol.sty) and, in boxed mode, skips the `\@colroom` cap. Since natural height grows sub-linearly with N (narrower columns hyphenate more efficiently), the balanced box height is:

```
box height ≈ natural height(N) / N   →   more columns = shorter content
```

Measured (60 paragraphs, 8.5pt): 2-col 1038pt → 3-col 927pt → 4-col 872pt.

**Caveat — the U-shaped curve**: for very long content, natural height grows super-linearly past the balance point (measured 120 paragraphs: 3-col 244% → 4-col 271%), so adding columns can *worsen* overflow. Autofit records every attempt and reports the historical best on failure, never the boundary configuration.

### Greedy search (monotone, no oscillation)

```
loop:
  compile → parse (overfull, fills)
  converged?  → 0 Overfull and min(fills) ≥ 0.45  → ✅
  overflow:   shrink font (8.5 floor) → add column (4 cap) → ❌ report best
  sparse:     grow font (11 cap) → drop column (2 floor) → ✅ accept (content is naturally short)
```

Monotone in each direction (font only shrinks while overflowing, only grows while sparse), so no oscillation; worst case 7 compiles (~35s), hard-capped at 10.

### Known interplay with dual-plate + main-aside

The `mainstory` multicol is hard-coded to 2 columns (newspaper classic layout), so the column knob has **no effect** on that layout; only the font knob helps. Measured: real P2–P4 overflow 132% → 111% at minimum font — insufficient to fully converge. Autofit reports this honestly as "cannot fit within bounds" (exit 1, PDF preserved).

## QA layers

| Layer | What | Failure mode |
|---|---|---|
| Compile-time | `Overfull plate` warnings from the class | content exceeds viewport — trim or re-configure |
| Compile-time | `Underfull` — globally filtered via `\vbadness=10000` | not a defect (sparse pages are legal) |
| Post-process | `pdfcheck.py` — log scan, MediaBox, embedded fonts ≥3, page count | any structural mismatch |
| Pixel-level | `pixelcheck.py` — column-gap analysis of rendered PNG | blank bands in production pages |
| Regression | `tests/run_tests.py` — positive/negative matrix (10 tests) | any pipeline regression |

## Known limitations (accepted)

- Pure text: no images/figures yet.
- Dual-plate + `main-aside`: the aside's multicol runs in a minipage (boxed mode) and is not capped by `\@colht`; overflow is caught by the Overfull warning. Single-plate mode is fully bounded.
- Font sizes are fixed per atom; themes change fonts and colors only.
