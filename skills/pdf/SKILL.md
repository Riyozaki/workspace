---
name: pdf
description: "Work with PDF files: create print-quality PDFs, merge, split, rotate, watermark, encrypt, extract text and tables, rasterise pages to images, and fill forms. Use whenever a .pdf is the input or the deliverable."
---

# PDF

## Creating

Three routes, in order of preference.

### 1. HTML → Chromium (default for anything with a layout)

Best typography and layout control, and you already know CSS. Chromium is the same engine that renders the QA previews.

```js
const { renderPdf } = require('./tools/js/chromium.js');  // run from the repo root
await renderPdf('report.html', 'out.pdf', {
  format: 'A4',
  printBackground: true,
  margin: { top: '20mm', bottom: '20mm', left: '18mm', right: '18mm' },
  displayHeaderFooter: true,
  headerTemplate: '<div style="font-size:8pt;width:100%;text-align:center;color:#667085">Отчёт</div>',
  footerTemplate: '<div style="font-size:8pt;width:100%;text-align:center;color:#667085">'
                + '<span class="pageNumber"></span> / <span class="totalPages"></span></div>',
});
```

Print CSS that matters:

```css
@page { size: A4; margin: 20mm; }
h1, h2, h3 { page-break-after: avoid; }
table, figure, pre { page-break-inside: avoid; }
p { orphans: 2; widows: 2; }
.page-break { page-break-before: always; }
```

- **`displayHeaderFooter` ignores your page `margin` unless it is large enough** — headers overlap the body at margins under ~15mm.
- **An `@page { size: ... }` rule beats the `width`/`height` you pass to `page.pdf()`.** If you need a non-A4 page, either set it in `@page` or leave `@page` out entirely. This silently turns custom sizes into portrait A4.
- **Wait for fonts:** `await page.evaluate(() => document.fonts.ready)` before printing, or the first render may use fallback metrics.
- Use `assets/preview.css` as a starting point, not as house style.

### 2. Typst (long structured documents, maths, precise typography)

Bundled — no LaTeX needed. Excellent for reports with numbered sections, cross-references, and formulas.

```python
import typst
typst.compile("report.typ", output="report.pdf")
```

```typst
#set page(paper: "a4", margin: 2cm, numbering: "1")
#set text(font: "PT Serif", size: 11pt, lang: "ru")
#set heading(numbering: "1.1")
= Введение
Формула: $sum_(i=1)^n x_i = 42$
```

Set `lang: "ru"` for correct hyphenation. The font must be one installed in `assets/fonts/`.

### 3. reportlab (programmatic drawing, exact coordinates)

For labels, certificates, badges — anything positioned to the millimetre.

**Never use Unicode superscript/subscript characters** (`²`, `₂`) — the built-in fonts lack those glyphs and render solid black boxes. Use `<super>` / `<sub>` markup in a `Paragraph`.

For Cyrillic you must register a font; the built-in Type 1 faces are Latin-only:

```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
pdfmetrics.registerFont(TTFont('PTSerif', 'assets/fonts/pt-serif-400.ttf'))
```

---

## Reading and extracting

```python
import pdfplumber
with pdfplumber.open("doc.pdf") as pdf:
    text = pdf.pages[0].extract_text()
    tables = pdf.pages[0].extract_tables()     # list of row lists
```

`pdfplumber` keeps layout and is the right tool for tables. `pypdf` is faster for plain text. Neither reads scanned pages — if `extract_text()` returns nothing, the page is an image, and there is no OCR engine installed here; say so rather than returning empty text.

## Manipulating

```python
from pypdf import PdfReader, PdfWriter

writer = PdfWriter()
for name in ("a.pdf", "b.pdf"):
    for page in PdfReader(name).pages:
        writer.add_page(page)
writer.write("merged.pdf")
```

Rotate `page.rotate(90)` · encrypt `writer.encrypt("user", "owner")` · watermark `page.merge_page(stamp)` · split by writing one page per file.

## Rasterising

```bash
.venv/bin/python tools/render.py doc.pdf -o .workdir/qa --dpi 150
```

Uses pypdfium2 — no poppler required. This is how you *look* at a PDF.

---

## Before delivering

```bash
.venv/bin/python tools/validate.py out.pdf
.venv/bin/python tools/render.py out.pdf -o .workdir/qa
```

`validate.py` warns when a PDF has no extractable text (image-only: bad for search, copy-paste, and accessibility) and greps the text layer for placeholders.

Checklist: page count is what you intended · no content in the margins · page numbers correct and starting where they should · fonts embedded (they are, if it came from Chromium or Typst) · text is selectable · filename names the topic.
