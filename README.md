# Workspace document system

A clean-room, agent-oriented document platform for safely creating, editing, inspecting, rendering, comparing, and validating complex files in the repository runtime.

## Current capability

End-to-end **DOCX, XLSX, PPTX, and PDF vertical slices** are implemented.

DOCX:

- safe ZIP/OOXML intake and relationship validation;
- semantic extraction with revision views;
- declarative report generation with covers, fields, tables, images, and charts;
- format-preserving placeholder replacement across split Word runs;
- tracked changes and anchored comments;
- package/text/visual diff;
- isolated LibreOffice rendering, PDF rasterization, and contact sheets;
- structural, semantic, business-rule, optional Open XML SDK, and visual QA;
- repository Skills, tests, examples, and CI.

XLSX adds declarative dashboards/models, native tables and charts, preservation-safe cell/formula edits, calculation-cache inspection, mandatory recalculation gates, and printable-sheet QA.

PPTX adds professional high-level layouts, native charts, speaker notes, split-run-safe text replacement, same-format media replacement, geometry/overflow/overlap checks, and complete slide rendering QA.

PDF adds embedded-font report creation, TOC/outlines, merge/select/rotate/watermark/encryption, AcroForm filling, coordinate overlays, OCR, table extraction, active-content checks, and direct PDFium visual QA.

The common layer adds environment self-tests, schema-validated cross-format workflows with manifests and hashes, concurrent batch processing, generic semantic/package/visual comparison, bounded resource policies, an explicit no-false-fidelity conversion matrix, and stable DOCX paragraph / XLSX cell / PPTX shape / PDF page citations.

Advanced review routes now include DOCX accept/reject plus tracked-completeness proof, XLSX dependency tracing and formula compatibility lint, PPTX structural slide operations and master/layout inventory, PDF form-structure inference, and secure raster redaction. Cross-format brand profiles and claim lineage provide reusable styling plus source-to-deliverable citations.

## Ready-to-view examples

Download the generated [DOCX, XLSX, PPTX, and PDF examples](examples/generated/README.md), or review their rendered contact sheets directly on GitHub.

## Bootstrap

```bash
scripts/bootstrap-documents.sh
scripts/documentctl env
```

Bootstrap installs Python dependencies plus integrity-pinned LibreOffice/Tesseract WASM runtimes and a standalone Microsoft Open XML SDK validator from npm. Native LibreOffice/Tesseract are used when present; WASM is the automatic fallback in restricted Arena sandboxes, so DOCX/XLSX/PPTX rendering, XLSX recalculation, English/Russian OCR, and Microsoft 365 OOXML validation work without APT or host .NET. Use `DOCUMENT_SYSTEM_OFFICE_BACKEND=native|wasm|auto` to select the Office backend explicitly.

## Quick start

Create and validate the example report:

```bash
scripts/documentctl create \
  examples/docx/operational-review.json \
  .document-work/operational-review.docx \
  --require-header --require-footer --require-page-numbers \
  --require-toc --require-images 1
```

Inspect and extract:

```bash
scripts/documentctl inspect .document-work/operational-review.docx \
  -o .document-work/inspection.json
scripts/documentctl extract .document-work/operational-review.docx \
  --format text -o .document-work/content.txt
```

Apply a tracked edit with a comment:

```bash
scripts/documentctl edit \
  .document-work/operational-review.docx \
  .document-work/operational-review-redlined.docx \
  --plan examples/docx/review-plan.json
```

Render and visually review:

```bash
scripts/documentctl render .document-work/operational-review.docx \
  -o .document-work/render
```

Create and evaluate an Excel dashboard:

```bash
scripts/documentctl xlsx-create \
  examples/xlsx/operational-dashboard.json \
  .document-work/operational-dashboard.xlsx \
  --require-sheet Панель --require-sheet Данные --require-formulas
scripts/documentctl xlsx-edit \
  .document-work/operational-dashboard.xlsx \
  .document-work/operational-dashboard-scenario.xlsx \
  --plan examples/xlsx/scenario-update.json
scripts/run-xlsx-evals.sh
```

Create and evaluate a presentation:

```bash
scripts/documentctl pptx-create \
  examples/pptx/operational-review.json \
  .document-work/operational-review.pptx \
  --expected-slides 9 --require-notes
scripts/documentctl pptx-edit \
  .document-work/operational-review.pptx \
  .document-work/operational-review-updated.pptx \
  --plan examples/pptx/review-plan.json
scripts/run-pptx-evals.sh
```

Create and evaluate a PDF report:

```bash
scripts/documentctl pdf-create \
  examples/pdf/operational-report.json \
  .document-work/operational-report.pdf \
  --render --render-dir .document-work/pdf-render
scripts/run-pdf-evals.sh
```

Run a recorded cross-format workflow or concurrent batch:

```bash
scripts/documentctl doctor --self-test
scripts/documentctl workflow examples/workflows/document-suite.json \
  --work-dir .document-work/jobs/document-suite
scripts/documentctl batch incoming/ --recursive --action validate --workers 4 \
  -o .document-work/batch
```

Run all complete evaluations:

```bash
scripts/run-docx-evals.sh
scripts/run-xlsx-evals.sh
scripts/run-pptx-evals.sh
scripts/run-pdf-evals.sh
scripts/run-system-evals.sh
```

## Agent entry points

- [`AGENTS.md`](AGENTS.md) — mandatory repository behavior for document requests.
- [`skills/documents/SKILL.md`](skills/documents/SKILL.md) — format/operation router.
- [`skills/docx/SKILL.md`](skills/docx/SKILL.md) — DOCX workflows and gates.
- [`skills/xlsx/SKILL.md`](skills/xlsx/SKILL.md) — XLSX modeling, recalculation, and QA.
- [`skills/pptx/SKILL.md`](skills/pptx/SKILL.md) — PPTX authoring, editing, and slide QA.
- [`skills/pdf/SKILL.md`](skills/pdf/SKILL.md) — PDF creation, forms, transforms, OCR, and QA.

## Documentation

- [Implemented architecture](docs/architecture/document-system.md)
- [Cross-format orchestration](docs/architecture/orchestration.md)
- [LibreOffice and Tesseract WASM runtime](docs/architecture/wasm-runtime.md)
- [Optional Microsoft Office oracle](docs/architecture/microsoft-oracle.md)
- [GitHub Actions CI workflow template](docs/ci/README.md)
- [Claude parity gap analysis](docs/research/claude-parity-gap-analysis-2026-08-20.md)
- [Parity benchmark](benchmarks/document-parity/README.md)
- [Initial landscape research](docs/research/document-system-research-2026-08-20.md)
- [DOCX creation specification](skills/docx/references/creation-spec.md)
- [DOCX edit plans](skills/docx/references/edit-plan.md)
- [DOCX quality checklist](skills/docx/references/quality.md)
- [XLSX creation specification](skills/xlsx/references/creation-spec.md)
- [XLSX edit plans](skills/xlsx/references/edit-plan.md)
- [XLSX quality checklist](skills/xlsx/references/quality.md)
- [PPTX creation specification](skills/pptx/references/creation-spec.md)
- [PPTX edit plans](skills/pptx/references/edit-plan.md)
- [PPTX quality checklist](skills/pptx/references/quality.md)
- [PDF creation specification](skills/pdf/references/creation-spec.md)
- [PDF forms and overlays](skills/pdf/references/forms-and-overlays.md)
- [PDF quality checklist](skills/pdf/references/quality.md)

## Proprietary research artifact

`docx.zip` is retained only because it was supplied by the repository owner for comparison. Its Moonshot AI license prohibits reproduction, modification, and redistribution outside Moonshot services; its native modules target a different Python runtime. The production system does not import, execute, unpack, or derive code from it.
