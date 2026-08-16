---
name: document-quality
description: "The quality gate every document deliverable passes before it is handed over. Use at the end of any docx/xlsx/pptx/pdf task, and read it first when planning a large or high-stakes document. Covers the delivery checklist, self-review, typography and layout rules, Russian-language typographic conventions, and the failure modes that validation cannot catch."
---

# Document quality gate

Format-specific traps live in the `docx`, `xlsx`, `pptx`, and `pdf` skills. This is what applies to all of them, and what separates a file that technically opens from one a person is glad to receive.

---

## The one rule

**Look at the output before delivering it.**

```bash
.venv/bin/python tools/validate.py out.docx
.venv/bin/python tools/render.py out.docx -o .workdir/qa
# then actually read the PNGs in .workdir/qa/
```

Validation proves the file is not corrupt. It cannot see that a heading landed alone at the bottom of a page, that a table ran into the margin, that the cover text is white on a pale background, or that a chart's labels are unreadable. Every one of those ships as a "valid" file.

Render every page, not the first one. Most defects are on page 3.

---

## Before you write anything

Five questions. If the request does not answer them, either the answer is obvious from context or you should ask:

1. **Who reads this, and what do they do after reading?** A board memo, an onboarding guide, and a regulator filing are different documents even with identical facts.
2. **What decision or action does it drive?** Documents that inform nothing get skimmed and forgotten.
3. **How long?** "A short summary" and "a comprehensive report" differ by 10×. A stated word count means ±20%.
4. **What format, and why?** Word for anything the reader will edit or comment on; PDF for anything fixed; slides for anything presented aloud; a spreadsheet only when the numbers must recalculate.
5. **Is there a template, brand, or precedent?** If yes, follow it — it beats every default in this skill.

Then plan the structure before writing prose. A document whose outline you cannot state in one breath will not have one.

---

## Structure

- **Lead with the conclusion.** Executive summary, then the argument, then the detail. Readers who stop after one paragraph should still get the point.
- **Headings are a table of contents, not decoration.** "Выводы и рекомендации" tells the reader something; "Раздел 3" does not. Someone reading only the headings should follow the argument.
- **One idea per paragraph**, 3–5 sentences. A paragraph that fills half a page is two paragraphs.
- **Tables for anything with more than two dimensions.** Prose comparing five things across three criteria is unreadable; the same content as a 5×3 table is obvious.
- **Bullets only for genuine lists.** A bulleted argument is an argument with its connective tissue removed. If the items have a logical relationship, write sentences.
- **Front matter earns its place.** A cover and TOC belong on a 20-page report, not a 2-page memo.

## Numbers and evidence

- **Every number has a source or a stated assumption.** "Выручка выросла на 23%" needs to say since when, and where the figure came from.
- **Consistent units and precision.** Do not mix `1 250 000 ₽` and `1,25 млн ₽` in one table. Do not report 3 decimals on an estimate.
- **Do not invent data.** If a number is unknown, say so or mark it clearly as an assumption. A plausible fabricated figure is the worst possible outcome — it survives review and fails in use.
- **Round in prose, keep precision in tables.**

---

## Typography

- **Body text 10–12pt**, line height 1.4–1.5. Headings step down clearly: 20 / 15 / 12.5pt is a workable scale.
- **Line length 65–90 characters.** Full-width text on A4 at 11pt is too wide — use margins of at least 18–20mm.
- **Two font families maximum**, three weights. A serif for body and a sans for headings is a safe pairing; so is one family throughout.
- **Never pure `#000000` on pure `#FFFFFF`.** `#1F2933` on white reads better and looks less harsh in print.
- **One accent colour**, used consistently for the same meaning throughout.
- **Contrast is a requirement, not a preference.** Body text needs at least 4.5:1 against its background; large headings 3:1. This is the most common defect in generated documents and the render is where you catch it.
- **Never `#FF0000` / `#0000FF`.** Pick a low-saturation palette: one hue direction, three tiers (primary for headings, dark for body, light for captions).

## Layout

- **No orphans or widows** — a single line stranded across a page break. `orphans: 2; widows: 2` in CSS.
- **Headings never sit alone at the bottom of a page.** `page-break-after: avoid`.
- **Tables and figures do not split across pages** unless they are genuinely long, in which case the header row repeats.
- **Every table and figure has a caption** and is referenced from the text. A chart nobody points at is decoration.
- **Consistent spacing.** Pick one vertical rhythm and hold it; irregular gaps read as carelessness even when the reader cannot say why.

---

## Russian-language conventions

When the document is in Russian, these are not optional — getting them wrong marks the document as machine-made:

- **Quotation marks are «ёлочки»**, with „лапки“ nested inside. Not `"straight"` and not English “curly”.
- **Dash is `—` (em dash) with spaces** around it in text: `Проект — это...`. The hyphen `-` joins words; the en dash `–` spans ranges (`2020–2024`, no spaces).
- **Non-breaking space** (`\u00A0`) between a number and its unit (`10 кг`, `1250 ₽`), after short prepositions (`в 2024 году`), and in initials (`А. С. Пушкин`). Without it the line breaks in embarrassing places.
- **Thousands separator is a space**, not a comma: `1 250 000`. Decimal separator is a comma: `3,14`.
- **Dates**: `15 августа 2026 г.` in prose, `15.08.2026` in tables. Never `08/15/2026`.
- **`ё`** — use it consistently, or consistently not. Mixed usage looks sloppy.
- **Percent sign has no space**: `23%`. Currency does: `1 250 ₽`.
- Headings in Russian documents do not take a trailing period.

---

## Self-review before delivery

Read the render as if you were the recipient, then check:

**Content**
- Does it answer the question that was actually asked?
- Could a reader act on it, or does it end without a conclusion?
- Is anything asserted that you cannot support?
- Would cutting 20% lose anything? (Usually not.)

**Correctness**
- Do the numbers in the text match the numbers in the tables?
- Do totals add up? Do percentages sum to 100 where they should?
- Are all names, dates, and titles right?
- Do cross-references point at the right sections?

**Presentation**
- Any placeholder text left? (`validate.py` greps, but it does not know your domain.)
- Any `v2`, `draft`, `итог_финал` files left in the output directory? Deliver one clean file.
- Is the filename descriptive, in the user's language, with no spaces-as-underscores mess?
- Headers, footers, page numbers present and correct?
- Does every image and chart render?

**Consistency**
- One language throughout — body, headings, headers, chart labels, filename. A Russian report with an English footer is a common and visible slip.
- One date format, one number format, one terminology set. If it is «пользователь» in section 1, it is not «юзер» in section 4.

---

## Failure modes

| Symptom | Cause |
|---|---|
| Formula cells look empty everywhere but Excel | No cached values — run `tools/recalc.py` |
| Cover text invisible | Text colour matches the background — check the render |
| Text runs off a slide | Coordinates past the canvas are written, not clamped — `validate.py` reports these |
| Table wider than the page | Column widths do not sum to the table width |
| Wrong font in the delivered file | Font not installed on the reader's machine — prefer common families for travelling documents |
| PDF page size ignored | An `@page { size }` rule overrides `page.pdf()` dimensions |
| Cyrillic renders as boxes or falls back | Font lacks Cyrillic coverage — `tools/install_fonts.py --report` shows which do |
| "Unreadable content" prompt in Word | Dangling relationship or malformed XML part — `validate.py` finds both |

---

## Delivery

State plainly what you produced, where it is, and anything the user must know: assumptions you made, numbers you could not verify, sections you left deliberately thin. If you could not do part of the task, say so in the first sentence rather than burying it.

Do not describe the document's contents back at length — they can read it. Describe the decisions you made that they might want to change.
