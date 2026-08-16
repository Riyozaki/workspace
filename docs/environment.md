# Environment

What this sandbox has, what it does not, and why the toolchain is built the way
it is. Verified 2026-08-16.

## Baseline

| | |
|---|---|
| OS | Debian 12 (bookworm), x86-64 |
| Python | 3.11.2 (`/usr/bin/python3`) — 3.12 is **not** installable |
| Node | 22.22.3 with npm |
| sudo | available (uid 1001, `sudo` group) — but see below |
| Disk | ~20 GB free |
| Fonts | DejaVu only, 6 files |

## Network: partially open

This is the constraint that shapes everything else. Reachable:

| Host | Status |
|---|---|
| `pypi.org`, `files.pythonhosted.org` | **200** — pip works |
| `registry.npmjs.org` | **200** — npm works |
| `github.com` (git clone, HTML) | **200** |
| `codeload.github.com` (tarballs) | **200** |

Blocked (connection fails or TLS is intercepted):

| Host | Consequence |
|---|---|
| `deb.debian.org` and every Debian mirror tried | **apt cannot install anything.** `sudo` is useless for packages. |
| `release-assets.githubusercontent.com` | GitHub *release binaries* cannot be downloaded, though the repo can be cloned |
| `raw.githubusercontent.com` | fetch files via `git clone` or `codeload` instead |
| `dot.net`, `aka.ms`, `builds.dotnet.microsoft.com`, `api.nuget.org` | **no .NET SDK** |
| `download.documentfoundation.org`, sourceforge | **no LibreOffice** |
| `cdn.playwright.dev` | `playwright install` cannot fetch browsers |
| `conda.anaconda.org`, `repo.anaconda.com`, `prefix.dev` | no conda |
| `python.org/ftp` | cannot build another Python |
| `fonts.googleapis.com`, `fonts.gstatic.com` | fetch fonts from npm instead |
| `cdn.jsdelivr.net`, `unpkg.com` | use the npm registry directly |

**Everything must come from PyPI, npm, or a git clone.** That single rule
explains every unusual choice below.

## What is missing, and what replaces it

| Missing | Normally used for | Replacement here |
|---|---|---|
| LibreOffice (`soffice`) | `--convert-to pdf`, recalculating formulas, `.doc`/`.ppt` conversion | Chromium for rendering (`tools/render.py`), the `formulas` engine for recalculation (`tools/recalc.py`). **Legacy `.doc`/`.ppt`/`.xls` cannot be converted at all** — ask the user for the modern format. |
| .NET SDK | Anthropic's and Moonshot's C#/OpenXML SDK routes | `docx` and `pptxgenjs` on npm, `openpyxl` on PyPI |
| Poppler (`pdftoppm`, `pdftotext`) | rasterising and reading PDFs | `pypdfium2`, `pdfplumber` (both bundle their own binaries) |
| Pandoc (system) | format conversion | `pypandoc-binary` bundles pandoc 3.9 |
| Playwright browsers | headless rendering | `@sparticuz/chromium` from npm |
| Tesseract | OCR of scanned PDFs | **nothing** — say so rather than returning empty text |
| Cyrillic-capable UI fonts | any Russian document | merged TTFs via `tools/install_fonts.py` |

## The preview must show the document, not a generic page

Without LibreOffice, `tools/render.py` converts a document to HTML and prints
it with Chromium. The trap: it used to apply `assets/preview.css` — A4, 18 mm
margins, Inter — to *every* file, and passed `format: 'A4'` to `page.pdf()`.
Both silently overrode whatever the document itself specified, so the preview
looked plausible while the real file was wrong. Margin, font-size, leading and
whitespace defects were invisible until the `.docx` was opened in Word.

`from_docx()` now reads the actual geometry out of the file — `w:pgSz`,
`w:pgMar`, `w:autoHyphenation`, and the font, size, `w:line` and `w:firstLine`
from `styles.xml` — builds an `@page` rule from it, and sets `hyphens: auto`
to match Word's line breaking. `page.pdf()` is then told
`preferCSSPageSize: true` with zero margins so it cannot override that rule.

**A preview you cannot trust is worse than no preview.** If a rendered page
disagrees with what Word shows, fix the renderer before touching the document.

## The three problems worth knowing about

### 1. Chromium will not start on its own

`@sparticuz/chromium` ships a Chromium built for Amazon Linux 2023. It needs
`libnspr4.so` and `libnss3.so`, which Debian here does not have. The package
*carries* them in `bin/al2023.tar.br` but only unpacks them when it detects a
Lambda environment, so a plain `puppeteer.launch()` fails:

```
Failed to launch the browser process: Code: 127
/tmp/chromium: error while loading shared libraries: libnspr4.so
```

`tools/js/chromium.js` inflates that payload and passes `LD_LIBRARY_PATH` to the
browser through puppeteer's `env` option. It has to be `env` and not
`process.env`: the dynamic linker reads `LD_LIBRARY_PATH` when a process
*starts*, so a parent that sets its own variable after boot changes nothing —
but `env` applies to the child about to be spawned. Always launch through this
wrapper.

### 2. openpyxl writes formulas with no values

A formula written by openpyxl has no cached result, so the cell reads as `None`
to pandas, to `data_only=True`, and to every previewer and converter. The file
looks empty to everything except Excel. Normally you would open it in
LibreOffice to fix that; here, run `tools/recalc.py`, which evaluates with the
pure-python `formulas` engine and injects the values into the sheet XML.

It does not implement `XLOOKUP`, `XMATCH`, `FILTER`, `SORTBY`, `TEXTSPLIT`,
`LAMBDA`, or `LET` — it names them in its report rather than leaving a silent
`#NAME?`. Use `INDEX`/`MATCH` and do the rest in Python.

### 3. Fonts need converting, not copying

Two separate traps, both silent:

- **fontconfig cannot read `.woff2`.** Chromium finds local fonts through
  fontconfig, so dropping webfonts into a directory does nothing — text falls
  back to another family and nothing warns you.
- **@fontsource splits families by subset.** `inter-latin-400` has no Cyrillic
  and `inter-cyrillic-400` has no Latin, yet both declare the family "Inter".
  Two files, same family and weight, disjoint coverage: fontconfig picks one and
  the other alphabet silently degrades.

`tools/install_fonts.py` converts to TTF and merges the subsets into one file
per family and weight. Check coverage with `--report`.

The symptom of getting this wrong is subtle: text renders, and looks fine, but
every family resolves to the same fallback. Measuring rendered text width for
two supposedly different fonts is how you detect it — identical widths mean
identical fallback.

## Verifying

```bash
bash tools/setup.sh --check     # verify without installing
bash tools/setup.sh             # install or repair; safe to re-run
```

The script ends with a real render through Chromium, so a pass means the whole
chain works, not just that packages are present.

## If the network opens up later

Should apt or the Microsoft CDN become reachable, LibreOffice and .NET would
allow a few things this toolchain cannot do: converting legacy `.doc`/`.ppt`,
byte-exact Word pagination in previews, and native chart rendering in the
`.pptx` preview. Nothing in `tools/` depends on their absence — `render.py`
would simply gain a `soffice` route. The current design is not a workaround to
be undone, only a floor that holds without them.
