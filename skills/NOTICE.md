# Third-party attribution

## Vendored from anthropics/skills

The following directories are copied unmodified from
<https://github.com/anthropics/skills> and are licensed under the Apache
License 2.0. Each carries its upstream `LICENSE.txt`:

- `brand-guidelines/`
- `internal-comms/`
- `skill-creator/`
- `theme-factory/`
- `doc-coauthoring/` — the upstream directory ships no `LICENSE.txt`; it sits
  in the same Apache-2.0 repository and is covered by it. Retrieved
  2026-08-16.

Copyright and licence notices inside those files are left intact. Modifications
to any of them should be noted here.

## Deliberately not vendored

**Anthropic's `docx`, `xlsx`, `pptx`, and `pdf` skills.** These are
source-available but proprietary. Their licence permits use only within
Anthropic's own services and explicitly forbids extracting the materials,
retaining copies outside those services, creating derivative works, and
redistribution. They also depend on LibreOffice (`soffice`) for validation and
rendering, which cannot be installed in this environment.

The `skills/docx`, `skills/xlsx`, `skills/pptx`, and `skills/pdf` directories in
this repository are original work written against this repository's own
toolchain. Where they describe a well-known library behaviour — that docx-js
tables need widths on both the table and each cell, that pptxgenjs corrupts a
file given an 8-digit hex colour — that is publicly documented behaviour of
those npm packages, described here in our own words and verified in this
sandbox.

**Moonshot AI's `docx` skill** (supplied as `docx.zip` on `main`). Its licence
states the materials "may not be reproduced, modified, or redistributed in whole
or in part" and prohibits reverse engineering the compiled components. It is not
copied into this tree, and its compiled `.so` modules target CPython 3.12 while
this image runs 3.11, so they cannot be loaded regardless.

The original `docx.zip` remains untouched on the `main` branch as the user
uploaded it. It is not deleted, redistributed, or modified here.

## Fonts

Installed into `assets/fonts/` by `tools/install_fonts.py`, from npm packages:

| Family | Licence |
|---|---|
| Inter | SIL Open Font License 1.1 |
| PT Serif | SIL Open Font License 1.1 |
| JetBrains Mono | SIL Open Font License 1.1 |
| DejaVu | Bitstream Vera / Arev fonts licence |

The generated TTFs are subset merges of the upstream `latin` and `cyrillic`
webfont files. The OFL permits modification and redistribution; the merged files
keep their original family names, which the OFL allows as no Reserved Font Name
is declared by these projects.

## Chromium

`@sparticuz/chromium` (MIT) packages a Chromium build for serverless use.
Chromium itself is BSD-3-Clause with third-party components under their own
licences. Used here only to render documents locally; nothing is served.
