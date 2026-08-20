---
name: xlsx-workflows
license: Internal clean-room implementation; see repository dependency licenses.
description: Create, inspect, edit, recalculate, render, and validate Excel XLSX workbooks with formulas, tables, native charts, conditional formatting, data validation, print layouts, dashboards, and preservation-sensitive cell updates. Use for .xlsx, spreadsheet, workbook, tabular analysis, financial model, budget, tracker, dashboard, formulas, or Excel output.
---

# XLSX workflows

Use `scripts/documentctl` rather than ad-hoc spreadsheet scripts.

References:

- `skills/xlsx/references/creation-spec.md`
- `skills/xlsx/references/edit-plan.md`
- `skills/xlsx/references/quality.md`

## Routes

| Task | Route |
|---|---|
| Normalize CSV/TSV | `documentctl xlsx-import messy.csv clean.xlsx` |
| Inspect formulas and workbook structure | `documentctl inspect workbook.xlsx` |
| Create a workbook | JSON spec → `documentctl xlsx-create` |
| Edit exact cells while preserving package fidelity | edit plan → `documentctl xlsx-edit` |
| Trace formulas/cite cells | `documentctl xlsx-trace` and `xlsx-formulas` |
| Recalculate formulas | `documentctl xlsx-recalc` through isolated LibreOffice |
| Validate | `documentctl xlsx-validate` |
| Layout/print QA | `documentctl render` and inspect every rendered sheet/page |

For bulk dataframe analysis, use pandas in a temporary script, then materialize the audited result through the declarative workbook spec or a narrowly tested adapter.

## Mandatory workflow for formula workbooks

```bash
scripts/documentctl xlsx-create spec.json draft.xlsx --require-formulas
scripts/documentctl xlsx-recalc draft.xlsx final.xlsx
scripts/documentctl xlsx-validate final.xlsx \
  --require-formulas --require-recalculated \
  --require-sheet Summary --require-cell 'Summary!B5' \
  -o .document-work/job/qa.json
scripts/documentctl render final.xlsx -o .document-work/job/render
```

If LibreOffice is unavailable, formula cached values remain missing. Structural work can continue, but a formula workbook is not final until Excel or LibreOffice recalculates it and formula-error QA is rerun.

## Existing workbook edits

```bash
scripts/documentctl inspect source.xlsx -o .document-work/job/input.json
scripts/documentctl xlsx-edit source.xlsx result.xlsx --plan edit-plan.json
scripts/documentctl inspect result.xlsx -o .document-work/job/output.json
scripts/documentctl xlsx-validate result.xlsx -o .document-work/job/qa.json
```

The direct editor changes worksheet XML only, preserves styles and unrelated package parts, removes stale calculation chains when necessary, and forces full recalculation. It refuses unsafe edits to shared/array formulas and non-anchor merged cells.

## Modeling rules

- Store assumptions in labeled cells and reference them from formulas; do not bury constants inside repeated formulas.
- Use blue text/yellow fill for editable inputs, black for formulas, and consistent number formats.
- Percentages are decimal fractions (`0.15` displays as `15.0%`).
- Keep units in headers: `Revenue (RUB m)`, not only in notes.
- Use formulas for derived values, not hardcoded answers.
- Guard zero denominators and empty-input cases.
- Run `xlsx-formulas --libreoffice-compatible` before the LibreOffice gate. It detects circular references, volatile formulas, unresolved/external ranges, unsupported spill functions, and missing `_xlfn.` prefixes.
- Use `xlsx-trace 'Sheet!A1'` for precedent/dependent chains and stable `[Sheet!A1]` citations.
- `xlsx-recalc` refuses external-link workbooks by default because recalculation can destroy links and their only cached values.
- Use one formula pattern across each projection row/column; isolated hardcodes are suspicious.
- Charts must use native workbook data ranges and compatible scales. Do not mix percentages and currency on one axis.
- Include a source/provenance sheet for externally sourced data.
- Keep at least one visible worksheet and give every user-facing sheet an intentional print area.

## Delivery gate

- Package and relationship validation: zero errors.
- Required sheets/cells/formulas exist.
- No `#REF!`, `#VALUE!`, `#DIV/0!`, `#NAME?`, `#N/A`, or unresolved placeholders.
- Formula cached values exist after recalculation.
- Inputs, formulas, units, and sources are distinguishable.
- Native tables/charts/validations remain editable.
- Hidden sheets, external links, macros, and embeddings are inventoried.
- Every printable page is visually reviewed for clipping, excessive pagination, unreadable charts, and repeated headings.
