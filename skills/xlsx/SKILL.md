---
name: xlsx
description: "Create, edit, and audit spreadsheets (.xlsx/.xlsm/.csv). Use whenever a spreadsheet is the input or the deliverable — financial models, budgets, data cleanup, formula work, formatted tables, charts. Do not use when the deliverable is a Word document or a slide deck that merely contains a table."
---

# Spreadsheets

| Task | Tool |
|---|---|
| Create / edit with formulas and formatting | `openpyxl` |
| Bulk data in or out | `pandas` (`read_excel` / `to_excel`) |
| Quick look at contents | `.venv/bin/markitdown file.xlsx` |
| Read a model's formulas **and** values | two `load_workbook` passes — see below |

---

## The rule that breaks people: recalculation

openpyxl writes formulas as plain strings with **no cached result**. Until something computes them, every formula cell reads back as `None` to pandas, to `data_only=True`, to any preview, and to any converter. The file looks empty to everything except Excel.

The usual fix is to open the file in LibreOffice. **There is no LibreOffice in this environment and it cannot be installed.** Use the bundled recalculator instead:

```bash
.venv/bin/python tools/recalc.py model.xlsx          # rewrites in place
.venv/bin/python tools/recalc.py model.xlsx --json   # machine-readable report
```

It evaluates every formula with the pure-python `formulas` engine and injects the results as cached values, then sets `fullCalcOnLoad` so Excel re-verifies on open.

- Exit `0` = everything evaluated. Exit `1` = at least one cell is an Excel error.
- **A clean run proves the formulas *evaluate*, not that they are *right*.** An off-by-one range gives a spotless report full of wrong numbers. Write two or three formulas, check the values are what you expect, and only then build out the grid.

### Functions the engine cannot evaluate

`recalc.py` reports these by name instead of leaving a bare `#NAME?`:

`XLOOKUP` · `XMATCH` · `FILTER` · `SORTBY` · `TEXTSPLIT` · `LAMBDA` · `LET`

Use `INDEX`/`MATCH` for lookups, and sort/filter/deduplicate in Python before writing cells. Prefer the Excel-2007 function set (`SUMIFS`, `INDEX`, `MATCH`, `IFERROR`, `SUMPRODUCT`) which needs no special handling.

Six post-2007 functions must be written with an `_xlfn.` prefix, because openpyxl copies your string into the XML verbatim and Excel stores these names prefixed (its UI hides that):

`_xlfn.TEXTJOIN` · `_xlfn.CONCAT` · `_xlfn.IFS` · `_xlfn.SWITCH` · `_xlfn.MAXIFS` · `_xlfn.MINIFS`

---

## Requirements for anything you ship

- **Use formulas, not computed constants.** `ws['B10'] = '=SUM(B2:B9)'`, never the Python-side total. The sheet has to survive someone editing an input.
- **Reference assumptions, don't inline them.** `=B5*(1+$B$6)`, never `=B5*1.05`.
- **Follow the user's spec literally** — exact tab names, exact headers, the formula they asked for. An elegant redesign that computes something else is a failure.
- **Document every hardcoded number** where the reader will see it: a cell comment or a labelled cell beside the table. Cite the source if there is one; if the number came from the user, say so.
- **A blank workbook for someone to fill in** needs a short legend saying which cells are inputs, plus one example row in the expected format. Never add an example row to a file you were asked to edit.
- **Editing an existing file: match its conventions.** They override everything here. Find its input cells first — they are usually marked by font colour or fill — write only there, and leave existing formulas alone.
- **Professional font** throughout (Arial, Calibri, Times New Roman) unless told otherwise.

## Financial model conventions

Unless the file already does something else:

**Colour** — blue text `0000FF` for hardcoded inputs and scenario levers · black for formulas · green `008000` for links to another sheet · red `FF0000` for links to another file · yellow fill `FFFF00` for cells the user must fill in.

**Numbers** — currency `$#,##0` or `#,##0 ₽` with the unit in the header (`Выручка, млн ₽`) · negatives in parentheses · zeros as `-` (`#,##0;(#,##0);-`) · percentages `0.0%` **stored as fractions** (`0.15` → `15.0%`; storing `15` gives `1500.0%`) · multiples `0.0x` · years as text so they don't render as `2 024`.

**Structure** — every assumption in its own labelled cell · formulas identical across a projection row, since one hand-edited cell mid-row is the most common silent error · guard every denominator that could be zero.

---

## openpyxl traps

- **Reading a model takes two loads.** `data_only=True` gives cached values with formulas gone; the default gives formulas with no values. One pass cannot give both.
- **`data_only=True` is destructive if you save.** That workbook has no formulas left — saving replaces every one with a literal, permanently.
- **`data_only=True` right after you wrote the file returns `None` everywhere.** Run `recalc.py` first.
- **Merged cells: write the top-left anchor only.** Every other cell in the range is read-only.
- **`.xlsm` loses its macros** unless you pass `keep_vba=True`.
- **Sheet names with spaces must be quoted** in references: `='Исходные данные'!$B$5`. Unquoted gives `#VALUE!`.
- **Cyrillic sheet names are fine**, but `formulas` uppercases them internally — that is cosmetic, in the report only.
- **A workbook linking to another file** loses those links if you re-save with openpyxl: the cached value is the only copy of that data, and openpyxl strips it. Copy the values out first.

---

## Before delivering

```bash
.venv/bin/python tools/recalc.py book.xlsx
.venv/bin/python tools/validate.py book.xlsx
.venv/bin/python tools/render.py book.xlsx -o .workdir/qa   # then look at it
```

`validate.py` fails on any `#REF!`/`#VALUE!`/`#DIV/0!` left in the file and warns about formulas with no cached value. `render.py` shows each sheet as a grid — that is where you notice a column of `###`, a stray test row, or a total that is obviously wrong by an order of magnitude.
