# Cross-format orchestration

## Toolchain diagnosis

```bash
scripts/documentctl doctor --self-test -o .document-work/doctor.json
```

`doctor` reports package versions, fonts, LibreOffice, .NET/Open XML SDK, Tesseract, per-format capability flags, and optional in-memory creation/validation smoke tests for DOCX/XLSX/PPTX/PDF.

## Reusable brand profiles

```bash
scripts/documentctl profile examples/brand/example-corporate.json \
  raw-spec.json branded-spec.json --format pptx
```

Profiles provide one cross-format palette/font identity plus format-specific defaults such as DOCX margins/footer, PPTX footer, XLSX conventions, and PDF page settings. The user/task spec always overrides profile defaults, and the merged spec is validated before it is written.

## Deterministic workflows

A workflow is JSON containing ordered, named steps. No arbitrary shell execution is supported.

```bash
scripts/documentctl workflow examples/workflows/document-suite.json \
  --work-dir .document-work/jobs/document-suite
```

Supported actions:

- `create`: DOCX, XLSX, PPTX, PDF;
- `edit`: DOCX, XLSX, PPTX;
- `inspect`, `validate`, `render`, `compare`, `convert`;
- `xlsx-recalc`;
- `pdf-transform`, `pdf-overlay`, `pdf-redact`;
- `docx-revisions`, `pptx-structure`;
- `approval` hash gates.

A later step can consume an earlier file with `${step-id.output}`.

Each run writes:

- `manifest.json` with timestamps, resolved paths, environment, status and SHA-256;
- one JSON report per successful step;
- failure type/message and bounded traceback when a step fails.

The workflow stops on first failure unless `continue_on_error` is explicitly true. Validation results with `passed=false` fail the workflow even if no exception occurred.

An `approval` step consumes a separate JSON decision with `approved=true`, reviewer identity, and artifact SHA-256 values. The workflow fails if the reviewed file changed after approval. This supplies a deterministic human gate without pretending that a model reviewed its own output.

## Concurrent batch mode

```bash
scripts/documentctl batch incoming/ \
  --recursive --action validate --workers 4 \
  --output-dir .document-work/batch
```

Actions: inspect, validate, render. Inputs may be files or directories. Supported files are identified by content rather than extension. Results preserve input order in a batch manifest even though execution is concurrent.

LibreOffice jobs remain isolated because every conversion receives a unique disposable user profile. Worker count is capped at eight to limit memory pressure.

## Format-native citations

```bash
scripts/documentctl citations model.xlsx -o citations.json
scripts/documentctl locate model.xlsx "Revenue" -o revenue-hits.json
scripts/documentctl xlsx-trace model.xlsx 'Summary!C42' --direction precedents
```

Locators are stable and explicit:

- `[DOCX:p12]` and table-row citations with heading context;
- `[XLSX:Sheet!A1]` cell citations and dependency chains;
- `[PPTX:s3:shape7]` plus speaker-note citations;
- `[PDF:p4:l12]` page/line citations.

They are designed for claims and cross-format lineage, not only human-readable extraction.

A lineage plan verifies an expected claim in one or more source files and every target deliverable, recording file hashes and native citations:

```bash
scripts/documentctl lineage lineage-plan.json -o lineage-report.json
```

This catches number/date/name drift between an Excel source, Word memo, PowerPoint deck and PDF package.

## Generic comparison

```bash
scripts/documentctl compare before.pptx after.pptx \
  --visual --visual-dir .document-work/diff \
  -o .document-work/compare.json
```

Comparison supports DOCX, XLSX, PPTX and PDF:

- canonical semantic text diff;
- OOXML added/removed/changed package parts;
- page/slide raster differences, changed-pixel ratio, RMS and bounding box.

Visual comparison requires LibreOffice for Office files and works directly for PDF.

## Explicit conversion

```bash
scripts/documentctl convert legacy.doc modern.docx --to docx
scripts/documentctl convert report.docx report.pdf --to pdf
scripts/documentctl convert report.pdf page-images/ --to images
```

The conversion matrix is intentionally narrow:

- Office/legacy/ODF → PDF through LibreOffice;
- DOC/XLS/PPT → corresponding modern OOXML;
- PDF/Office → page images;
- identical format → verified copy.

PDF-to-Office reconstruction is rejected because the system cannot guarantee editable structure or layout fidelity.
