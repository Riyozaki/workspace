# Showcase

Four documents that push the toolchain as far as it goes. They are a single
coherent case — an investment programme for an energy-storage network — told
in the four formats, with **the same numbers in all of them**.

```bash
.venv/bin/python showcase/build_all.py            # build + validate
.venv/bin/python showcase/build_all.py --preview  # also render QA PNGs
.venv/bin/python showcase/build_all.py --clean    # rebuild from scratch
```

The four documents live in `showcase/out/` and are **committed**, so they can be
opened and reviewed without running anything. Rebuilding overwrites them; the
QA preview folders (`showcase/out/qa-*/`) are gitignored. Exit code is non-zero
if any generator fails or any validation reports FAIL, so it is CI-safe.

| File | Generator | What it demonstrates |
|---|---|---|
| `Модернизация_сети_накопителей.docx` | `build_whitepaper.js` | The hardest Word document here: full-bleed cover, TOC, footnotes, comments, tracked changes, OMML equations, landscape section, merged cells |
| `Финансовая_модель_накопители.xlsx` | `build_workbook.py` | Six sheets of live formulas, scenario switch, conditional formatting, native charts |
| `Совет_директоров_накопители.pptx` | `build_deck.js` | Seven 16:9 slides, master layout, native editable charts, autoshape diagrams, speaker notes |
| `Резюме_программы_одна_страница.pdf` | `build_onepager.py` | Exact mm-grid A4 leave-behind drawn directly with reportlab |

`make_charts.py` produces the two matplotlib images (`waterfall.png`,
`tornado.png`) that OOXML has no native chart type for. Everything else that
*can* be a native chart *is* one.

## Feature coverage

**Word** (`docx` npm + `tools/js/docx_fix.js`)

- Cover image anchored to the page, behind text, no wrapping — a real
  full-bleed background rather than an inline picture
- Four sections: cover (no numbering) → front matter (roman) → body (arabic,
  restarted) → landscape appendix, each with its own header and footer
- Field-based `TableOfContents`, `PAGE`/`NUMPAGES` fields ("с. 3 из 9")
- Real footnotes (`word/footnotes.xml`), real threaded comments
  (`word/comments.xml`, two named authors), real tracked changes
  (`w:ins`/`w:del` with author and timestamp)
- OMML equations: NPV summation with a nested fraction and superscript, WACC,
  a radical over a summation
- Table with vertically merged group cells, a repeating header row
  (`tblHeader`), zebra shading and a spanning total row
- Multilevel legal numbering (1. / 1.1. / a\)), bullets, checkboxes
- Bookmark + internal cross-reference, external hyperlink
- Captions via a custom `Caption` style; headings via `styles.default.*`

**Excel** (openpyxl + `tools/recalc.py`)

- `Допущения` drives everything through named ranges; a dropdown switches
  scenario and `CHOOSE` propagates it
- `Прогноз P&L`, `DCF`, `Чувствительность`, `Реестр объектов`, `Графики`
- Every downstream number is a formula. `recalc.py` computes and caches them,
  and the totals were re-derived independently before shipping
- Conditional formatting: 3-colour scale, data bars, icon set, rule-based
- Freeze panes, autofilter with `SUBTOTAL`, print titles, fit-to-width
- Cell comments, custom number formats, blue-input/black-formula convention
- Two native charts (combo with secondary axis; column)

**PowerPoint** (pptxgenjs)

- A `CONTENT` master carrying the background, rule, footer and slide number
- Title slide: photo + scrim, because white text on a raw photograph is
  unreadable
- Native, editable charts: bar+line combo with a secondary percentage axis,
  and a doughnut — not images of charts
- Autoshape diagrams: KPI cards, 2×2 risk matrix, alternating timeline
- Speaker notes on all seven slides

**PDF** (reportlab)

- Absolute mm grid on A4 — nothing reflows
- Embedded Inter/PT Serif with Cyrillic; vector donut, bars, badges
- Document outline, metadata, and a real clickable link annotation

## Consistency

The four documents are cross-checked, not just individually valid:

- 2026 revenue is **5 310 млн ₽** in the model, and the segment tables in the
  whitepaper, the deck doughnut and the one-pager donut all sum to it
- IRR **13,6 %** vs WACC **12,1 %**, NPV **83 млн ₽**, payback **4,1 года**
  and capex **4,35 млрд ₽** are identical across all four
- Capacity roll-out in the one-pager sums to the 252 МВт·ч quoted in its text

This mattered: the first draft had the deck and whitepaper claiming 5 444
against a model that computed 5 310. Building the model first and deriving the
prose from it is the only reliable order.

## Bugs this exercise surfaced

Three real defects, all fixed in the toolchain and covered by tests:

1. **`install_fonts.py` merged only `latin` + `cyrillic`.** The ruble sign ₽
   (U+20BD) lives in `latin-ext`, so *every* Russian financial document would
   have rendered its currency as a blank box. Now merges four subsets and
   hard-fails if any of ₽ — « » № ± … is missing.
2. **`recalc.py` cached `#NAME?` over valid formulas.** `SUBTOTAL` is fine in
   Excel but unimplemented by the `formulas` engine; writing the engine's error
   into the file turned a working workbook into a broken one. Engine gaps are
   now left uncached and reported as `left_to_excel`.
3. **`render.py` drew every ellipse as a rectangle.** Risk bubbles and timeline
   dots looked square in QA previews, which is exactly what a reviewer judges.
