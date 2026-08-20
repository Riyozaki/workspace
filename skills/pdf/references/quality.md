# PDF quality checklist

## Parse and safety

- Strict parser opens the document.
- Encryption state is known.
- Page count and dimensions are valid.
- JavaScript, OpenAction, Launch, embedded files, RichMedia, and XFA are absent unless explicitly accepted.
- Required fonts are embedded; standard 14 fonts are the only normal exception.

## Content

- Required text appears in extracted text.
- No TODO/TBD/template placeholders remain.
- Metadata is intentional.
- Tables extract with plausible rows and columns.
- Links and annotations are expected.
- OCR text is checked against visible scans and language is correct.

## Forms and overlays

- Field names come from the actual AcroForm.
- Checkboxes use the field's valid export value.
- Every value appears visually after filling.
- Overlay coordinates are measured from rendered pages, not guessed.
- Text fits its box and does not cover labels.
- Signatures/images retain aspect ratio and adequate resolution.

## Visual review

PDFium rendering is the primary visual QA route:

1. confirm rendered page count;
2. inspect contact sheet for blank/duplicate pages and inconsistent rhythm;
3. inspect dense pages and all overlays individually;
4. check edge clipping, table splits, chart labels, footers, page numbers, and font rendering;
5. regenerate and rerender after every change.

A PDF that parses but has misplaced content is a failed deliverable.
