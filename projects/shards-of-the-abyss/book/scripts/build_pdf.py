#!/usr/bin/env python3
"""Сборка PDF главы из markdown — формат publication-work (А5, DejaVu Serif),
но с настоящим курсивом: в прежних сборках реплики Тени печатались со звёздочками.

    python3 scripts/build_pdf.py 03-manuscript/arc-01/ch-01.md            # → 05-publication/Глава_01.pdf
    python3 scripts/build_pdf.py 03-manuscript/arc-01/ch-01.md out.pdf

Зависимости: pip install --break-system-packages fpdf2 pyphen
Шрифты: DejaVuSerif (regular/bold — системные; italic — из matplotlib, если нет системного).

Разметка, которую понимает:
  # Глава N        — заголовок главы (титульный лист + колонтитул)
  ---              — разделитель сцен (◆)
  *курсив*         — реплики Тени / выделение
  **жирный**       — не используется в книге, но поддержан
Мягкие переносы расставляются pyphen (ru_RU); проверка «беспробельной пробой»
(additiontoSkill §7.C) остаётся за вызывающим.
"""
from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

try:
    import pyphen
    HYPH = pyphen.Pyphen(lang="ru_RU")
except Exception:  # pragma: no cover
    HYPH = None

BOOK = "ХРОНИКИ ЭТЕРИУМА"
PART = "КНИГА ПЕРВАЯ"
ARC_TITLE = {1: "МИНТА", 2: "МИНТА", 3: "МИНТА", 4: "МИНТА", 5: "МИНТА"}

PAGE_W, PAGE_H = 148, 210          # A5, мм
MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 18, 15, 14, 16
BODY_PT, HEAD_PT, FOOT_PT = 11.0, 9.0, 9.0
LEADING = 1.38                     # межстрочный, в долях кегля
INDENT_MM = 4.5                    # красная строка
SOFT = "\u00ad"


def find_fonts() -> dict[str, str]:
    cands = {
        "": ["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
        "B": ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"],
        "I": ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"],
        "BI": ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf"],
    }
    try:
        import matplotlib
        d = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
        cands[""].append(os.path.join(d, "DejaVuSerif.ttf"))
        cands["B"].append(os.path.join(d, "DejaVuSerif-Bold.ttf"))
        cands["I"].append(os.path.join(d, "DejaVuSerif-Italic.ttf"))
        cands["BI"].append(os.path.join(d, "DejaVuSerif-BoldItalic.ttf"))
    except Exception:
        pass
    out = {}
    for style, paths in cands.items():
        for p in paths:
            if os.path.exists(p):
                out[style] = p
                break
    missing = [s for s in ("", "B", "I") if s not in out]
    if missing:
        sys.exit(f"не найдены шрифты DejaVuSerif для стилей {missing}; "
                 f"поставьте fonts-dejavu-extra или matplotlib")
    return out


def hyphenate(text: str) -> str:
    if not HYPH:
        return text
    def h(m):
        w = m.group(0)
        if len(w) < 7:
            return w
        return HYPH.inserted(w, hyphen=SOFT)
    return re.sub(r"[А-Яа-яЁё]{7,}", h, text)


def parse_md(path: str):
    text = Path(path).read_text(encoding="utf-8")
    title = None
    items = []
    for raw in text.split("\n\n"):
        p = raw.strip()
        if not p:
            continue
        if p.startswith("# "):
            title = p[2:].strip()
            continue
        if p in ("---", "***", "* * *"):
            items.append(("break", ""))
            continue
        items.append(("para", re.sub(r"\s*\n\s*", " ", p)))
    return title, items


class Book(FPDF):
    def __init__(self, chapter_title: str, arc_title: str):
        super().__init__(orientation="P", unit="mm", format=(PAGE_W, PAGE_H))
        self.chapter_title = chapter_title
        self.arc_title = arc_title
        self.set_margins(MARGIN_L, MARGIN_T, MARGIN_R)
        self.set_auto_page_break(auto=True, margin=MARGIN_B)
        self.title_page = True

    def header(self):
        if self.title_page:
            return
        self.set_font("DejaVuSerif", "", HEAD_PT - 1.5)
        self.set_text_color(110, 110, 110)
        self.set_y(7)
        if self.page_no() % 2 == 0:
            self.cell(0, 5, BOOK, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            self.cell(0, 5, " ".join(self.chapter_title.upper()), align="R",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)
        self.set_y(MARGIN_T)

    def footer(self):
        if self.title_page:
            return
        self.set_y(-11)
        self.set_font("DejaVuSerif", "", FOOT_PT)
        self.set_text_color(110, 110, 110)
        self.cell(0, 5, str(self.page_no() - 1), align="C")
        self.set_text_color(0, 0, 0)


def render_title(pdf: Book, chapter_title: str):
    pdf.title_page = True
    pdf.add_page()
    pdf.set_font("DejaVuSerif", "", 9)
    pdf.set_y(70)
    pdf.cell(0, 6, " ".join(BOOK), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(120, 120, 120)
    pdf.line(PAGE_W / 2 - 22, pdf.get_y() + 1.5, PAGE_W / 2 + 22, pdf.get_y() + 1.5)
    pdf.ln(4)
    pdf.cell(0, 6, " ".join(PART), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(14)
    pdf.set_font("DejaVuSerif", "B", 22)
    pdf.cell(0, 12, chapter_title.upper(), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)
    pdf.set_font("DejaVuSerif", "", 12)
    pdf.cell(0, 8, "◆", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_y(PAGE_H - 30)
    pdf.set_font("DejaVuSerif", "", 8)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 5, " ".join(pdf.arc_title), align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.title_page = False


def md_inline_to_html(p: str) -> str:
    p = (p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    p = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", p)
    p = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", p)
    return p


def render_para(pdf: Book, p: str):
    line_h = BODY_PT * LEADING * 0.3528  # pt → mm
    html = md_inline_to_html(hyphenate(p))
    # красная строка — через неразрывный отступ первой строки
    pdf.set_font("DejaVuSerif", "", BODY_PT)
    pdf.set_x(MARGIN_L)
    # fpdf2: write_html не даёт отступа первой строки, эмулируем невидимым cell
    pdf.cell(INDENT_MM, line_h, "", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.write_html(f'<p line-height="{LEADING}">{html}</p>' if False else html)
    pdf.ln(line_h)


def render_para_manual(pdf: Book, p: str):
    """Ручная вёрстка абзаца с выключкой по ширине и курсивом внутри строки."""
    line_h = BODY_PT * LEADING * 0.3528
    width = PAGE_W - MARGIN_L - MARGIN_R
    # токены: (text, italic)
    toks = []
    for seg in re.split(r"(\*[^*]+\*)", hyphenate(p)):
        if not seg:
            continue
        if seg.startswith("*") and seg.endswith("*") and len(seg) > 2:
            toks.append((seg[1:-1], True))
        else:
            toks.append((seg, False))
    # разбить на слова с сохранением стиля
    words = []
    for text, it in toks:
        for w in re.split(r"(\s+)", text):
            if w == "":
                continue
            if w.isspace():
                if words and words[-1][0] != " ":
                    words.append((" ", it))
            else:
                words.append((w, it))
    # склеить слова, разделённые границей стиля без пробела (напр. «*Сильвия.*» + «,»)
    merged = []
    for w, it in words:
        if merged and w != " " and merged[-1][0] != " " and merged[-1][0] != "":
            # слипание: разные стили, но нет пробела → одно "слово" из двух частей
            merged[-1] = (merged[-1][0] + "\x00" + w, merged[-1][1]) if False else (merged[-1][0], merged[-1][1])
            merged.append((w, it))
        else:
            merged.append((w, it))
    words = merged

    def wlen(w, it):
        pdf.set_font("DejaVuSerif", "I" if it else "", BODY_PT)
        return pdf.get_string_width(w.replace(SOFT, ""))

    def parts_of(w):
        """варианты разрыва слова по мягким переносам: (head, tail)"""
        if SOFT not in w:
            return []
        idx = [i for i, c in enumerate(w) if c == SOFT]
        return [(w[:i].replace(SOFT, "") + "-", w[i + 1:]) for i in idx]

    lines = []          # каждая строка: список (text, italic), без ведущих/замыкающих пробелов
    cur, cur_w = [], 0.0
    avail = width - INDENT_MM  # первая строка короче на отступ
    i = 0
    while i < len(words):
        w, it = words[i]
        if w == " ":
            if cur:
                cur.append((" ", it)); cur_w += wlen(" ", it)
            i += 1
            continue
        lw = wlen(w.replace(SOFT, ""), it)
        if cur_w + lw <= avail:
            cur.append((w.replace(SOFT, ""), it)); cur_w += lw; i += 1
            continue
        # не влезает: пробуем перенос
        placed = False
        for head, tail in reversed(parts_of(w)):
            hw = wlen(head, it)
            if cur_w + hw <= avail and len(head) > 2 and len(tail.replace(SOFT, "")) > 1:
                cur.append((head, it))
                lines.append(cur)
                cur, cur_w, avail = [], 0.0, width
                words[i] = (tail, it)
                placed = True
                break
        if placed:
            continue
        if not cur:  # слово длиннее строки — кладём как есть
            cur.append((w.replace(SOFT, ""), it)); lines.append(cur)
            cur, cur_w, avail = [], 0.0, width
            i += 1
            continue
        # перенос строки без разрыва слова
        while cur and cur[-1][0] == " ":
            cur.pop()
        lines.append(cur)
        cur, cur_w, avail = [], 0.0, width
    while cur and cur[-1][0] == " ":
        cur.pop()
    if cur:
        lines.append(cur)

    # вывод
    for li, line in enumerate(lines):
        if pdf.get_y() + line_h > PAGE_H - MARGIN_B:
            pdf.add_page()
        x = MARGIN_L + (INDENT_MM if li == 0 else 0)
        avail_w = width - (INDENT_MM if li == 0 else 0)
        last = li == len(lines) - 1
        text_w = sum(wlen(t, it) for t, it in line if t != " ")
        n_sp = sum(1 for t, _ in line if t == " ")
        sp_w = wlen(" ", False)
        if not last and n_sp:
            sp_w = (avail_w - text_w) / n_sp
            if sp_w > wlen(" ", False) * 3:   # слишком редко — не растягиваем
                sp_w = wlen(" ", False)
        pdf.set_xy(x, pdf.get_y())
        for t, it in line:
            if t == " ":
                pdf.set_x(pdf.get_x() + sp_w)
                continue
            pdf.set_font("DejaVuSerif", "I" if it else "", BODY_PT)
            pdf.cell(wlen(t, it), line_h, t, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(line_h)


def build(src: str, dst: str | None = None) -> str:
    title, items = parse_md(src)
    if not title:
        m = re.search(r"ch-(\d+)", src)
        title = f"Глава {int(m.group(1))}" if m else "Глава"
    n = int(re.search(r"\d+", title).group(0))
    if dst is None:
        Path("05-publication").mkdir(exist_ok=True)
        dst = f"05-publication/Глава_{n:02d}.pdf"
    fonts = find_fonts()
    pdf = Book(title, ARC_TITLE.get((n - 1) // 7 + 1, "МИНТА"))
    pdf.set_title(f"{BOOK.title()}. {PART.capitalize()}. {title}")
    pdf.add_font("DejaVuSerif", "", fonts[""])
    pdf.add_font("DejaVuSerif", "B", fonts["B"])
    pdf.add_font("DejaVuSerif", "I", fonts["I"])
    if "BI" in fonts:
        pdf.add_font("DejaVuSerif", "BI", fonts["BI"])
    render_title(pdf, title)
    pdf.add_page()
    pdf.set_font("DejaVuSerif", "B", 13)
    pdf.cell(0, 10, title.upper(), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)
    line_h = BODY_PT * LEADING * 0.3528
    for kind, p in items:
        if kind == "break":
            pdf.ln(line_h * 0.6)
            if pdf.get_y() + line_h * 2 > PAGE_H - MARGIN_B:
                pdf.add_page()
            pdf.set_font("DejaVuSerif", "", BODY_PT)
            pdf.cell(0, line_h, "◆", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(line_h * 0.6)
            continue
        render_para_manual(pdf, p)
    pdf.output(dst)
    return dst


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out = build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print("→", out)
