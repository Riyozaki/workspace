# Declarative PPTX creation

Create with:

```bash
scripts/documentctl pptx-create spec.json presentation.pptx
```

The schema is `src/document_system/schemas/pptx-spec.schema.json`. The first implementation intentionally targets widescreen 16:9 so all layout measurements have one tested canvas.

## Top-level settings

```json
{
  "metadata": {"title": "Quarterly review", "author": "Operations"},
  "size": "wide",
  "language": "en-US",
  "footer": "Quarterly review · confidential",
  "theme": {
    "primary": "203F54",
    "accent": "C77932",
    "font": "Arial",
    "heading_font": "Arial"
  },
  "slides": []
}
```

## Layouts

- `title`: kicker, title, subtitle, footer.
- `section`: section number, title, subtitle.
- `bullets`: takeaway title plus structured bullets.
- `two-column`: two titled bullet cards.
- `metrics`: two to four KPI cards with semantic status colors.
- `table`: styled lookup/comparison table.
- `chart`: editable native PowerPoint chart.
- `image`: contain/cover image with optional caption.
- `quote`: large quotation and attribution.
- `timeline`: two to six dated milestones.

Every slide accepts `notes`, `source`, `footer`, and optional background color where applicable.

## Native chart

```json
{
  "layout": "chart",
  "title": "Revenue grew in every quarter",
  "chart_type": "column",
  "categories": ["Q1", "Q2", "Q3", "Q4"],
  "series": [
    {"name": "Actual", "values": [12, 14.5, 16.8, 19.2]},
    {"name": "Plan", "values": [13, 15.2, 17.5, 20]}
  ],
  "y_title": "USD million",
  "legend": "bottom",
  "data_labels": true,
  "source": "Source: management reporting"
}
```

Charts remain editable because PowerPoint receives native chart XML and an embedded workbook. That embedded XLSX is expected chart data, not an arbitrary executable object.

## Content budgets

Schema limits are guardrails, not targets:

- title: up to 120 characters, usually much shorter;
- ordinary slide: generally 3–6 primary bullets;
- metric card label: short noun phrase;
- table: normally no more than 5–6 columns and 6–8 body rows;
- timeline: 2–6 events;
- notes: evidence and delivery context, not a second report.

When content exceeds the budget, split the argument across slides rather than shrinking fonts.
