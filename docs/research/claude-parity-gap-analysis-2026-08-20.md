# Gap analysis: current Claude document stack vs. this repository

**Date:** 2026-08-20
**Reference snapshot:** `anthropics/skills@0a64e398ec6bb34a494f0c347e8ccae53a862f8e` (2026-08-18)
**Our runtime:** `documentctl 0.6.0` (the initial comparison began on `0.4.0`)

## Post-analysis implementation update

The first achievable P1 batch identified below has now been implemented:

- DOCX accept/reject revision views and tracked-edit completeness proof;
- XLSX dependency graph, precedent/dependent tracing, stable cell citations, cycle detection and LibreOffice compatibility lint;
- external-link refusal before XLSX recalculation;
- PPTX master/layout inventory, duplicate/delete/reorder operations, recursive orphan cleanup and template-baseline package QA;
- PDF geometric form-field inference with annotated validation images;
- secure raster redaction that removes original object/text streams;
- cross-format paragraph/cell/shape/page citation indexes and text location;
- hash-bound human approval gates for workflows;
- reusable cross-format brand profiles and explicit claim-lineage verification;
- a pinned LibreOffice WASM runtime fetched through npm, enabling DOCX/XLSX/PPTX rendering and XLSX recalculation directly inside Arena without native packages;
- pinned Tesseract.js English/Russian OCR;
- a self-contained Microsoft Open XML SDK validator binary from npm, eliminating the host .NET dependency;
- an explicit opt-in Microsoft Graph rendering oracle adapter with temporary upload, cleanup, and LibreOffice-vs-Microsoft visual diff.

The advanced baseline now contains 64 passing tests with no unavailable local capability path after npm bootstrap, plus all five end-to-end suites. LibreOffice rendering/recalculation, English/Russian OCR, and Microsoft 365 Open XML SDK validation all execute in the interactive runtime. Live Microsoft rendering remains disabled until an approved delegated token and Graph network access are supplied.

The remaining matrix is retained as the decision record. Items above should now be treated as **implemented but awaiting real Microsoft Office/external-fixture validation**, rather than absent.

## Executive conclusion

There are now three different targets hidden behind “Claude’s document capability”:

1. **Claude.ai / Claude API built-in document Skills** — filesystem/code-execution pipelines for DOCX/XLSX/PPTX/PDF.
2. **Claude for Microsoft 365 add-ins** — native, interactive editing inside open Excel, PowerPoint, and Word files.
3. **Claude’s reasoning and vision loop** — content synthesis, source interpretation, narrative choices, and visual review.

Against the **hosted built-in Skills**, this repository is already broadly comparable and exceeds them in several platform qualities: explicit schemas, manifests, hashes, untrusted-package protection, deterministic plans, cross-format workflows, concurrent batch processing, generic comparison, and direct PDF QA.

Against the **current M365 add-ins**, parity is not yet reached. The decisive gap is not prompt quality or OOXML syntax; it is access to the native Office object model and renderer:

- Excel cell citations, dependency tracing, pivot edits, and immediate native recalculation;
- PowerPoint slide-master/layout awareness and native structural editing;
- Word’s full tracked-change/comment-thread model, semantic navigation, numbering and cross-reference awareness;
- native application undo/review UX.

The shortest path to “Claude level and above” is therefore **not another generic document generator**. It is:

1. prove the existing runtime on real Microsoft Office files;
2. add native-compatible template/editing routes and stronger semantic citations;
3. establish benchmarked visual and preservation fidelity;
4. optionally add a Microsoft Office compatibility worker rather than trying to emulate all of Office in Linux.

## 1. What was compared

### 1.1 Hosted Anthropic document Skills

The current public reference contains:

| Skill | SKILL.md | Supporting implementation |
|---|---:|---|
| DOCX | 91 lines | merge-runs, modern comments/replies, accept tracked changes, XSD/relationship validation, LibreOffice wrapper |
| XLSX | 99 lines | LibreOffice recalculation and formula-error reporting, OOXML validation |
| PPTX | 238 lines | slide duplication, orphan cleanup, thumbnails, OOXML/chart validation, LibreOffice wrapper |
| PDF | 314 lines | form inspection/filling, annotation overlays, bounding-box checks, image conversion |

Anthropic explicitly states that these four Skills power its production document capability, but are source-available rather than open source.

### 1.2 Claude for M365

Official current product documentation describes:

- **Excel:** read/write cells, formulas, formatting, pivot tables and charts; cell-level citations; dependency-preserving assumption edits; multi-tab model analysis; error root-cause tracing.
- **PowerPoint:** read/edit/generate slides using the active deck’s master, layouts, fonts and colors; native editable charts and diagrams; targeted slide edits.
- **Word:** whole-document reading; selected-text editing with formatting preservation; native tracked changes; comment-driven editing; counterparty redline summaries; template fill; semantic navigation.
- **Cross-app:** shared context between currently open Excel, PowerPoint, Word and Outlook sessions.

Official limitations remain substantial: human review is required, Excel data tables/macros/VBA are unsupported, Office add-ins only access currently open files, and the add-ins cannot create/open/close/switch files themselves.

### 1.3 Initial repository baseline

Capabilities at the time of the initial comparison (before the post-analysis implementation update above):

- 4 format Skills plus a cross-format router;
- safe ZIP/XML/PDF intake;
- declarative creation for DOCX/XLSX/PPTX/PDF;
- preservation-aware edits;
- schema/business/semantic/visual QA;
- Open XML SDK adapter;
- LibreOffice adapter;
- PDFium visual pipeline;
- Tesseract adapter;
- workflow manifests and SHA-256 provenance;
- concurrent batch operations;
- semantic/package/visual comparison;
- explicit conversion matrix;
- 45 passing tests and 78% measured code coverage;
- all-format deterministic self-test and regression evaluation.

## 2. Capability matrix

Legend:

- **Ahead** — repository capability is materially stronger or more auditable.
- **Parity candidate** — implemented, but Microsoft Office or external benchmark evidence is still required.
- **Partial** — useful implementation exists but misses current Claude behavior.
- **Gap** — no equivalent route exists.

### 2.1 Platform and execution

| Capability | Hosted Skills | M365 Claude | Repository | Status |
|---|---|---|---|---|
| Automatic format routing | Yes | Native app context | AGENTS + document router | Parity candidate |
| Progressive disclosure | Yes | Skills apply in app | Separate compact Skills/references | Parity candidate |
| Deterministic scripts | Yes | Hidden add-in operations | Yes | Parity candidate |
| Untrusted ZIP/XML checks | Partial | Product sandbox | Explicit path/symlink/ratio/DTD/collision policy | **Ahead** |
| Per-step manifest and hashes | No public equivalent | Native change UX, no repo manifest | Yes | **Ahead** |
| Concurrent batch collections | Not in public Skills | Open files only | Yes, bounded workers | **Ahead** |
| Cross-format filesystem workflow | Conversational | Open apps only | Schema-validated workflow | **Ahead** |
| Persistent/replayable execution plan | Container/session dependent | Local add-in chat | JSON workflow + reports | **Ahead** |
| Native Office object model | No | Yes | No | **Gap** |
| Native Office undo/review UX | No | Yes | File-level outputs/diffs | **Gap** |
| Microsoft renderer | No; LibreOffice | Yes | No; Microsoft Office unavailable | **Gap** |
| LibreOffice renderer in Arena | Managed by Anthropic | N/A | Native adapter + pinned WASM fallback | **Implemented** |
| Runtime available in this Arena sandbox | Managed by Anthropic | Requires M365 | Python + LibreOffice WASM + Tesseract.js + standalone Open XML SDK | **Parity candidate** |

### 2.2 DOCX / Word

| Capability | Claude reference/current product | Repository | Status |
|---|---|---|---|
| New polished report | docx-js + visual QA | Declarative builder + QA | Parity candidate |
| Exact split-run text replacement | merge-runs/direct OOXML | Character-mapped run replacement | Parity candidate |
| Minimal tracked insert/delete | Yes | Yes | Parity candidate |
| Validate untracked edits against original | Anthropic validator supports `--author` diff | Package/text diff, but no tracked-edit completeness proof | **Partial** |
| Accept all tracked changes | LibreOffice helper | Missing | **Gap** |
| Reject tracked changes | Not prominent in public Skill | Missing | Gap for full review lifecycle |
| Modern threaded comments/replies | Six synchronized parts + parent replies | Basic comments only | **Gap** |
| Resolve/reopen/delete comments | M365 thread workflow | Missing | **Gap** |
| Whole-document citations | Word add-in clickable section citations | Extracted structure, no citation protocol | **Gap** |
| Footnotes/endnotes/bookmarks read | Word add-in reads them | Extracted/inventoried | Partial parity |
| Footnotes/endnotes creation/editing | Native Word | Missing | **Gap** |
| Legal numbering/cross-reference QA | Word add-in scans inconsistency | Only package/business checks | **Gap** |
| Content controls / fields / mail merge | Native Word can preserve/use open document | No dedicated route | **Gap** |
| Equations, columns, floating shapes | Native Word | No authoring route | **Gap** |
| Template style inheritance | Word add-in active template | Minimal direct patch, no template composition engine | **Partial** |
| Macro-enabled DOCM preservation | Word add-in supports open document | Not claimed | **Gap** |

### 2.3 XLSX / Excel

| Capability | Claude reference/current product | Repository | Status |
|---|---|---|---|
| New models/tables/charts | Yes | Yes | Parity candidate |
| Formula/value dual read | Yes | Yes | Parity candidate |
| Recalculation gate | Strong `recalc.py` | Implemented and runnable through LibreOffice WASM | Parity candidate |
| Formula error inventory | Detailed JSON, up to 100 locations/type | Detailed inventory | Parity candidate |
| Formula compatibility rules | Explicit LO function allow/deny guidance | Only separator/external/#REF checks | **Gap** |
| Formula correctness beyond evaluation | Manual sample guidance | No dependency/proof engine | **Gap** |
| Cell-level citations | Excel add-in | Sheet/cell inventory, no answer citation protocol | **Partial** |
| Dependency tracing/root cause | Excel add-in | Missing formula dependency graph | **Gap** |
| Existing model convention discovery | Add-in/native context | Styles inventoried, no semantic input/formula classifier | **Partial** |
| Safe assumption edits | Add-in preserves dependencies | Expected-value atomic XML edits | Parity candidate |
| Pivot-table editing | Current Excel add-in | Missing | **Gap** |
| Chart editing | Current Excel add-in | Creation only; no direct chart edit route | **Gap** |
| Conditional format/data validation edit | Current Excel add-in | Creation only | **Partial** |
| Sort/filter native operations | Current Excel add-in | No dedicated edit operation | **Gap** |
| Named ranges and formulas | Native Excel | Inventory only | **Gap** |
| External link preservation guard | Strong refusal/cached-value guidance | Warning only | **Gap** |
| XLSM macro preservation | Add-in can open XLSM but not modify VBA | Not claimed | Gap; neither handles VBA logic fully |
| Data tables / VBA | Officially unsupported | Unsupported | Equal limitation |
| Large CSV/TSV cleanup | Hosted Skill + pandas | Pandas installed, no deterministic CSV adapter | **Gap** |

### 2.4 PPTX / PowerPoint

| Capability | Claude reference/current product | Repository | Status |
|---|---|---|---|
| New editable deck | PptxGenJS/native add-in | Python-pptx high-level layouts | Parity candidate |
| Native charts | Yes | Yes | Parity candidate |
| Speaker notes | Yes | Yes | Parity candidate |
| Template thumbnail/layout mapping | Public Skill | Content/shape extraction only | **Partial** |
| Read slide master/layout/colors/fonts | PowerPoint add-in | No semantic template inventory | **Gap** |
| Add slide from existing layout | Public `add_slide.py`; native add-in | Missing | **Gap** |
| Duplicate/reorder/delete slides | Public Skill | Missing | **Gap** |
| Remove orphaned media/rels | Public `clean.py` | Missing | **Gap** |
| Template-aware new slide generation | PowerPoint add-in | Not implemented | **Gap** |
| Targeted text replacement | Yes | Split-run-safe replacement | Parity candidate |
| Same-format media replacement | Native add-in | Yes | Parity candidate |
| Native chart-data editing | Native add-in | Missing | **Gap** |
| Diagrams / grouped shapes | Native add-in | Timeline/cards only at creation | **Partial** |
| Chart corruption-specific validation | Public validator catches faults generic tools miss | OPC + optional SDK, no PptxGenJS chart fault rules | **Gap** |
| Template baseline validation | Public `--original` suppresses inherited XSD errors | Package diff but no baseline schema-error subtraction | **Gap** |
| Real visual QA | Hosted Skill renders every slide; add-in uses native app | Implemented through LibreOffice WASM + PDFium | Parity candidate |
| Existing graphics understanding | Add-in itself has documented limitations | Structural extraction + optional render/agent vision | Potentially **ahead** once render is always available |
| Animations/transitions/SmartArt/comments | Native app partial | Missing | **Gap** |

### 2.5 PDF

| Capability | Claude reference | Repository | Status |
|---|---|---|---|
| Text/table extraction | Yes | Yes | Parity candidate |
| Report generation | ReportLab | ReportLab + embedded Unicode/TOC/outlines | **Ahead** in deterministic defaults |
| Merge/split/rotate/watermark/encrypt | Yes | Yes | Parity candidate |
| Fill AcroForm | Yes | Yes | Parity candidate |
| Flat annotation overlay | Yes | Bounded top-left overlays | Parity candidate |
| Automatic non-fillable form structure extraction | Dedicated script | Missing | **Gap** |
| Bounding-box validation | Dedicated script | Bounds + visual QA, not label/field collision model | **Partial** |
| Scanned OCR | Generic route | Tesseract route | Parity candidate |
| PDF active-content detection | Not central in public Skill | Explicit JS/OpenAction/Launch/XFA/etc. checks | **Ahead** |
| Font embedding checks | Not central | Yes | **Ahead** |
| Direct PDF visual QA without LO | Images via Poppler | PDFium in current sandbox | **Ahead** |
| Redaction with removal verification | Missing/publicly unclear | Missing | **Gap** |
| Digital signatures | Missing/publicly unclear | Missing | **Gap** |
| Tagged PDF/accessibility | Missing | Missing | **Gap** |
| PDF/A conformance | Missing | Missing | **Gap** |
| Attachments/portfolios | Basic library possible | Safety detection only | **Gap** |
| OCR deskew/rotation/confidence | Basic OCR | Missing | **Gap** |

## 3. Where this repository is already above Claude’s public file Skills

1. **Auditability:** every workflow can produce a manifest, step reports, durations and output hashes.
2. **Safety:** archive traversal, symlinks, duplicate/case-colliding paths, ZIP expansion, XML entities and active PDF content are explicit gates.
3. **Cross-format automation:** workflows can create, edit, validate, render and compare multiple files without requiring them to be manually open in separate applications.
4. **Batch:** bounded concurrent processing of directories is built in.
5. **Comparison:** one semantic/package/visual diff interface spans all four formats.
6. **No false fidelity:** unsupported PDF-to-Office reconstruction is rejected rather than presented as a conversion.
7. **PDF visual availability:** PDFium QA works in the present restricted runtime.
8. **Reproducibility:** dependency hashes, JSON Schemas, clean-room source and tests are repository-owned.
9. **Size:** the system is not constrained by Claude.ai’s 30 MB file output limit; local resource policies are explicit and adjustable.
10. **Replay:** deterministic plans can be rerun and reviewed independently from chat history.

## 4. The true blockers to current Claude parity

### P0 — prove production fidelity

#### 4.1 Always-available Office renderer — resolved with WASM

Native APT/AppImage/OCI downloads are blocked by the Arena egress policy, but the npm registry is available. The repository now pins `@matbee/libreoffice-converter@2.7.2`, which contains a LibreOffice WebAssembly runtime. It renders DOCX/XLSX/PPTX to PDF and recalculates XLSX directly in the interactive sandbox. The native LibreOffice adapter remains preferred when installed; WASM is the automatic fallback.

The remaining concern is renderer diversity: LibreOffice WASM is a real LibreOffice engine, but it is still not Microsoft Office.

#### 4.2 Microsoft Office compatibility oracle

LibreOffice rendering and schema validation do not prove Word/Excel/PowerPoint behavior. Microsoft-specific chart, field, revision, font and layout failures can survive every Linux check.

**Required:** optional native Office worker (Windows VM, Office add-in/test harness, or approved M365 service) for:

- open/save smoke test;
- native PDF export/screenshots;
- formula recalculation;
- document repair warnings;
- per-format feature inspection.

#### 4.3 Real benchmark corpus

Current tests are strong engineering tests but mostly generated fixtures. They do not yet measure fidelity against messy external documents, corporate templates or human quality judgments.

**Required:** licensed benchmark corpus plus blind scoring.

### P1 — native-format feature parity

1. DOCX: modern threaded comments/replies and full revision lifecycle.
2. DOCX: numbering, defined-term and cross-reference analysis with citations.
3. XLSX: dependency graph, cell citations and formula compatibility linter.
4. XLSX: pivot/chart/conditional-format/data-validation edit routes.
5. PPTX: master/layout inventory, slide add/duplicate/reorder/delete and orphan cleanup.
6. PPTX: baseline validation against a supplied template.
7. PDF: automatic form-label/field coordinate inference and collision checks.
8. All formats: reusable brand/template profiles.

### P2 — above-Claude specialization

1. Verified cross-format source lineage: every slide/table/claim traces to source cells/pages.
2. Claim-level fact/citation QA between XLSX → DOCX/PPTX/PDF.
3. Accessibility: tagged PDFs, alt text, reading order, contrast and table headers.
4. Regression visual baselines for corporate templates.
5. Domain packs: legal redlining, financial modeling, board decks, regulatory reports.
6. Scheduled/watch-folder workflows with resumability and idempotency.
7. Human approval gates in workflow manifests.
8. Native Office plus LibreOffice dual-render diffs.

## 5. Recommended implementation order

### Milestone A — runtime proof and benchmark harness

1. Keep the pinned LibreOffice WASM runtime green and add native LibreOffice as a second renderer when available.
2. Keep the standalone Open XML SDK and Tesseract.js gates green; neither now requires a host runtime.
3. Add real-world fixtures for each format.
4. Establish structural, semantic, preservation, editability and visual scores.
5. Record a Claude baseline on exactly the same prompts/files.

This milestone determines whether later feature work improves real quality or only increases feature count.

### Milestone B — template and review parity

- modern DOCX comments/replies + accept/reject;
- PPTX master/layout inventory and structural slide operations;
- XLSX formula dependency/citation engine and compatibility lint;
- PDF form-structure extraction.

### Milestone C — native Office oracle

Define a provider-neutral interface first, then implement a Microsoft Office provider only when an approved runtime is available. The Linux pipeline remains the default; the native worker is a high-confidence compatibility gate.

### Milestone D — above-Claude provenance

Cross-format claim lineage and human approval gates are the clearest defensible advantages over conversational add-ins.

## 6. Benchmark definition for parity

Each test case should grade eight independent dimensions from 0–5:

1. **Semantic correctness** — facts, formulas, requested edits.
2. **Structural validity** — package/schema/application open.
3. **Preservation fidelity** — unrelated content and features unchanged.
4. **Visual quality** — layout, clipping, hierarchy, brand fit.
5. **Native editability** — real styles, formulas, charts, fields, revisions.
6. **Auditability** — citations, diff, assumptions, provenance.
7. **Safety** — untrusted content, active content, secret/network boundaries.
8. **Operational reliability** — deterministic completion, resumability, batch behavior.

“Claude parity” should mean no lower score on the same fixture/task, not merely support for the same file extension.

## 7. Sources

### Primary Anthropic

- [Public Skills repository](https://github.com/anthropics/skills), snapshot `0a64e398ec6bb34a494f0c347e8ccae53a862f8e`.
- [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview).
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).
- [Create and edit files with Claude](https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude).
- [Claude for M365 overview](https://claude.com/docs/office-agents/overview).
- [Claude for Excel](https://claude.com/docs/office-agents/excel).
- [Claude for PowerPoint](https://claude.com/docs/office-agents/powerpoint).
- [Claude for Word](https://claude.com/docs/office-agents/word).
- [Work across M365 apps](https://claude.com/docs/office-agents/work-across-apps).

### Important official caveats

Anthropic itself does not recommend current Excel/PowerPoint/Word add-ins for final or audit-critical deliverables without human review. Excel data tables/macros/VBA are unsupported. Cross-app mode only accesses currently open files and cannot create/open/close/switch files. These limitations matter when defining “current Claude level.”
