# Document agent workspace

Toolchain and skills for producing Word, Excel, PowerPoint, and PDF
deliverables — built to work in a sandbox with no apt, no LibreOffice, and no
.NET.

```bash
bash tools/setup.sh                      # install (idempotent, ~40s)
.venv/bin/python tests/test_toolchain.py # 15 regression tests
```

## Quick start

```bash
# make something
node examples/build_report.js                       # Word report
.venv/bin/python examples/build_model.py            # Excel model with formulas
node examples/build_deck.js                         # PowerPoint deck

# the two steps that matter before delivering anything
.venv/bin/python tools/validate.py .workdir/Квартальный_отчёт.docx
.venv/bin/python tools/render.py  .workdir/Квартальный_отчёт.docx -o .workdir/qa
# ...then look at the PNGs in .workdir/qa/
```

## Layout

```
skills/         instructions the agent loads per task — see skills/README.md
tools/          the toolchain
  setup.sh        install and verify everything
  render.py       docx/xlsx/pptx/pdf/md/html -> PDF -> PNG (visual QA)
  validate.py     OOXML structure + editorial checks
  recalc.py       evaluate xlsx formulas, write cached values
  install_fonts.py  build Cyrillic-capable TTFs
  js/chromium.js    headless browser that actually launches here
  js/docx_fix.js    repair docx-js output
examples/       worked examples, all verified in CI-style tests
tests/          regression tests for every bug found during development
docs/           environment constraints, and the Kimi-vs-Claude analysis
assets/         fonts and the preview stylesheet
```

## The three things worth knowing

**1. Validation is not verification.** `validate.py` proves a file is not
corrupt. It cannot see that a heading is stranded at the foot of a page or that
cover text is white on a pale background. `render.py` exists so you can look at
the output, and looking at it is not optional.

**2. openpyxl writes formulas with no cached values.** Until something computes
them, every formula cell reads as empty to pandas, to previews, to converters —
to everything except Excel. Normally you would fix that by opening the file in
LibreOffice, which does not exist here. Run `tools/recalc.py`.

**3. Chromium needs a wrapper to start at all.** The npm Chromium build targets
Amazon Linux and needs libraries Debian lacks; the fix has to pass
`LD_LIBRARY_PATH` to the browser child process, because the parent cannot change
its own after boot. Always launch through `tools/js/chromium.js`.

Full details, including everything the network blocks, in
[`docs/environment.md`](docs/environment.md).

## Which skills, and why

You asked whether Kimi's or Claude's skills suit me better. Neither runs here as
shipped — Kimi's needs .NET and a CPython 3.12 binary, Anthropic's document
skills need LibreOffice, and both licences forbid copying them into this
repository. So `skills/docx`, `skills/xlsx`, `skills/pptx`, `skills/pdf`, and
`skills/document-quality` are written from scratch against this toolchain, in
Anthropic's terser style, with Kimi's route-first structure and delivery
checklist. Five Apache-2.0 skills from `anthropics/skills` are vendored intact
with attribution.

The reasoning, and what would change if the sandbox got network access to those
tools, is in [`docs/skills-comparison.md`](docs/skills-comparison.md).

## Notes

`.workdir/` is scratch space and is gitignored, as are `.venv/`,
`node_modules/`, and the generated fonts in `assets/fonts/*.ttf` (rebuild with
`python tools/install_fonts.py`). Deliverables should be written somewhere
deliberate, named for their topic in the user's language.
