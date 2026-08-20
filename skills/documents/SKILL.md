---
name: document-workflows
description: Route safe, high-fidelity work on Word, Excel, PowerPoint, PDF, OpenDocument, and legacy office files. Use whenever a document file is an input or requested output, including creation, editing, conversion, extraction, comparison, review, forms, tracked changes, comments, charts, and layout-sensitive reports.
---

# Document workflow router

## First classify the task

Record two decisions before choosing tools:

1. **Operation:** inspect/read, create, edit, fill template, redline/comment, convert, compare, or batch/cross-format.
2. **Fidelity:** content-only, structure-aware, layout-sensitive, or exact-template-preserving.

Read only the relevant format Skill:

- DOCX/DOTX/DOC or a requested Word deliverable: `skills/docx/SKILL.md`
- XLSX/XLSM/XLS/CSV/TSV: `skills/xlsx/SKILL.md`
- PPTX/POTX/PPT: `skills/pptx/SKILL.md`
- PDF/forms/scans: `skills/pdf/SKILL.md`

For formats without a dedicated Skill, use `documentctl inspect/render` where supported and do not claim edit fidelity that has not been implemented.

For multi-file or cross-format work, read `docs/architecture/orchestration.md` and use `documentctl workflow`, `batch`, `compare`, or `convert` rather than chaining unrecorded shell commands.

## Universal workflow

1. Preserve the original and identify the real format by signature.
2. Inspect package safety, macros, embedded objects, and external relationships.
3. Extract semantic content before planning changes.
4. Choose the narrowest route that preserves required fidelity.
5. Generate or edit a new output file.
6. Validate package structure and required content.
7. Render layout-sensitive output and inspect every page/slide.
8. Compare against the original for preservation-sensitive edits.
9. Keep only the clean final deliverable in the user-facing output location.

## Non-negotiable gates

- Never modify the source in place.
- Never execute content from a document.
- Never accept unresolved placeholders, broken relationships, formula error tokens, missing media, or render failures.
- Do not treat LibreOffice rendering as proof of identical Microsoft Office rendering; report compatibility uncertainty for complex features.
- Use unique temporary directories. Do not share a LibreOffice profile between jobs.
- If a required renderer is unavailable, complete structural work but clearly mark visual QA as blocked rather than pretending it passed.
