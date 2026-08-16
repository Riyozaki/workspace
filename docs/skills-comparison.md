# Kimi skills or Claude skills?

You asked which suits me better. Short answer: **neither runs here as shipped —
so I took the ideas from both and built the implementation against this
sandbox.** The reasoning, since the choice affects everything built on top.

## What each one is

**Moonshot's `docx` skill** (the `docx.zip` you put on `main`) is a serious
piece of engineering: 2,144 lines of reference material, three routes (create
via C# + OpenXML SDK, edit via a "WIR" engine, convert via a markdown pipeline),
a compiled validator, and six background-generator scripts. The WIR editing
engine is the standout — a proper open/read/edit/save session model over an
existing `.docx`, which is exactly the right abstraction for editing a document
without destroying its formatting.

**Anthropic's document skills** are terser and more empirical: a table routing
you to an approach, then a dense list of the specific ways each library bites
you. Less architecture, more accumulated scar tissue. Their strength is that
almost every line prevents a concrete failure.

## Why neither runs as shipped

| | Kimi `docx` | Anthropic `docx`/`xlsx`/`pptx`/`pdf` |
|---|---|---|
| Needs .NET SDK 6+ | yes — the whole Create route | no |
| Needs LibreOffice | for `.doc` conversion | **yes** — rendering, validation, `recalc.py` |
| Needs compiled binaries | yes — `_core.cpython-**312**-x86_64-linux-gnu.so` | no |
| Runs on this image | **no** | **partly** |
| Licence permits vendoring | **no** | **no** for these four |

Concretely, the blockers I verified rather than assumed:

- **.NET is unreachable.** `dot.net`, `aka.ms`, `builds.dotnet.microsoft.com`
  and `api.nuget.org` all fail to connect. Kimi's `scripts/docx` tries to
  bootstrap the SDK on first run; it cannot.
- **The WIR engine is compiled for CPython 3.12.** This image is 3.11, and 3.12
  cannot be installed — Debian mirrors are unreachable, python.org is
  unreachable, and `uv python install` fails on a TLS error fetching from GitHub
  release assets. `import engine` raises `ModuleNotFoundError: engine._core`.
  This is not a bug I can route around; the source is not in the package, and
  the licence forbids reverse engineering it.
- **LibreOffice is unreachable**, so Anthropic's `soffice.py`, their
  `xlsx/scripts/recalc.py`, and their entire "render it and look at it" QA loop
  do not function.
- **Both licences forbid redistribution.** Moonshot's says the materials "may
  not be reproduced, modified, or redistributed in whole or in part".
  Anthropic's four document skills are source-available, not open source, and
  explicitly prohibit retaining copies outside Anthropic's services or creating
  derivative works. Copying either into your repository would be a licence
  violation, regardless of whether it ran.

Their *other* skills are Apache-2.0, and those I did vendor — see below.

## What I actually built

Original implementations in `skills/docx`, `skills/xlsx`, `skills/pptx`,
`skills/pdf`, plus a `document-quality` gate, all written against the toolchain
in `tools/`. Every replacement for a missing dependency is verified working:

| Their approach | Mine |
|---|---|
| C# + OpenXML SDK (Kimi) | `docx` and `pptxgenjs` on npm, `openpyxl` on PyPI |
| `soffice --convert-to pdf` | Chromium via `tools/render.py` → PDF → PNG |
| LibreOffice recalculation | `tools/recalc.py` — pure-python `formulas` engine |
| Compiled OpenXML validator | `tools/validate.py` — zip, XML parts, dangling relationships, plus editorial checks |
| WIR session editing | unzip → patch `document.xml` → rezip, documented with the run-fragmentation and `<w:del>` traps |

The one real capability loss is Kimi's WIR engine. Editing raw
`word/document.xml` is more error-prone than a session API, so `skills/docx`
compensates with explicit warnings about the traps that abstraction hid: text
fragmented across `<w:r>` runs, `<w:delText>` inside `<w:del>`, deleted paragraph
marks, and `ElementTree` corrupting namespaces on write.

## Which style I borrowed

**Anthropic's**, deliberately. Their format works better for me because it front-loads
the things a model gets wrong.

I know the docx-js and openpyxl APIs. What I do not reliably know is that
`ShadingType.SOLID` renders black, that an 8-digit hex corrupts a pptx, that
`data_only=True` destroys formulas if you save, or that an `@page { size }` rule
silently overrides the dimensions passed to `page.pdf()`. A skill spending its
budget on trap lists buys far more than one spending it on API tutorials.

Two things I took from Kimi instead:

- **Route first.** Its opening decision table — does a target file exist, is
  its formatting load-bearing — is the right first question, and prevents the
  single worst docx failure: rebuilding a user's template from scratch.
- **An explicit delivery checklist.** Kimi's six-point pre-delivery list is
  good practice, and `document-quality` expands it.

I dropped Kimi's hard rule against markdown→docx as a *creation* path but kept
its reasoning: pandoc output is generic and looks it. It stays as a preview
mechanism only.

## What I vendored

Five Apache-2.0 skills from `anthropics/skills`, copied unmodified with their
licences: `theme-factory`, `brand-guidelines`, `doc-coauthoring`,
`internal-comms`, `skill-creator`. `theme-factory` is immediately useful — ten
worked colour and type systems — and `doc-coauthoring` is the best thing in
either collection for long documents written *with* someone rather than handed
over. Attribution is in `skills/NOTICE.md`.

Your `docx.zip` is untouched on `main`.

## If you disagree

The honest counter-argument is that Kimi's C# route produces better Word output
than docx-js, and its WIR engine is a better editing model. Both are true. If
you can give the sandbox network access to `dot.net` and a Debian mirror, tell
me and I will add a .NET route alongside the current one and use whichever suits
each task. The toolchain does not assume those tools stay missing.
