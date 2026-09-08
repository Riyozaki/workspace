"""Compare manuscript words with the imported PDFs, not typography or prose quality.

Run from workspace root:
  python -m venv .venv
  .venv/bin/pip install -r projects/shards-of-the-abyss/tools/requirements.txt
  .venv/bin/python projects/shards-of-the-abyss/tools/check_pdf_text.py

Does not modify any manuscript or PDF. Ignores title page, known running headers,
page numbers, punctuation, spaces and case. Equality is NOT visual/PDF proofing.
"""
import json
from pathlib import Path
import re
import sys

from pypdf import PdfReader

PROJECT = Path(__file__).resolve().parents[1]
BOOK = PROJECT / "book"
HEADER = re.compile(r"\s*(?:Х\s*Р\s*О\s*Н\s*И\s*К\s*И\s*Э\s*Т\s*Е\s*Р\s*И\s*У\s*М\s*А|Г\s*Л\s*А\s*В\s*А\s*\d(?:\s*\d)*)\s*")


def normalize(text):
    return re.sub(r"[^\w]+", "", text).lower()


def pdf_body(reader):
    pages = []
    for page in reader.pages[1:]:
        lines = (page.extract_text() or "").splitlines()
        # Remove only the last line if it is a page number; preserve body digits.
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and re.fullmatch(r"\s*\d+\s*", lines[-1]):
            lines.pop()
        pages.append("\n".join(line for line in lines if not HEADER.fullmatch(line)))
    return "\n".join(pages)


def main():
    results = []
    for chapter in range(1, 17):
        paths = list((BOOK / "03-manuscript").glob(f"arc-*/ch-{chapter:02}.md"))
        if len(paths) != 1:
            raise ValueError(f"Expected one manuscript for chapter {chapter}: {paths}")
        md = paths[0]
        reader = PdfReader(BOOK / f"05-publication/Глава_{chapter:02}.pdf")
        manuscript = md.read_text(encoding="utf-8")
        if not manuscript.startswith("# Глава "):
            raise ValueError(f"Unexpected manuscript heading: {md}")
        a = normalize(manuscript.split("\n", 1)[1])
        b = normalize(pdf_body(reader))
        results.append({"chapter": chapter, "pages": len(reader.pages),
                        "manuscript_characters_normalized": len(a),
                        "pdf_characters_normalized": len(b),
                        "normalized_body_equal": a == b})
    print(json.dumps({"scope": "chapters 1–16; normalized text only, not typography",
                      "results": results}, ensure_ascii=False, indent=2))
    return 0 if all(r["normalized_body_equal"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
