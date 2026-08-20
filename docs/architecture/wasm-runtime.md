# Office and OCR WebAssembly runtime in Arena

## Why WASM

Direct native installation paths were tested and blocked by the interactive Arena egress policy:

- Debian APT mirrors over HTTP/HTTPS;
- The Document Foundation downloads and mirrors;
- LibreItalia AppImage hosting;
- GitHub release-assets/object hosting;
- Snapcraft, Docker Hub, GHCR and Quay.

GitHub API/git and the npm registry are available. The npm registry therefore provides the reproducible runtime path.

## LibreOffice WASM

Pinned dependency:

```json
"@matbee/libreoffice-converter": "2.7.2"
```

Package characteristics at the pinned version:

- npm integrity recorded in `package-lock.json`;
- MPL-2.0;
- approximately 249 MB installed for LibreOffice plus 82 MB for the standalone Open XML SDK validator;
- `soffice.wasm`: approximately 147 MB;
- `soffice.data`: approximately 100 MB;
- LibreOfficeKit-based DOCX/XLSX/PPTX/legacy conversion;
- bundled Latin/Cyrillic and other common fonts.

The runtime is executed through `scripts/wasm-office.mjs` and the Python `office_runtime` adapter. Native `soffice` remains preferred automatically when present.

```bash
DOCUMENT_SYSTEM_OFFICE_BACKEND=wasm scripts/documentctl render report.docx -o render/
```

### Supported current uses

- DOCX → PDF and page images;
- PPTX → PDF and slide images;
- XLSX → PDF and printable-sheet images;
- XLSX open/recalculate/save through an editor session;
- legacy Office → modern OOXML/PDF conversion where supported by the WASM build.

### Runtime behavior discovered during integration

1. A filename must be passed to the converter. Without it, the one-shot API assumes DOCX and misclassifies XLSX/PPTX buffers.
2. Same-format XLSX save is handled through `openDocument`/`getStructure`/`closeDocument`, not generic conversion. Reading Calc structure forces formula evaluation before save.
3. Cold WASM initialization can take over a minute on constrained CPUs; the Python adapter enforces a 300-second minimum timeout.
4. The package’s subprocess worker can survive wrapper termination and retain roughly 1 GB RAM. The wrapper is started in its own process group, and the Python adapter kills the complete group after output materializes.
5. Each worker can approach 1 GB RSS. Batch rendering/visual validation is automatically serialized when WASM is the selected backend; non-rendering inspection remains concurrent.
6. The XLSX output may contain valid style references that openpyxl cannot map back to named-style labels. Extraction falls back to `style_id:N` while preserving the workbook and validating formulas/output.
7. LibreOffice-generated PDF `/OpenAction` can be a benign page destination. PDF safety analysis now distinguishes destination navigation from executable action dictionaries.

### Observed results

- Russian DOCX rendered correctly with embedded/substituted Cyrillic fonts.
- Nine-slide 16:9 PPTX rendered with correct page geometry, charts, tables and text.
- Contact sheets now adapt their tile aspect ratio to portrait documents or landscape slides.
- XLSX formula caches were populated and formula-error QA passed.
- Full DOCX/XLSX/PPTX integration tests now run in the interactive sandbox.

## Tesseract.js WASM

Pinned dependencies:

```json
"tesseract.js": "7.0.0",
"@tesseract.js-data/eng": "1.0.0",
"@tesseract.js-data/rus": "1.0.0"
```

The `scripts/wasm-ocr.mjs` wrapper copies the bundled compressed traineddata into a local ignored cache and performs offline OCR. `pdf-ocr` chooses native Tesseract when installed and Tesseract.js otherwise.

The WASM OCR route:

1. rasterizes PDF pages with PDFium;
2. recognizes English, Russian, or `rus+eng` with one reusable worker;
3. reconstructs each page from the source image;
4. adds an embedded-font invisible searchable text layer;
5. records characters, words and recognition duration per page.

Russian/English OCR was verified on the generated operational report. No network fetch is needed after `npm ci`.

## Standalone Microsoft Open XML SDK validation

Pinned dependency:

```json
"@xarsh/ooxml-validator": "0.3.0"
```

Its platform-specific optional dependency installs an 82 MB self-contained Linux x64 binary with Microsoft Open XML SDK. It requires neither host .NET nor NuGet access and validates DOCX/XLSX/PPTX against Microsoft 365.

The first SDK pass found defects tolerated by Microsoft/LibreOffice readers but invalid against the SDK model:

- DOCX `tcPr`, table border/margin, `tblLayout`, settings and on/off element ordering;
- XLSX font child particle ordering emitted by openpyxl;
- signed/overflowing PowerPoint chart axis IDs emitted by python-pptx.

All generators now normalize these structures after creation. Current generated DOCX, XLSX and PPTX examples return zero SDK errors.

## Bootstrap and verification

```bash
scripts/bootstrap-documents.sh
scripts/documentctl env
scripts/documentctl doctor --self-test
pytest
scripts/run-all-evals.sh
```

Expected Arena capability flags after bootstrap:

- `office_backends.native = false` (unless the host changes);
- `office_backends.wasm = true`;
- `office_rendering = true`;
- `ocr = true`;
- `openxml_sdk_validation = true` through the standalone binary;
- DOCX/XLSX/PPTX/PDF/OCR self-tests all pass.

## Security and repository size

- `node_modules` is ignored and never committed.
- Dependency names, versions and integrity hashes are committed in `package.json` and `package-lock.json`.
- `npm audit --omit=dev` reports zero known vulnerabilities at the integration snapshot.
- WASM receives only explicit buffers and an isolated virtual filesystem.
- Generated caches and outputs remain under ignored `.cache` and `.document-work` directories.

LibreOffice WASM is a real Office-compatible rendering engine, but it is not a Microsoft Office oracle. Native Microsoft validation remains the final unresolved compatibility tier.
