---
name: docx
description: "Create, edit, and review Word documents (.docx/.dotx). Use for any Word deliverable — reports, memos, letters, contracts, specifications, templates — and for editing, redlining with tracked changes, adding comments, or extracting content from an existing .docx. Do not use for PDF, spreadsheet, or slide deliverables."
---

# Word documents

## Pick the route first

| Situation | Route |
|---|---|
| A `.docx` exists and its **formatting matters** (template to fill, document to edit or redline) | **Edit in place** — unzip, patch `word/document.xml`, rezip |
| No source file — building from nothing | **Create** with `docx` (npm) |
| A `.docx` is just a **source of text** (its look is irrelevant) | Read it with pandoc, then Create |

**Never rewrite an existing document from scratch.** If the user hands you a file, its styles, numbering, headers, and theme are part of the deliverable. Rebuilding loses all of it and it always shows.

**Never write Markdown and convert it with pandoc as the delivery path.** Pandoc output is generic: no real cover, no controlled table widths, default fonts. It is fine for previews, not for something a person will send.

---

## Reading

```bash
# text + structure (fast, lossy — formatting is gone)
.venv/bin/python -c "import pypandoc;print(pypandoc.convert_file('in.docx','markdown'))"

# see what it actually looks like — do this before editing anything
.venv/bin/python tools/render.py in.docx -o .workdir/look
```

Plain text extraction hides the thing that usually matters. Look at the render.

---

## Creating

Write a Node script against `docx` (v9). Run it from the repo root so `require` resolves `node_modules`.

```js
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
        Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
        Header, Footer, PageNumber, TableOfContents, LevelFormat } = require('docx');
const fs = require('fs');

const doc = new Document({
  styles: { default: { document: { run: { font: 'PT Serif', size: 22 } } } }, // size = half-points
  numbering: { config: [{ reference: 'bullets', levels: [
    { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT },
  ]}]},
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 } } },  // A4 in DXA
    headers: { default: new Header({ children: [new Paragraph('Отчёт')] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: ['Стр. ', PageNumber.CURRENT, ' из ', PageNumber.TOTAL_PAGES] })],
    })]})},
    children: [ /* ... */ ],
  }],
});
Packer.toBuffer(doc).then(b => fs.writeFileSync('out.docx', b));
```

### Run `docx_fix.js` after every write — not optional

```js
const { fixDocx } = require('./tools/js/docx_fix.js');
await fixDocx('out.docx');
```

docx-js emits a `styles.xml` with **no `Normal` style**, while every style it
writes declares `w:basedOn="Normal"`. Word tolerates the dangling reference
because it has a built-in fallback, so the file looks perfect when you open it.
Nothing else tolerates it: pandoc cannot resolve the chain and reports every
heading as a plain paragraph, which means the preview renders headings as body
text, extracted structure is flat, and a generated TOC comes back empty.

The failure is invisible where you check and total everywhere else. `fixDocx`
inserts the missing style and adds the `outlineLvl` that docx-js also omits.

### Traps that cost real time

- **Page size defaults to A4.** US Letter is `{ width: 12240, height: 15840 }` DXA (1440 DXA = 1 inch). Russian and EU documents want A4: `11906 × 16838`.
- **Landscape:** pass *portrait* dimensions plus `orientation: PageOrientation.LANDSCAPE`; the library swaps them itself. Passing swapped dimensions too gives you portrait back.
- **Tables need widths in two places:** `columnWidths: [...]` on the `Table` *and* `width: { size, type: WidthType.DXA }` on every `TableCell`. Column widths must sum to the table width. `WidthType.PERCENTAGE` renders wrong in Google Docs.
- **Shading:** `ShadingType.CLEAR` with a `fill`. `ShadingType.SOLID` renders as a black block.
- **Lists:** use a `numbering` config. A literal `•` in the text gives you a bullet glyph with no indent behaviour, and doubles up if the style also bullets.
- **`\n` does nothing.** One `Paragraph` per line, always.
- **`PageBreak` lives inside a `Paragraph`**, not beside one.
- **`ImageRun` needs `type`** (`'png'`, `'jpg'`, …) or it throws.
- **Table of contents:** headings must use built-in `HeadingLevel.*`. A custom heading style needs an explicit `outlineLevel` or it will not appear in the TOC. The TOC renders as "right-click → update field" until opened in Word — that is normal, not a bug.
- **Horizontal rule:** a paragraph with a bottom border. Not a one-row table.
- **Right-aligned text on the same line** (dot leaders, signature lines): use `PositionalTab`, not spaces or dots.
- **Font size is in half-points.** `size: 22` is 11pt.
- **`styles.paragraphStyles` does not override the built-in heading styles.**
  Defining `{ id: 'Heading1', ... }` there is silently ignored — docx-js has
  already written its own. Style headings through `styles.default.heading1`
  (and `heading2`, …), or accept the defaults and set the run properties on
  each paragraph.
- **`HeadingLevel.TITLE` becomes document *metadata* to pandoc**, not a heading.
  It renders correctly in Word, and `render.py` handles it, but a naive
  fragment conversion drops that line entirely.

### Cyrillic

Set a font that actually has Cyrillic: `PT Serif`, `Inter`, `JetBrains Mono` are installed by `tools/install_fonts.py`. Word substitutes silently on a machine that lacks the font, so prefer widely available families (`Times New Roman`, `Arial`, `Calibri`) when the file will travel to an unknown Windows box.

---

## Editing an existing document

```bash
unzip -q in.docx -d unpacked/
find unpacked -type l -delete          # untrusted input may carry symlinks
# edit unpacked/word/document.xml — do NOT pretty-print it
(cd unpacked && rm -f ../out.docx && zip -Xr ../out.docx .)
.venv/bin/python tools/validate.py out.docx
```

Word fragments text across many `<w:r>` runs (spell-check state, revision ids), so a sentence you can see is often not a contiguous string in the XML. Search for a short distinctive fragment, or merge adjacent identically-formatted runs first.

**Parse with `defusedxml` or `lxml`, never `xml.etree.ElementTree`** — ElementTree rewrites namespace prefixes on write and Word will reject the result.

### Tracked changes

Wrap inserted runs in `<w:ins>` and deleted runs in `<w:del>`, each with `w:id`, `w:author`, `w:date`. Inside `<w:del>`, the text element is `<w:delText>`, not `<w:t>` — get this wrong and the text silently disappears.

Deleting a whole paragraph means marking every run deleted **and** marking the paragraph mark itself:

```xml
<w:pPr><w:rPr><w:del w:id="7" w:author="..." w:date="..."/></w:rPr></w:pPr>
```

`<w:del/>` must come first among that `rPr`'s children — the order is schema-enforced.

Any text you change without wrapping it is an untracked edit: invisible in the accepted view, and exactly the thing a reviewer will catch later.

---

## Before delivering

```bash
.venv/bin/python tools/validate.py out.docx      # structure + placeholders
.venv/bin/python tools/render.py out.docx -o .workdir/qa   # then LOOK at the PNGs
```

Checklist:

1. Opens without a repair prompt, `validate.py` passes.
2. You have **looked at every page** of the render, not just the first.
3. Headers, footers, and page numbers present and on the right pages.
4. No `TODO`, `[Company Name]`, `Lorem ipsum` — `validate.py` greps for these.
5. Tables fit the page width; nothing runs into the margin.
6. Every image renders (a missing image is a blank gap, not an error).
7. Filename names the topic in the user's language — `Квартальный_отчёт.docx`, never `output.docx`. Do not leave `v1`/`final`/`draft2` variants in the output directory.
