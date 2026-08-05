<div align="center">

# 🗞️ Linotype

**A configuration-driven LaTeX typesetting engine for the AI age**

Turn Markdown content into print-quality multi-column PDFs — with compile-time overflow detection.

`plates/*.md` → `build.py` → `xelatex` → **PDF**

[Quick Start](#quick-start) · [Content Format](#content-format) · [Configuration](#configuration) · [QA Pipeline](#qa-pipeline) · [Architecture](docs/ARCHITECTURE.md) · [中文 README](README.zh-CN.md)

</div>

---

## What is Linotype?

Linotype is a **generic, configuration-driven typesetting engine** built on LaTeX. It is not bound to any newspaper or publication: point it at any set of Markdown plates, pick a paper size, column count, font family and color theme, and it produces a print-ready PDF.

Its core differentiator is **fixed-viewport layout**: content is typeset into a fixed content area (the "plate") with a fixed column grid, and if content exceeds the plate, the page **does not push to a new page** — the overflow is reported as a **compile-time warning** (`Overfull plate: content Xpt > contentH Ypt`) and the layout stays stable.

> Existing LaTeX newspaper projects (LiX, modernnewspaper, papertex, CTAN `newspaper`) all let overflowing content push to a new page or silently spill past the viewport. Linotype is — as far as we have researched — the only one that holds the page and tells you at compile time exactly how much room was exceeded.

## Features

- **Config-driven** — paper (A3/A4/Letter) × orientation × columns (2–4) × plates per page (1/2) × fonts × colors × theme, all in one `\linotypesetup` key-value call
- **Theme system** — `newspaper` (serif + deep red), `magazine` (Charter + deep blue), `brief` (monochrome); explicit font/color settings always win
- **Markdown field format** — plates are plain text with `KICKER:`, `HEADLINE:`, `BODY:` etc. field labels; no HTML, no CSS, no DOM
- **Compile-time overflow detection** — `Overfull plate` warnings are emitted by the engine itself; underfull (sparse) pages are filtered as non-defects
- **No blank pages** — overflow is truncated with `vsplit` instead of pushing the plate to the next page
- **Fonts via fontconfig** — any installed font family works (`Newsreader`, `Playfair Display`, `Inter` ship-ready; swap with `bodyfont=...`)
- **Engine discipline** — XeLaTeX required, pdfLaTeX rejected at load time (fontspec dependency)
- **QA pipeline** — compile warnings + `pdfcheck.py` (PDF structure/fonts/pages) + optional `pixelcheck.py` (pixel-level column-gap analysis)

## Quick Start

```bash
# 1. Author content — one Markdown file per plate (see examples/plates/)
ls examples/plates/
#   p1.md  p2.md

# 2. Generate LaTeX from plates
python3 build.py examples/plates/ examples/sample.tex \
    --docopts "paper=a3,landscape,columns=3,plates=1"

# 3. Compile (XeLaTeX only — pdfLaTeX is rejected by the class)
xelatex -interaction=nonstopmode -halt-on-error -output-directory=examples examples/sample.tex

# 4. Post-process QA
python3 pdfcheck.py examples/sample.pdf --log examples/sample.log \
    --paper a3 --landscape --pages 2
```

The sample output (2 pages, A3 landscape, 3 columns, 0 warnings):

| Plate 1 — equal columns | Plate 2 — main + aside |
|:---:|:---:|
| ![sample p1](assets/preview-p1.png) | ![sample p2](assets/preview-p2.png) |

## How it works

```
plates/*.md (field-formatted content)     ← single source of truth
      │  build.py (content pipeline)
      ▼
      .tex  (linotype.cls document class)
      │  xelatex
      ▼
      PDF  +  .log
      │
      ├─ LaTeX native warnings: Overfull plate / Underfull (filtered)
      ├─ pdfcheck.py: MediaBox / embedded fonts / page count / log scan
      └─ pixelcheck.py (optional): column-gap analysis on rendered PNG
```

`linotype.cls` provides the layout atoms: `masthead`, `sectionstrip`, `kicker`, `headline`, `subheadline`, `expandedtitle` (cross-column title), `deck`, `byline`, `storycolumns[N]`, `pullquote`, `inbrief`, `mainaside` (main 2-col + aside 1-col), and the `plate` container that enforces the fixed content area.

## Content Format

Each plate is a `plates/pN.md` file with **field labels** (not Markdown headings):

```markdown
LAYOUT: main-aside        # optional: '' (equal columns, default) | main-aside
COLUMNS: 3                # optional: per-plate column count
EXPANDEDTITLE: Title      # optional: full-width title breaking all columns
KICKER: Section label
HEADLINE: Main headline
SUBHEADLINE: Subtitle     # optional
DECK: Standfirst
BYLINE: Byline
BODY:                     # body paragraphs, separated by blank lines
First paragraph...
Second paragraph...
STORY-B: Sidebar title    # optional, main-aside layout
Sidebar body...
PULLQUOTE: Quote          # optional
BRIEFS:                   # optional, up to 3 items
**Item 1:** text...
```

Special characters (`& % $ # _ { } ~ ^`) and Markdown bold/italic are escaped/translated by `build.py` automatically. Full examples in [`examples/plates/`](examples/plates/).

## Configuration

### `\linotypesetup` keys (via `--docopts`)

| Key | Values | Default | Description |
|---|---|---|---|
| `paper` | `a3` / `a4` / `letter` | `a3` | Paper size |
| `landscape` / `portrait` | — | portrait | Orientation |
| `columns` | 2–4 | 3 | Global column count |
| `plates` | 1 / 2 | 2 | Plates per page (2 = side-by-side) |
| `theme` | `newspaper` / `magazine` / `brief` | `newspaper` | Preset fonts + colors |
| `bodyfont` / `displayfont` / `sansfont` | any installed family | Newsreader / Playfair Display / Inter | Fonts (fontconfig lookup) |
| `ink` / `accent` / `papercolor` | hex | `1A1A1A` / `8C1D18` / `FFFFFF` | Colors |
| `fontpath` | directory | `~/.fonts` | Font search path (fallback) |

Themes fill in *unset* values only — an explicit `bodyfont` or `accent` always wins.

### `\Set*` metadata commands

```latex
\SetTagline{INDEPENDENT DAILY NEWS}   % masthead strapline (comma-safe)
```

## QA Pipeline

Linotype treats typesetting as a **build with warnings**:

| Stage | Tool | Detects | Fails when |
|---|---|---|---|
| Compile | `xelatex` + class | `Overfull plate: content Xpt > contentH Ypt` | Content exceeds fixed viewport (must trim or resize) |
| Compile | class | `Underfull \vbox` | **Filtered** (`\vbadness=10000`) — sparse pages are not defects in newspaper layout |
| Post | `pdfcheck.py` | Log errors, MediaBox, embedded fonts (≥3), page count | Any mismatch |
| Post | `pixelcheck.py` | Column gaps / bottom overflow on rendered PNG | Blank bands in production pages |

```bash
# Regression suite (positive + negative matrix, runs in a temp dir)
python3 tests/run_tests.py /path/to/engine
#   ✅ 10 PASS — covers: build, pages, fonts, overflow detection, escaping,
#   dual-plate no-blank-page, themes
```

## Design Decisions

The engine's hardest problem was **keeping multi-column content inside a fixed content area**. The solution combines three mechanisms (details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)):

1. **`vbox` collection** — plate content is gathered in a box of fixed width
2. **`\@colht` / `\@colroom` height budget** — multicol is told to balance to the content height, not the full page
3. **`vsplit` truncation fallback** — if content still exceeds, it is cut at the boundary and reported via `Overfull plate`

The result: real newspaper content typesets at 151–222mm inside a 281mm viewport with **zero overflow warnings**, instead of spilling past the page edge.

## Comparison with existing projects

| Project | Config-driven | Per-plate columns | Fixed viewport | Overflow → no page push |
|---|---|---|---|---|
| [LiX](https://github.com/LiX2018/LiX) | ✓ | ✗ | ✗ | ✗ |
| modernnewspaper | ✓ | ✗ | ✗ | ✗ |
| papertex | ✓ | ✓ | ✗ | ✗ |
| CTAN `newspaper` | ✗ | ✗ | ✗ | ✗ |
| **Linotype** | ✓ | ✓ | ✓ | **✓** |

## Known Limitations

- **Pure text** — no image/figure support yet (planned)
- **Dual-plate + `main-aside`** — the aside's multicol runs inside a minipage and is not height-capped by `\@colht` (a known multicol boxed-mode behavior); overflow is caught by the `Overfull plate` warning. Single-plate mode has no such issue.
- **Font sizes are fixed per atom** — themes change fonts and colors, not size scales (planned: size-scale theming)

## Requirements

- **XeLaTeX** (TeX Live) — pdfLaTeX is rejected by the class
- Python 3.10+ with `pypdf` (for `pdfcheck.py` / tests)
- Fonts: `Newsreader`, `Playfair Display`, `Inter` (or any fontconfig-registered family)

## Project Layout

```
├── linotype.cls        # Generic LaTeX document class (the engine)
├── build.py            # Content pipeline: plates → .tex + layout.json
├── pdfcheck.py         # PDF post-processing QA
├── SKILL.md            # Claude Code skill manual (agent-facing)
├── docs/
│   └── ARCHITECTURE.md # Key design decisions & LaTeX lessons
├── examples/
│   ├── plates/         # Sample content (all field formats)
│   └── sample.pdf      # Pre-built sample output
├── scripts/
│   └── pixelcheck.py   # Pixel-level column-gap analysis
└── tests/
    ├── run_tests.py    # Positive/negative regression matrix
    └── scenarios.md    # Pressure-test scenarios
```

## License

[MIT](LICENSE) © 2026 Yu (8cli)
