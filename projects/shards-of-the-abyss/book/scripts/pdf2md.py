#!/usr/bin/env python3
"""Обратная сборка главы из PDF (сборка publication-work, сентябрь 2026) в markdown.

Проверено на главе 7, где есть md-исходник: 682 из 682 абзацев совпали дословно.
Абзац определяется по красной строке (отступ первой строки), переносы по дефису
склеиваются, колонтитулы («ХРОНИКИ ЭТЕРИУМА», «Г Л А В А  N», номер страницы) и
титульный лист отбрасываются. Курсив Тени в этих PDF набран звёздочками — они
остаются как есть, то есть сразу дают markdown-курсив.

    python3 scripts/pdf2md.py "Глава_01 (1).pdf" temp/pdf-md/ch-01.md
    python3 scripts/pdf2md.py --all            # все Глава_*.pdf в корне → temp/pdf-md/
"""
import re, sys, glob
from collections import Counter
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover
    sys.exit("нужен pymupdf: pip install --break-system-packages pymupdf")

SERVICE = re.compile(r'\s*(ХРОНИКИ ЭТЕРИУМА|Г\s*Л\s*А\s*В\s*А\s*\d*|ГЛАВА \d+|КНИГА ПЕРВАЯ|◆|М\s*И\s*Н\s*Т\s*А|\d+)\s*')


def pdf_to_paras(path: str) -> list[str]:
    doc = pymupdf.open(path)
    lines = []
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                txt = "".join(s["text"] for s in l["spans"])
                if not txt.strip() or SERVICE.fullmatch(txt):
                    continue
                lines.append((round(l["bbox"][0], 1), txt))
    xs = Counter(x for x, _ in lines).most_common(2)
    indent = max(xs[0][0], xs[1][0])
    paras, cur = [], None
    for x, txt in lines:
        t = txt.strip()
        if abs(x - indent) < 2.5 or cur is None:
            if cur:
                paras.append(cur)
            cur = t
        elif cur.endswith('-') and re.match(r'[а-яё]', t):
            cur = cur[:-1] + t
        else:
            cur = cur + ' ' + t
    if cur:
        paras.append(cur)
    return [re.sub(r'\s*Г\s*Л\s*А\s*В\s*А\s+\d+\s*', ' ', p).strip() for p in paras]


def convert(src: str, dst: str) -> None:
    n = int(re.search(r'Глава_(\d+)', src).group(1))
    paras = pdf_to_paras(src)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(f"# Глава {n}\n\n" + "\n\n".join(paras) + "\n", encoding="utf-8")
    print(f"{src} → {dst}: {len(paras)} абзацев")


if __name__ == "__main__":
    if "--all" in sys.argv:
        for f in sorted(glob.glob("Глава_*.pdf")):
            n = int(re.search(r'Глава_(\d+)', f).group(1))
            convert(f, f"temp/pdf-md/ch-{n:02d}.md")
    else:
        convert(sys.argv[1], sys.argv[2])
