---
name: docx-workflows
license: Internal clean-room implementation; see repository dependency licenses.
description: Create, inspect, extract, edit, template-fill, redline, comment, compare, render, and validate Word DOCX files while preserving package fidelity. Use for any Word document, .docx/.dotx/.doc input, report/memo/contract output, tracked changes, comments, page layout, headers, footers, tables, charts, or template work.
---

# DOCX workflows

Use the repository CLI through `scripts/documentctl`. Its source is auditable and tests cover package safety, split-run replacement, comments, revisions, semantic extraction, and declarative creation.

## Route table

| Task | Route |
|---|---|
| Inspect/read | `documentctl inspect` and `documentctl extract` |
| Create from scratch | JSON spec → `documentctl create` |
| Fill placeholders | edit plan with untracked replacements |
| Edit someone else's formal document | edit plan with tracked replacements |
| Add review comments | edit plan `comments` entries |
| Compare | `documentctl diff`; add `--visual` when rendering exists |
| Prove every visible edit is tracked | `documentctl docx-tracked-check original.docx reviewed.docx` |
| Produce clean accepted/rejected copy | `documentctl docx-revisions --mode accept|reject` |
| Legacy `.doc` | convert a copy through LibreOffice, then inspect the DOCX |
| Layout QA | `documentctl render`, inspect contact sheet and every suspicious page |

Detailed authoring and editing contracts:

- `skills/docx/references/creation-spec.md`
- `skills/docx/references/edit-plan.md`
- `skills/docx/references/quality.md`

## Required sequence

### Existing DOCX

```bash
scripts/documentctl inspect input.docx -o .document-work/job/input-inspection.json
scripts/documentctl extract input.docx --format json -o .document-work/job/input-content.json
# Create and apply an edit plan; never edit input.docx itself.
scripts/documentctl edit input.docx result.docx --plan .document-work/job/edit-plan.json
scripts/documentctl validate result.docx \
  --forbid-text '{{' --forbid-text 'TODO' \
  -o .document-work/job/qa.json
scripts/documentctl diff input.docx result.docx -o .document-work/job/diff.json
```

For a layout-sensitive edit, add rendering and visually inspect it. For exact-template-preserving work, review changed package parts from the diff; unexpected changes are defects.

### New DOCX

```bash
scripts/documentctl create .document-work/job/spec.json result.docx \
  --require-footer --require-page-numbers
scripts/documentctl validate result.docx \
  --require-footer --require-page-numbers \
  -o .document-work/job/qa.json
scripts/documentctl render result.docx -o .document-work/job/render
```

Open the contact sheet, then page images. Check typography, hierarchy, page breaks, table wrapping, captions, image quality, headers/footers, empty pages, clipping, and contrast. Correct the spec and rebuild rather than patching a newly generated document by hand.

## Editing principles

- Word often splits visible phrases across runs. The edit engine maps characters across runs; do not use raw XML string replacement.
- Replacements that cross drawings, fields, or hyperlink boundaries stop with an error rather than corrupting content.
- Formal/legal/external documents should default to tracked changes unless the user requests a clean replacement.
- For a redline, run `docx-tracked-check`: rejecting all revisions must reproduce the original visible text. This catches accidental untracked replacements.
- `docx-revisions` supports deterministic accept/reject views, including deleted paragraph marks; validate and visually review the clean output.
- Make the smallest defensible change. Unchanged ZIP members must remain byte-identical.
- Comments require anchored ranges, not merely a `comments.xml` entry.
- Set an explicit expected occurrence count for template placeholders and high-stakes edits.

## Creation principles

- Prefer a supplied template over free design.
- Without a template, choose one restrained visual system based on purpose and audience.
- Use real Word headings, lists, fields, tables, headers, and footers—not lookalike glyphs or manual spacing.
- Charts created by the current vertical slice are high-resolution images. If the user requires editable native Word charts, state that requirement before authoring and use a future Open XML chart route; do not mislabel an image chart as editable.
- TOC and PAGE fields are marked for update on open. Verify their rendered behavior in the target application when exact pagination matters.

## Delivery gate

A DOCX is ready only when:

- package validation has zero errors;
- expected content exists and forbidden text/placeholders do not;
- required media, fields, headers, footers, comments, and revisions are present;
- layout-sensitive work has a completed visual review;
- an edit has no unexplained package-part changes;
- the final filename is meaningful and no iteration clutter is delivered.
