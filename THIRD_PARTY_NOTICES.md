# Third-party dependency notices

This repository contains original clean-room orchestration and document-processing code. It does not vendor the source or binaries of the dependencies below; bootstrap installs them from their normal package sources. Exact Python artifacts and hashes are recorded in `requirements.lock`.

This file is an engineering inventory, not legal advice. Confirm terms before redistributing a bundled runtime.

| Component | Purpose | Upstream license (summary) |
|---|---|---|
| defusedxml | defensive XML helpers | Python Software Foundation License |
| jsonschema | JSON specification validation | MIT |
| lxml | XML parsing | BSD-3-Clause |
| matplotlib | chart image generation | PSF-based/BSD-compatible |
| openpyxl / et_xmlfile | XLSX creation and analysis | MIT |
| pandas / NumPy | tabular analysis and bulk data transforms | BSD-3-Clause |
| Pillow | image/contact-sheet operations | HPND |
| pypandoc_binary / Pandoc | semantic document conversion fallback/tooling | wrapper MIT; bundled Pandoc GPL-2.0-or-later |
| pdfplumber / pdfminer.six | PDF text and table extraction | MIT |
| pypdf | PDF metadata/page/form operations | BSD-3-Clause |
| pypdfium2 / PDFium | PDF rasterization | Apache-2.0 / BSD-style PDFium notices |
| pytesseract / Tesseract OCR | native searchable scan route | Apache-2.0 |
| tesseract.js + bundled eng/rus data | pinned WebAssembly OCR fallback | Apache-2.0 |
| ReportLab | PDF authoring and overlays | BSD |
| python-docx | DOCX creation primitives | MIT |
| python-pptx | PPTX creation and analysis | MIT |
| pytest / pytest-cov | tests | MIT |
| Ruff | static analysis | MIT |
| Microsoft Open XML SDK | OOXML schema/semantic validator | MIT |
| @xarsh/ooxml-validator | pinned standalone Open XML SDK binary wrapper | MIT |
| LibreOffice | external compatibility renderer/converter | MPL-2.0 / LGPLv3+ |
| @matbee/libreoffice-converter / LibreOffice WASM | pinned in-process Office renderer fallback | MPL-2.0 |
| System fonts | rendering | package-specific; DejaVu, Liberation, Noto, Carlito, and Caladea have their own open font licenses |

## Proprietary comparison artifact

`docx.zip` is not a dependency. It is a user-provided Moonshot AI research artifact with a restrictive proprietary license. The document system does not import, execute, unpack into product code, modify, or redistribute its contents.

## Anthropic reference materials

The initial research consulted publicly visible Anthropic document Skills. Anthropic identifies those four document Skills as source-available rather than open source. No Anthropic Skill source or script is copied into this implementation.
