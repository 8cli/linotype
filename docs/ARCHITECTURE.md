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

## Content pipeline

`build.py` parses `plates/*.md` field labels (`KICKER:`/`HEADLINE:`/`BODY:`/…), escapes LaTeX special characters, renders each plate with the layout atoms implied by its fields, and emits:

- one `.tex` (with `\linotypesetup{docopts}` generated from `--docopts`);
- a `layout.json` consumed by `pixelcheck.py --layout auto` (per-plate `single`/`multi` layout semantics).

Dual-plate mode pairs files in order (P1|P2, P3|P4). Newspaper fold semantics (P1|P4 on the same sheet) are achieved by naming files in fold order.

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
