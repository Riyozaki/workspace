# PDF forms, overlays, and transformations

## Interactive AcroForm

Extract exact field names:

```bash
scripts/documentctl pdf-extract form.pdf -o fields.json
```

Fill a JSON object:

```json
{
  "legal_name": "Northern Systems LLC",
  "approved": "/Yes"
}
```

```bash
scripts/documentctl pdf-fill form.pdf filled.pdf --values values.json
```

Unknown fields stop the operation. The implementation preserves the AcroForm and updates appearances without claiming to flatten it.

## Infer a non-fillable form

```bash
scripts/documentctl pdf-form-structure flat-form.pdf \
  -o field-candidates.json \
  --image-dir field-review/
```

The detector combines vector rectangles/horizontal lines with nearby text labels and emits top-left point coordinates, confidence, and annotated page images. Candidates are never filled automatically: review and curate them into an overlay plan.

## Non-fillable overlay

Coordinates are PDF points measured from the **top-left**. One inch is 72 points.

```json
{
  "items": [
    {
      "page": 1,
      "type": "text",
      "x": 120,
      "y": 210,
      "width": 240,
      "height": 20,
      "text": "Northern Systems LLC",
      "font_size": 10
    },
    {
      "page": 1,
      "type": "check",
      "x": 120,
      "y": 260,
      "width": 14,
      "height": 14,
      "color": "26734D"
    }
  ]
}
```

Supported overlay types: text, check, rectangle, image. Every bounding box must fit inside the page.

## Merge/select/rotate/watermark

```json
{
  "inputs": [
    {"path": "cover.pdf", "pages": "1"},
    {"path": "report.pdf", "pages": "1-5,8"}
  ],
  "rotate": [{"pages": "2", "degrees": 90}],
  "watermark": {
    "text": "DRAFT",
    "font_size": 48,
    "color": "808080",
    "opacity": 0.15,
    "angle": 35
  },
  "metadata": {"title": "Combined report"}
}
```

Passwords may be passed in temporary plans but must never be committed. AES-256 output encryption is supported.

## Secure redaction

`pdf-redact` rasterizes each page, paints reviewed top-left rectangles, and constructs a new image-only PDF. Original text, images, metadata and object streams are not copied. This is deliberately more destructive than a cosmetic overlay.

```json
{
  "dpi": 300,
  "rectangles": [
    {"page": 1, "x": 90, "y": 130, "width": 170, "height": 30}
  ],
  "verify_absent": ["SECRET", "account 1234"]
}
```

The output still requires visual review and, when Tesseract is available, OCR verification that each intended secret is covered.
