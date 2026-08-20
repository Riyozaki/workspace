# DOCX edit plans

Apply with:

```bash
scripts/documentctl edit source.docx result.docx --plan edit-plan.json
```

## Template filling

```json
{
  "author": "Automation",
  "track_changes": false,
  "replacements": [
    {
      "find": "{{CLIENT_NAME}}",
      "replace": "Northern Systems LLC",
      "expected": 3,
      "scopes": ["document", "headers", "footers"]
    },
    {
      "find": "{{REPORT_DATE}}",
      "replace": "20 August 2026",
      "expected": 1
    }
  ],
  "metadata": {
    "title": "Northern Systems — assessment",
    "author": "Automation"
  }
}
```

Use `expected` for every placeholder. A mismatch stops the operation, preventing silent partial filling.

## Tracked review

```json
{
  "author": "Document Review",
  "track_changes": true,
  "replacements": [
    {
      "find": "within 30 calendar days",
      "replace": "within 20 business days",
      "expected": 1
    },
    {
      "find": "The supplier may terminate without notice.",
      "replace": "The supplier may terminate on 10 business days’ written notice.",
      "expected": 1
    }
  ],
  "comments": [
    {
      "target": "within 30 calendar days",
      "text": "Confirm that the replacement period matches the operational SLA.",
      "occurrence": 1,
      "initials": "DR",
      "phase": "before"
    }
  ]
}
```

Tracked deletion and insertion preserve run formatting and only wrap the changed range. The engine refuses ranges that cross drawings, fields, or incompatible nested containers.

## Fields

Replacement fields:

- `find`, `replace` — required text operation.
- `expected` — exact count; strongly recommended.
- `required` — defaults to true when no exact count is supplied.
- `all` — defaults to true; false replaces only the first occurrence across selected scopes.
- `scopes` — any of `document`, `headers`, `footers`.
- `track_changes`, `author`, `date` — per-operation overrides.

Comment fields:

- `target` — exact visible text in the main document.
- `text` — comment body.
- `occurrence` — 1-based occurrence, default 1.
- `phase` — `after` by default; use `before` when the anchored original range will then be redlined.
- `author`, `initials`, `date` — attribution.

## Limits and escape hatches

The current editor intentionally stops rather than guessing when:

- the replacement crosses a hyperlink boundary;
- text intersects a drawing, field, footnote reference, or other complex run;
- comment target is outside the main document;
- target count differs from `expected`.

For these cases, inspect the package and implement a narrowly tested operation. Do not fall back to raw string replacement or round-trip the full document through a high-level library.
