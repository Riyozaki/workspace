# Declarative XLSX creation

Create with:

```bash
scripts/documentctl xlsx-create spec.json workbook.xlsx
```

The JSON schema is `src/document_system/schemas/xlsx-spec.schema.json`.

## Top-level structure

```json
{
  "metadata": {"title": "Sales model", "creator": "Finance"},
  "theme": {"primary": "23465C", "accent": "C47A35", "font": "Arial"},
  "active_sheet": "Summary",
  "sheets": []
}
```

Each sheet can define:

- visibility, tab color, zoom, gridlines, freeze panes;
- merged ranges, columns, row dimensions;
- explicit cells and formulas;
- native Excel tables and charts;
- conditional formatting and data validation;
- orientation, paper size, print area, repeated rows/columns, fit-to-page, headers/footers.

## Styled cells

```json
{
  "cells": [
    {"cell": "A1", "value": "Revenue model", "style": "title"},
    {"cell": "A3", "value": "Growth assumption", "style": "text"},
    {"cell": "B3", "value": 0.08, "style": "input", "number_format": "0.0%"},
    {"cell": "B5", "formula": "=B4*(1+$B$3)", "style": "currency"}
  ]
}
```

Built-in styles:

- structural: `title`, `subtitle`, `section`, `header`, `note`;
- semantic: `input`, `formula`, `text`, `positive`, `negative`;
- numeric: `integer`, `decimal`, `currency`, `percent`, `date`.

Explicit style overrides support number format, font/fill colors, bold/italic, size, alignment, wrapping, and cell locking.

## Native table

```json
{
  "tables": [
    {
      "name": "SalesData",
      "start_cell": "A1",
      "headers": ["Month", "Revenue", "Margin"],
      "rows": [["Jan", 1200000, 0.21], ["Feb", 1450000, 0.24]],
      "style": "TableStyleMedium2"
    }
  ]
}
```

Table names are unique workbook-wide. Explicit `cells` are applied after table data so individual numeric columns can receive currency/percent formats.

## Native chart

```json
{
  "charts": [
    {
      "type": "column",
      "title": "Monthly revenue",
      "data_sheet": "Data",
      "data_range": "B1:B13",
      "categories_range": "A2:A13",
      "anchor": "E3",
      "series_from": "columns",
      "titles_from_data": true,
      "legend": "none"
    }
  ]
}
```

Supported types: bar, column, line, pie, area. Use compatible units per axis. Source data remains editable.

## Formula guidance

- Formulas must begin with `=` and use invariant OOXML syntax: English function names and comma separators.
- Quote sheet names containing spaces: `='Input Data'!B5`.
- Inputs belong in separate labeled cells.
- Apply `IFERROR` only when the fallback is meaningful; do not hide model defects.
- Newly generated formulas have no cached results until recalculated by Excel or LibreOffice.
