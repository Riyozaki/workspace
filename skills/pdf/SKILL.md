---
name: pdf-workflows
license: Internal clean-room implementation; see repository dependency licenses.
description: Create, inspect, extract, merge, split, select, rotate, watermark, encrypt, fill forms, overlay content, OCR, render, and validate PDF files. Use for PDFs, reports, invoices, forms, scans, signatures, page manipulation, table extraction, bounding boxes, or searchable OCR output.
---

# PDF workflows

Use `scripts/documentctl` and read the relevant reference:

- `skills/pdf/references/creation-spec.md`
- `skills/pdf/references/forms-and-overlays.md`
- `skills/pdf/references/quality.md`

## Routes

| Task | Route |
|---|---|
| Inspect text/forms/fonts/safety | `pdf-extract` or generic `inspect` |
| Create a report | JSON spec → `pdf-create` |
| Merge/select/rotate/watermark/encrypt | plan → `pdf-transform` |
| Fill AcroForm | `pdf-fill --values values.json` |
| Infer non-fillable form fields | `pdf-form-structure` + validation images |
| Non-fillable form / signature / check | `pdf-overlay --plan overlay.json` |
| Verified destructive redaction | `pdf-redact --plan redaction.json` |
| Scanned PDF | `pdf-ocr` with explicit language |
| Validate | `pdf-validate --render` |

## Creation workflow

```bash
scripts/documentctl pdf-create spec.json report.pdf \
  --render --render-dir .document-work/job/render
scripts/documentctl pdf-validate report.pdf \
  --require-text "Executive summary" --render \
  --render-dir .document-work/job/final-render \
  -o .document-work/job/qa.json
```

PDF rendering is available directly through PDFium and does not require LibreOffice. Inspect the contact sheet and every page containing dense tables, charts, small text, overlays, or signatures.

## Form workflow

1. `pdf-extract form.pdf -o fields.json`.
2. If AcroForm fields exist, fill exact names with `pdf-fill`.
3. If fields do not exist, run `pdf-form-structure --image-dir ...`; review inferred labels/boxes on validation images, then use `pdf-overlay`.
4. Render the result and inspect every placed value/check/image.
5. Never guess signature placement or silently flatten an interactive form.

## Safety

- Do not execute JavaScript, launch actions, embedded files, rich media, or XFA content.
- Encrypted inputs require an explicitly supplied password; never store passwords in committed plans.
- Treat OCR text as uncertain data and retain page-level provenance.
- Overlay coordinates use points from the top-left corner; bounds are validated.
- `pdf-redact` uses secure raster reconstruction so original text/object streams are removed. It intentionally sacrifices vector editability; visual and OCR verification remain mandatory.
- Preserve the original PDF and produce a new output.

## Delivery gate

- Strict parser opens every page.
- Required page count and text match.
- No unresolved placeholders or active/embedded risky features.
- Non-standard fonts are embedded.
- Forms contain the intended field values.
- Overlays remain inside page bounds.
- Rendered page count matches parsed page count.
- No unexplained blank pages, clipping, unreadable text, or misplaced marks.
- OCR output is spot-checked against the source image.
