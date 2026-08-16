#!/usr/bin/env python3
"""
Typeset the ГОСТ whitepaper straight to PDF with Typst.

The .docx build (build_whitepaper.js) and this one carry the same content on
purpose — they are the two delivery routes for the same report:

  .docx  when the recipient must edit, comment or track changes. Line breaking
         is Word's job, so the file only *asks* for hyphenation and justified
         text and the result depends on the reader.
  .pdf   when the recipient must only read, print or archive. Typst breaks the
         lines here, at compile time, with real ru hyphenation patterns and
         Knuth-Plass paragraph optimisation, so what is measured is what ships.

Run:  .venv/bin/python showcase/build_whitepaper_pdf.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import typst

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "out" / "Модернизация_сети_накопителей.pdf"
SRC = HERE / "whitepaper.typ"
FONTS = REPO / "assets" / "fonts"


def main() -> int:
    if not SRC.is_file():
        print(f"missing source: {SRC}", file=sys.stderr)
        return 1
    if not any(FONTS.glob("tinos*.ttf")):
        print("Tinos not installed — run tools/install_fonts.py", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # ignore_system_fonts keeps the build reproducible: only assets/fonts is
    # consulted, so a font present on one machine cannot change the layout.
    typst.compile(
        str(SRC),
        output=str(OUT),
        root=str(HERE),
        font_paths=[str(FONTS)],
        ignore_system_fonts=True,
    )
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
