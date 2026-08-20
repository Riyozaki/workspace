# Document system architecture

## Status

Production-oriented vertical slices are implemented for DOCX, XLSX, PPTX, and PDF.

DOCX provides:

- safe ZIP/OOXML intake;
- package and relationship inspection;
- semantic extraction with accepted/rejected/all revision views;
- declarative report creation;
- split-run-safe template replacement;
- minimal tracked changes and anchored comments;
- package/text/optional visual diff;
- isolated LibreOffice conversion wrapper;
- PDF rasterization and contact sheets;
- package, semantic, business-rule, revision/comment, optional Open XML SDK, and optional render QA;
- CLI, Skills, examples, unit tests, and an end-to-end evaluation script.

XLSX additionally provides declarative dashboards/models, native tables and charts, direct preservation-safe cell/formula edits, cached-value/error inspection, and isolated LibreOffice recalculation. PPTX adds tested 16:9 layouts, editable native charts, speaker notes, preservation-safe DrawingML text/media replacement, and geometry/overflow/overlap QA. PDF adds Unicode report authoring, page transformations, form filling, bounded overlays, OCR, table extraction, active-content detection, and native PDFium visual QA.

## Design goals

1. **Preserve fidelity by default.** Existing packages are patched minimally; untouched ZIP members remain byte-identical.
2. **Fail closed.** Unsafe archives, missing targets, mismatched replacement counts, unsupported run boundaries, and unavailable required QA gates stop the workflow.
3. **Separate flexible and deterministic work.** The agent decides content and intent; deterministic code performs package operations and validation.
4. **Make quality observable.** Every gate emits machine-readable JSON.
5. **Remain useful across agent vendors.** Repository Skills are plain files, while `AGENTS.md` supplies the universal entry point.
6. **Avoid proprietary runtime code.** The implementation does not import or execute the bundled Kimi archive or copy Anthropic document Skill sources.

## Components

```text
AGENTS.md / skills/
        │
        ▼
 scripts/documentctl
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ CLI: inspect extract create edit render validate diff       │
├─────────────────────────────────────────────────────────────┤
│ safety │ OPC │ DOCX extract/rules │ builder │ patch editor │
├─────────────────────────────────────────────────────────────┤
│ LibreOffice worker │ PDFium raster │ contact sheets         │
├─────────────────────────────────────────────────────────────┤
│ package QA │ semantic QA │ SDK schema QA │ visual QA        │
└─────────────────────────────────────────────────────────────┘
```

## Trust boundaries

### Input documents

Every input is untrusted. Archive checks run before XML access:

- path traversal, absolute paths, symlinks, duplicate names;
- encrypted entries;
- per-entry and total expansion limits;
- suspicious compression ratios;
- CRC failures;
- DTD/entity declarations and malformed XML.

Macros, embedded objects, hyperlinks, remote resources, and attached templates are inventoried. None is executed.

### Office renderers

The compatibility layer selects one of two backends:

1. native LibreOffice, when `soffice` is present;
2. pinned LibreOffice WASM (`@matbee/libreoffice-converter@2.7.2`) otherwise.

Native LibreOffice runs with a unique disposable profile, macro security level 3, isolated HOME/TMPDIR, headless SVP backend, process-group timeout, and staged inputs/outputs. The WASM backend runs LibreOfficeKit inside an isolated WebAssembly filesystem, has no host filesystem/network access beyond the explicit input/output buffers, and is integrity-pinned by `package-lock.json`.

Both backends feed the same PDFium raster/contact-sheet QA. `DOCUMENT_SYSTEM_OFFICE_BACKEND=native|wasm|auto` can select a backend explicitly.

### Model behavior

Text inside documents is data, not instructions. Skills tell agents not to follow embedded prompts, links, scripts, or macros. Deterministic scripts reject operations beyond their safe capability instead of asking the model to improvise raw OOXML.

## DOCX creation route

The model writes a JSON document specification validated by JSON Schema. The builder provides:

- A4/Letter and orientation/margins;
- restrained themes and language metadata;
- cover, header, footer, PAGE and TOC fields;
- real heading/list styles;
- paragraphs with rich runs and hyperlinks;
- tables with widths, repeated headers, anti-split rows, cell margins, borders, and zebra shading;
- callouts, images, captions, page breaks;
- deterministic bar/line/pie chart images.

The current chart route creates high-resolution images. Native editable Office charts are intentionally not claimed.

## DOCX editing route

An edit plan is validated by JSON Schema and applied in memory. Output is written only after every operation succeeds.

Visible text may span multiple Word runs. The editor constructs a character map over editable runs, finds ranges, and rebuilds only affected runs while preserving run properties. It refuses to cross drawings, fields, revision containers, or incompatible nested parents.

Tracked replacement emits minimal `w:del` and `w:ins` ranges with IDs, author, and UTC date. Deleted text uses `w:delText`. Revision tracking is enabled in settings.

Comments receive:

- a `comments.xml` entry;
- content-type override;
- main-document relationship;
- `commentRangeStart`, `commentRangeEnd`, and `commentReference` anchors.

A `before` comment phase lets a comment wrap an original range that is subsequently redlined. Accept/reject routes collapse revision markup into clean views, including deleted paragraph marks. A tracked-completeness proof compares the original visible stories to the reviewed document with every revision rejected; any mismatch is an untracked-text defect.

## XLSX creation and editing routes

The XLSX builder consumes a JSON Schema-validated workbook specification and creates:

- styled input, formula, numeric, title, header, note, and status cells;
- multiple visible/hidden sheets with dimensions, freeze panes, and print settings;
- native Excel tables, charts, conditional formats, comments, hyperlinks, and data validations;
- automatic/full-on-load calculation properties;
- explicit source/provenance sheets and editable assumptions.

The XLSX editor patches worksheet XML directly. It resolves worksheet names through workbook relationships, preserves existing style IDs, writes strings as inline strings, rejects non-anchor merged-cell writes and grouped formulas, removes stale calculation chains, and forces recalculation after formula changes. Untouched parts remain byte-identical.

Formula QA reads the workbook twice: once for formula expressions and once for cached results. Missing caches are warnings during drafting and become errors under `--require-recalculated`. LibreOffice recalculation is mandatory before formula-bearing deliverables are treated as final. A formula dependency engine now expands bounded ranges, detects circular chains, traces precedents/dependents with cell citations, and lints functions against the pinned LibreOffice verification route. Recalculation fails closed on external-link workbooks unless explicitly forced.

## PPTX creation and editing routes

The PPTX builder uses a single tested widescreen canvas and high-level layouts: title, section, bullets, two-column comparison, metrics, table, native chart, image, quote, and timeline. Layouts share one theme/grid and support per-slide sources, footers, and speaker notes. Native charts retain their editable embedded workbook.

The PPTX editor resolves slides by presentation order, not XML filenames. It patches visible text and notes across fragmented DrawingML runs while retaining run properties, and can replace a media part only when image format and optional expected hash match. Unrelated masters, layouts, themes, slides, charts, and media remain byte-identical. The structural route inventories masters/layouts, duplicates and registers slides, deletes/reorders by presentation order, recursively removes orphaned charts/media/embeddings/notes/diagrams, and can baseline inherited package warnings against a source template.

PPTX QA inventories slide content and notes, checks required titles/text, detects placeholders and out-of-bounds shapes, estimates text overflow from geometry/font metrics, reports suspicious overlaps and small text, and requires rendered slide count to match package slide count.

## PDF creation, transformation, and forms

The PDF builder uses ReportLab with embedded Unicode fonts, deterministic styles, outlines, repeated table headers, and a multi-pass TOC. PDFium provides direct rendering in the restricted runtime, so PDF visual QA does not depend on LibreOffice.

Page transformations use pypdf for merge/select, rotation, watermarking, metadata, and AES-256 encryption. AcroForm filling verifies field names before writing. Non-fillable forms use top-left point coordinates with page-bound checks for text, checkmarks, rectangles, and images. OCR selects native Tesseract when installed or pinned Tesseract.js WASM with bundled English/Russian data otherwise, producing searchable raster PDFs with page-level text statistics.

PDF QA uses strict parsing, page/text/form/font inventory, placeholder and active-content detection, embedded-font checks, table extraction, raster page-count matching, and blank/edge-clipping analysis. Geometric form inference associates vector boxes/lines with nearby labels and produces annotated review images. Secure redaction reconstructs pages from rasterized pixels so original object/text streams and metadata are not retained.

## Validation layers

### 1. Archive and OPC

- ZIP safety and CRC;
- required package parts;
- content types and overrides;
- root officeDocument relationship;
- internal relationship target existence;
- XML `r:id`/`r:embed`/`r:link` declaration checks;
- duplicate relationship and drawing IDs;
- macro, external resource, media, and embedding inventory.

### 2. DOCX business rules

- final section properties placement;
- table cells end in a paragraph;
- balanced fields and bookmarks;
- revision metadata and deleted-text element correctness;
- comment IDs synchronized across anchors and comments part.

### 3. Semantic

- accepted/rejected/all revision extraction;
- expected and forbidden text;
- unresolved placeholders;
- headers, footers, media, TOC and PAGE requirements;
- styles, comments, fields, story parts, and document statistics.

### 4. Microsoft Open XML SDK

`@xarsh/ooxml-validator@0.3.0` supplies an integrity-pinned standalone Linux binary containing Microsoft Open XML SDK validation for Microsoft 365. No host .NET installation is required. A local .NET project remains as a source-level fallback. `--require-openxml-sdk` makes this a hard gate.

Integrating the real SDK exposed and fixed previously invisible defects: DOCX property/edge ordering and on/off enums, XLSX font child ordering, and signed/overflowing PowerPoint chart axis IDs.

### 5. Render and visual

With native LibreOffice or the pinned WASM fallback:

1. isolated Office conversion to PDF;
2. PDFium rasterization;
3. page metrics and blank/edge-clipping heuristics;
4. labeled contact sheets;
5. agent visual inspection and rerender after fixes.

LibreOffice remains a compatibility smoke test, not proof of identical Microsoft Word rendering.

## Cross-format orchestration and concurrency

`documentctl workflow` executes schema-validated, non-shell steps across all four formats and writes a durable manifest with environment, resolved paths, per-step reports, timestamps, output hashes, and failure evidence. `${step.output}` references connect steps without relying on implicit filesystem state.

`documentctl batch` concurrently inspects, validates, or renders file collections with bounded workers and deterministic result ordering. `documentctl compare` provides one semantic/package/visual diff interface across DOCX/XLSX/PPTX/PDF. `documentctl convert` exposes only conversions with an honest fidelity model and rejects PDF-to-Office reconstruction.

See [`docs/architecture/orchestration.md`](orchestration.md) for the operational contract.

## Reproducibility

- Python dependency ranges live in `pyproject.toml` and exact hashes in `requirements.lock`.
- LibreOffice WASM and Tesseract.js with English/Russian data are pinned in `package.json`/`package-lock.json`; runtime binaries remain outside Git in `node_modules`.
- The Open XML SDK package version is pinned in its project.
- Runtime-generated environments and documents are excluded from Git.
- `scripts/bootstrap-documents.sh` installs system dependencies where package mirrors are reachable and always builds the repository-local Python environment.
- Integration rendering is exercised in GitHub Actions, even if a restricted interactive sandbox cannot reach Debian mirrors.

## Known limits of the first slice

- No Microsoft Word rendering oracle.
- Microsoft Office-native rendering is still unavailable; LibreOffice WASM now makes Linux visual QA and XLSX recalculation always available after `npm ci`.
- No native editable Word charts yet.
- No content controls, replies to modern threaded comments, SmartArt editing, equation authoring, or arbitrary field mutation.
- DOCX replacement intentionally refuses text crossing hyperlinks or complex runs.
- PPTX creation currently targets a tested 16:9 canvas; master/layout redesign, animations, comments, and chart-data edits need dedicated routes.
- PDF creation does not yet claim PDF/A conformance; AcroForm filling remains interactive rather than flattened, and OCR output is a searchable raster reconstruction.
- LibreOffice and Microsoft Office may render fields, pagination, charts, fonts, and tracked changes differently.

These are explicit capability boundaries and candidates for benchmark-driven expansion, not hidden failure modes.
