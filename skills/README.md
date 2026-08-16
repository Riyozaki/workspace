# Skills

Each folder is one skill: a `SKILL.md` with YAML frontmatter (`name`, `description`) plus any scripts or references it needs. The description is what decides whether a skill gets loaded for a given request, so it names concrete triggers rather than describing the skill in the abstract.

## Written for this repository

Tuned to the toolchain in `tools/`, which works without LibreOffice, .NET, or apt — see [`docs/environment.md`](../docs/environment.md) for why that constraint exists.

| Skill | Use for |
|---|---|
| [`docx`](docx/) | Word documents — creating, editing, tracked changes, templates |
| [`xlsx`](xlsx/) | Spreadsheets — formulas, models, formatted tables, the recalculation problem |
| [`pptx`](pptx/) | Presentations — decks from scratch, filling templates, native charts |
| [`pdf`](pdf/) | PDFs — creating via HTML/Typst/reportlab, merging, extracting, rasterising |
| [`document-quality`](document-quality/) | The delivery gate for all of the above: self-review, typography, Russian typographic conventions, failure modes |

`document-quality` is the one to read first when planning a large document, and last before handing anything over.

## Vendored from anthropics/skills

Copied unmodified under Apache-2.0. Source: <https://github.com/anthropics/skills>

| Skill | Use for |
|---|---|
| [`theme-factory`](theme-factory/) | Ten ready colour/type themes, or generating one to match a brand |
| [`brand-guidelines`](brand-guidelines/) | Worked example of encoding a house style as a skill |
| [`doc-coauthoring`](doc-coauthoring/) | Structured workflow for writing a document *with* someone: context gathering, iteration, reader testing |
| [`internal-comms`](internal-comms/) | Status reports, leadership updates, incident reports, newsletters, FAQs |
| [`skill-creator`](skill-creator/) | Building new skills, and evaluating whether a skill actually helps |

Anthropic's own `docx`/`xlsx/`pptx`/`pdf` skills are **not** vendored — they are proprietary, licensed for use inside Anthropic's services only, and their scripts depend on LibreOffice, which is unavailable here. The four skills above were rewritten from scratch against this environment; where a specific OOXML trap is common knowledge (docx-js dual widths, pptxgenjs hex colours), that knowledge is restated in our own words.

Moonshot's `docx` skill is likewise not vendored: it is proprietary, explicitly forbids redistribution, and its engine ships as compiled CPython 3.12 `.so` files that cannot load on this image's Python 3.11. See [`docs/skills-comparison.md`](../docs/skills-comparison.md).

## Adding a skill

```markdown
---
name: my-skill
description: What it does and exactly when to use it — name the triggers.
---

# My skill
...
```

Keep `SKILL.md` under roughly 500 lines; push detail into `references/` and link to it. Write the traps, not the API — the model knows the API, and gets bitten by the footguns.
