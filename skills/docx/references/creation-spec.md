# Declarative DOCX creation specification

`documentctl create SPEC.json OUTPUT.docx` validates the JSON against `src/document_system/schemas/docx-spec.schema.json` before authoring.

## Minimal example

```json
{
  "metadata": {"title": "Project brief", "author": "Example team"},
  "language": "en-US",
  "footer": {"left": "Project brief", "page_numbers": true, "page_number_label": "Page "},
  "content": [
    {"type": "heading", "level": 1, "text": "Summary"},
    {"type": "paragraph", "text": "The concise project summary."}
  ]
}
```

## Rich structure

Top-level keys:

- `metadata`: title, subject, author, keywords, category, comments.
- `language`: BCP-47-like Word language, e.g. `ru-RU`.
- `page`: A4/Letter, portrait/landscape, margins in millimetres.
- `theme`: six-digit RGB colors and body/heading font names.
- `cover`: optional title page.
- `header` and `footer`: running content; footer can contain a PAGE field.
- `toc`: `true` or a settings object. The field is updated by compatible office applications.
- `content`: ordered block list.

Supported content blocks:

- `heading`: `level`, `text` or rich `runs`.
- `paragraph`: `text` or rich `runs`, alignment, spacing, keep options.
- `bullets` / `numbered`: items as strings or `{text, level}`.
- `table`: headers, rows, percentage widths, zebra shading, caption.
- `callout`: highlighted text panel with accent border.
- `image`: path relative to the spec, size, alignment, caption.
- `chart`: bar, horizontal bar, line, or pie; labels and series.
- `page_break`.
- `spacer`: controlled vertical space.

## Rich runs

```json
{
  "type": "paragraph",
  "runs": [
    {"text": "Decision: ", "bold": true},
    {"text": "approved", "color": "227447"},
    {"text": " — source", "link": "https://example.com"}
  ],
  "align": "justify"
}
```

## Table example

```json
{
  "type": "table",
  "headers": ["Metric", "Current", "Target"],
  "widths_pct": [50, 25, 25],
  "rows": [
    ["Cycle time", "8 days", {"text": "5 days", "bold": true, "color": "227447"}],
    ["Defects", 14, 5]
  ],
  "caption": "Operational targets",
  "zebra": true
}
```

## Chart example

```json
{
  "type": "chart",
  "kind": "bar",
  "title": "Quarterly revenue",
  "labels": ["Q1", "Q2", "Q3", "Q4"],
  "series": [
    {"name": "2025", "values": [12, 15, 17, 20]},
    {"name": "2026", "values": [14, 18, 22, 27]}
  ],
  "y_label": "RUB million",
  "caption": "Source: management reporting"
}
```

## Authoring guidance

- Put facts and narrative in the spec; do not encode layout through spaces or Unicode bullets.
- Keep table widths at roughly 100%. Avoid more than six columns on portrait A4.
- Use page breaks intentionally before major appendices, not after every short section.
- Use one accent color direction. Reserve the accent for decisions, key values, and small rules.
- Generate charts from explicit numbers and retain those numbers in the source/spec for auditability.
- For documents longer than about 20 pages, split content generation into reviewed sections, then assemble one final spec.
