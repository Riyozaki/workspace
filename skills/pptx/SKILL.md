---
name: pptx
description: "Create and edit presentations (.pptx/.potx). Use for slide decks, pitch decks, and any task where a .pptx is the input or the deliverable, including filling templates, editing existing decks, and extracting slide content. Do not use for Word or PDF deliverables."
---

# Presentations

| Task | Approach |
|---|---|
| **Create** a deck | `pptxgenjs` script |
| **Edit** a deck, or fill a template | unzip → edit `ppt/slides/slideN.xml` → rezip |
| **Read** a deck | `.venv/bin/markitdown deck.pptx` |
| **See** a deck | `.venv/bin/python tools/render.py deck.pptx -o .workdir/qa` |

When a template exists, **use it**. Its masters, layouts, theme colours, and fonts are the deliverable's identity; a from-scratch deck in the same colours still looks foreign.

---

## Creating with pptxgenjs

```js
const pptxgen = require('pptxgenjs');
const pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';           // 10 × 5.625 in — the default is 10 × 7.5

const slide = pres.addSlide();
slide.background = { color: '1E2761' };
slide.addText('Квартальный обзор', {
  x: 0.6, y: 2.2, w: 8.8, h: 1.0,
  fontSize: 40, bold: true, color: 'FFFFFF', fontFace: 'Inter',
});
slide.addNotes('Speaker notes go here, never in a text box.');
await pres.writeFile({ fileName: 'deck.pptx' });
```

### Traps

- **`LAYOUT_16x9` is 10 × 5.625 inches, not 13.3 wide.** Coordinates past the edge are written, not clamped — the shape simply is not on the slide. (`LAYOUT_WIDE` is 13.3 × 7.5.)
- **Hex colours: no `#`, no alpha.** `color: 'FF0000'`. Both `'#FF0000'` and 8-digit hex **corrupt the file**. For translucency use `transparency: 0-100` on fills, `opacity` on shadows — each is ignored on the other.
- **pptxgenjs mutates option objects in place** (converting to EMU on first use). Never share one options object between two `add*` calls; build a fresh one each time.
- **Shadow `offset` must be ≥ 0.** A negative offset corrupts the file; for an upward shadow use `angle: 270` with a positive offset.
- **`letterSpacing` is silently ignored** — the real option is `charSpacing`.
- **Lists:** `bullet: true` per item, never a literal `•` (double bullets). `breakLine: true` on every array item except the last. Space them with `paraSpaceAfter`, not `lineSpacing`.
- **One `new pptxgen()` per output file.** Reusing an instance leaks slides between decks.
- **`rectRadius` only applies to `ROUNDED_RECTANGLE`.**
- **Gradient fills are not supported** — use a gradient image as the background.
- **Text boxes have built-in padding.** Set `margin: 0` when text must align to a shape or line at the same `x`.
- **Speaker notes go in `slide.addNotes()`**, once per slide, plain text.

### Charts

Keep charts native — `slide.addChart()` — so they stay editable and crisp:

```js
slide.addChart(pres.ChartType.bar, [{ name: 'Выручка', labels: ['Q1','Q2','Q3'], values: [120,150,190] }], {
  x: 0.5, y: 1.2, w: 9, h: 4,
  showValue: true, dataLabelPosition: 'outEnd',
  chartColors: ['1E2761', '4A6FA5', '8FB0D9'],
  showLegend: false,
  catAxisLabelColor: '667085', valAxisLabelColor: '667085',
  valGridLine: { color: 'E8EDF2', size: 1 }, catGridLine: { style: 'none' },
});
```

- **Default charts look dated** — no title, no labels, 2007 palette. Always set colours, labels, and quiet the gridlines.
- **On stacked bars, `dataLabelPosition` must be `ctr`, `inEnd`, or `inBase`.** `outEnd` **corrupts the file**.
- **A combo series using `secondaryValAxis` needs both `valAxes` and `catAxes`** declared with two entries each, or PowerPoint reports the deck as corrupt.
- Only chart types PowerPoint has no native form for (Sankey, chord, network) should be inserted as images — render those with matplotlib.

---

## Editing a deck or filling a template

```bash
.venv/bin/python tools/render.py template.pptx -o .workdir/template   # see the layouts first
python3 -c "import zipfile;zipfile.ZipFile('deck.pptx').extractall('unpacked')"
# structural work FIRST: add, delete, reorder (edit <p:sldIdLst> in ppt/presentation.xml)
# then edit ppt/slides/slideN.xml
(cd unpacked && rm -f ../out.pptx && zip -Xr ../out.pptx .)
.venv/bin/python tools/validate.py out.pptx
```

- **Do all structural work before editing content.** Duplicating a slide copies the file verbatim, so duplicate-then-edit clones the edit.
- **Parse with `defusedxml.minidom` or `lxml`.** Round-tripping OOXML through `xml.etree.ElementTree` rewrites namespace prefixes and corrupts the deck.
- **Template slots ≠ your content.** If the layout shows four team members and you have three, delete the fourth group entirely — image, text boxes, and all — not just its text. Then check the render for the orphaned photo frame you missed.
- **One `<a:p>` per list item.** Copy the sibling `<a:pPr>` to keep spacing. Text with leading/trailing spaces needs `xml:space="preserve"` on its `<a:t>`.
- **Let bullets inherit from the layout**; override only with `<a:buChar>`, `<a:buAutoNum>`, or `<a:buNone>`.
- **python-pptx cannot duplicate a slide**, and `text_frame.text = "..."` collapses a paragraph to one unstyled run — assign `run.text` instead to keep formatting.
- Legacy `.ppt` cannot be converted here (no LibreOffice). Ask the user for a `.pptx`.

---

## Design

Plain bullets on white will not impress anyone. Per deck:

- **Pick a palette that fits the topic.** If your colours would work equally well on an unrelated deck, they are not specific enough. One colour dominates (60-70%), one or two support, one sharp accent.
- **Sandwich the structure:** dark title and closing slides, lighter content slides between — or commit to dark throughout.
- **Repeat one motif** — rounded image frames, icons in filled circles, a consistent number treatment. Not a coloured stripe on every slide.
- **Every slide needs something visual.** Big stat callouts (60-72pt number, small label), two-column text/image, icon rows, 2×2 grids, half-bleed images.
- **Contrast is a hard requirement**, not taste: white-on-pale or dark-on-dark is the single most common defect, and the render is where you catch it.

| Theme | Primary | Secondary | Accent |
|---|---|---|---|
| Midnight Executive | `1E2761` | `CADCFC` | `FFFFFF` |
| Forest & Moss | `2C5F2D` | `97BC62` | `F5F5F5` |
| Warm Terracotta | `B85042` | `E7E8D1` | `A7BEAE` |
| Ocean Gradient | `065A82` | `1C7293` | `21295C` |
| Charcoal Minimal | `36454F` | `F2F2F2` | `212121` |
| Berry & Cream | `6D2E46` | `A26769` | `ECE2D0` |

---

## Before delivering

```bash
.venv/bin/python tools/validate.py deck.pptx
.venv/bin/python tools/render.py deck.pptx -o .workdir/qa
```

`validate.py` reports shapes that start off-canvas or overflow the slide — the defect you cannot see in code. `render.py` gives one PNG per slide with real geometry, backgrounds, and text colour; charts and images appear as labelled placeholders, so verify chart *contents* from the generating data, and everything else by looking.

Checklist: every slide has a visual · no text overflows its box · contrast holds on every background · no template leftovers · speaker notes where promised · filename names the topic in the user's language.
