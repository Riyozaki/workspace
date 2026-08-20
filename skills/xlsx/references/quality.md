# XLSX quality checklist

## Workbook correctness

- At least one worksheet is visible.
- Sheet and table names are valid and unique.
- Required cells are populated.
- Formulas use invariant syntax and contain no broken references.
- Formula calculation mode is automatic.
- Cached values are refreshed in Excel or LibreOffice.
- No formula result is an Excel error token.
- External workbook links and macros are absent unless explicitly required.

## Modeling quality

- Assumptions are isolated, labeled, and visually distinct.
- Derived values are formulas, not pasted values.
- Formula patterns are consistent across periods.
- Currency, percentages, dates, units, zeros, and negatives use deliberate formats.
- Denominators and empty inputs are handled explicitly.
- Sources and update dates are recorded.
- Hidden sheets have a documented purpose.

## Usability

- Freeze panes preserve useful headers.
- Data regions use native tables where filtering helps.
- Data validations constrain user inputs.
- Conditional formats explain exceptions rather than decorate every cell.
- Charts reference workbook ranges, have titles/units, and do not combine incompatible scales.
- Editable cells are unlocked if worksheet protection is used.

## Print and visual QA

- Every user-facing sheet has an intentional print area.
- Wide sheets use landscape and fit-to-width without making text unreadable.
- Repeated header rows work on multipage tables.
- No clipped values, `#####`, hidden labels, blank print pages, or chart overlap.
- Rendered pages are inspected individually after the final recalculation.

## Formula gate

`openpyxl` writes formula text but does not calculate it. A workbook with formulas is draft-quality until:

1. `xlsx-recalc` or Microsoft Excel recalculates it;
2. cached values are re-read;
3. formula-error validation passes;
4. rendered output is regenerated from that recalculated file.
