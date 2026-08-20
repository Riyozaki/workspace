---
name: pptx-workflows
license: Internal clean-room implementation; see repository dependency licenses.
description: Create, inspect, edit, render, and validate PowerPoint PPTX decks with professional layouts, native charts, tables, images, speaker notes, template-preserving text replacement, media replacement, geometry checks, and visual slide QA. Use for .pptx/.potx/.ppt, presentations, decks, slides, briefings, pitches, reviews, or speaker notes.
---

# PPTX workflows

Use the repository CLI and references:

- `skills/pptx/references/creation-spec.md`
- `skills/pptx/references/edit-plan.md`
- `skills/pptx/references/quality.md`

## Routes

| Task | Route |
|---|---|
| Inspect a deck | `documentctl inspect deck.pptx` |
| Create from scratch | JSON spec → `documentctl pptx-create` |
| Edit an existing deck/template | edit plan → `documentctl pptx-edit` |
| Duplicate/delete/reorder slides | structure plan → `documentctl pptx-structure` |
| Inventory masters/layouts | `documentctl inspect deck.pptx` |
| Validate geometry/content | `documentctl pptx-validate` |
| Visual QA | `documentctl render` → contact sheet → individual slides |
| Legacy `.ppt` | LibreOffice conversion on a copy, then inspect/edit PPTX |

## Creation workflow

```bash
scripts/documentctl pptx-create spec.json draft.pptx \
  --expected-slides 9 --require-notes
scripts/documentctl pptx-validate draft.pptx \
  --expected-slides 9 --require-notes \
  -o .document-work/job/qa.json
scripts/documentctl render draft.pptx -o .document-work/job/render
```

Inspect the contact sheet for narrative rhythm and every slide for text clipping, overlap, contrast, chart labels, table density, image crop, and footer consistency. Correct the spec and rebuild; do not patch a generated deck manually.

## Existing deck workflow

```bash
scripts/documentctl inspect template.pptx -o .document-work/job/input.json
scripts/documentctl pptx-edit template.pptx result.pptx --plan edit-plan.json
scripts/documentctl inspect result.pptx -o .document-work/job/output.json
scripts/documentctl pptx-validate result.pptx -o .document-work/job/qa.json
scripts/documentctl render result.pptx -o .document-work/job/render
```

The editor replaces text across fragmented DrawingML runs while preserving run formatting and untouched package parts. It can include speaker notes and replace an existing media part with a same-format image. Use exact expected counts and optional media hashes.

For structural work, use `pptx-structure` before text edits. It duplicates slides with package registration, deletes/reorders by presentation order, and recursively removes orphaned charts/media/embeddings/notes. Duplicated slides intentionally share chart/media assets and omit notes rather than creating an invalid shared notes slide. Validate template-derived output with `pptx-validate --original template.pptx` so inherited package issues are separated from regressions.

## Design rules

- One claim per slide. The title should state the takeaway, not merely the topic.
- Prefer 3–5 strong visual elements to dense walls of text.
- Use a restrained palette and consistent alignment grid.
- Body text should normally be at least 16–18 pt; labels and sources may be smaller but remain readable.
- Native charts must use comparable units and a visible baseline where interpretation depends on it.
- Avoid mixing percentages and currency on one axis.
- Tables are for lookup and precise comparison; charts are for patterns.
- Use speaker notes for evidence, caveats, and delivery prompts that should not crowd the slide.
- A supplied template is a constraint: replace content and media without redesigning masters, layouts, or unrelated slides.

## Delivery gate

- Package and Open XML validation pass.
- Slide count, required text, titles, notes, charts, tables, and media match the brief.
- No placeholders remain.
- Geometry heuristics report no out-of-bounds shapes or likely text overflow.
- Any overlap warning is visually reviewed and explained.
- LibreOffice-rendered slide count equals PPTX slide count.
- Contact sheet and every dense/suspicious slide have been viewed after the final edit.
- Template edits have only expected changed package parts.
