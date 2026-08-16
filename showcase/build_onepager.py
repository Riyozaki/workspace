#!/usr/bin/env python3
"""
Showcase 4 of 4 — a print-ready A4 one-pager built directly as PDF.

Word and PowerPoint reflow; a PDF drawn with reportlab does not. When the
layout must be exact to the millimetre — a leave-behind, a term sheet, a form
— drawing the page directly is the right call, not exporting from a document.

Demonstrated:
  - absolute mm-grid layout on A4
  - embedded TrueType fonts with Cyrillic (registered families, bold variants)
  - vector drawing: rules, filled bars, a donut, badge shapes
  - a table with alternating rows and right-aligned figures
  - document outline (bookmarks), metadata, and a clickable external link
  - deterministic output: no reflow, no font substitution, no surprises

Run from the repository root:
    .venv/bin/python showcase/build_onepager.py
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, Color
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FONTS = REPO / "assets" / "fonts"
OUT = HERE / "out" / "Резюме_программы_одна_страница.pdf"

NAVY = HexColor("#1E2761")
ACCENT = HexColor("#4A6FA5")
CORAL = HexColor("#B85042")
GREEN = HexColor("#2E7D5B")
AMBER = HexColor("#C98A2B")
INK = HexColor("#1F2933")
MUTED = HexColor("#667085")
RULE = HexColor("#D5D9E0")
LIGHT = HexColor("#F4F6FA")
WHITE = HexColor("#FFFFFF")

W, H = A4  # 595.27 x 841.89 pt


def register_fonts() -> tuple[str, str]:
    """Register Inter + PT Serif. Returns the family names actually usable."""
    pdfmetrics.registerFont(TTFont("Inter", str(FONTS / "inter-400.ttf")))
    pdfmetrics.registerFont(TTFont("Inter-Bold", str(FONTS / "inter-700.ttf")))
    pdfmetrics.registerFont(TTFont("PTSerif", str(FONTS / "pt-serif-400.ttf")))
    pdfmetrics.registerFont(TTFont("PTSerif-Bold", str(FONTS / "pt-serif-700.ttf")))
    # registerFontFamily lets <b> work in Paragraph markup if it is ever used.
    pdfmetrics.registerFontFamily(
        "Inter", normal="Inter", bold="Inter-Bold", italic="Inter", boldItalic="Inter-Bold"
    )
    return "Inter", "PTSerif"


def text(c, x, y, s, font="Inter", size=9, color=INK, align="left"):
    c.setFont(font, size)
    c.setFillColor(color)
    if align == "right":
        c.drawRightString(x, y, s)
    elif align == "center":
        c.drawCentredString(x, y, s)
    else:
        c.drawString(x, y, s)


def wrap(c, x, y, s, width, font="Inter", size=9, color=INK, leading=12.5):
    """Minimal greedy wrapper — enough for a one-pager, no Paragraph overhead."""
    c.setFont(font, size)
    c.setFillColor(color)
    words, line, cursor = s.split(), "", y
    for w in words:
        trial = f"{line} {w}".strip()
        if pdfmetrics.stringWidth(trial, font, size) <= width:
            line = trial
        else:
            c.drawString(x, cursor, line)
            cursor -= leading
            line = w
    if line:
        c.drawString(x, cursor, line)
        cursor -= leading
    return cursor


def donut(c, cx, cy, r_out, r_in, segments):
    """Vector donut. segments = [(share, colour)] summing to 1.0."""
    start = 90.0
    for share, colour in segments:
        extent = -360.0 * share
        c.setFillColor(colour)
        c.setStrokeColor(colour)
        p = c.beginPath()
        p.moveTo(cx, cy)
        p.arcTo(cx - r_out, cy - r_out, cx + r_out, cy + r_out, start, extent)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        start += extent
    # Punch the hole with a page-coloured disc.
    c.setFillColor(WHITE)
    c.circle(cx, cy, r_in, fill=1, stroke=0)


def build() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sans, serif = register_fonts()
    c = canvas.Canvas(str(OUT), pagesize=A4)

    c.setTitle("Модернизация сети накопителей — резюме программы")
    c.setAuthor("Департамент стратегического развития")
    c.setSubject("Инвестиционная программа 2026–2030")
    c.setCreator("doc-agent showcase")

    M = 16 * mm
    CW = W - 2 * M

    # ------------------------------------------------------------ header
    c.setFillColor(NAVY)
    c.rect(0, H - 34 * mm, W, 34 * mm, fill=1, stroke=0)
    # Accent wedge, drawn as a path so it stays crisp at any zoom.
    c.setFillColor(HexColor("#2C3A7A"))
    p = c.beginPath()
    p.moveTo(W - 62 * mm, H)
    p.lineTo(W, H)
    p.lineTo(W, H - 34 * mm)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    text(c, M, H - 13 * mm, "РЕЗЮМЕ ИНВЕСТИЦИОННОЙ ПРОГРАММЫ",
         font="Inter-Bold", size=8.5, color=HexColor("#8FA6D8"))
    text(c, M, H - 21 * mm, "Модернизация сети накопителей энергии",
         font="Inter-Bold", size=17, color=WHITE)
    text(c, M, H - 28 * mm, "Горизонт 2026–2030 · Запрос 4,35 млрд ₽ · Конфиденциально",
         font="Inter", size=9, color=HexColor("#CADCFC"))
    c.bookmarkPage("top")
    c.addOutlineEntry("Резюме программы", "top", level=0)

    y = H - 34 * mm - 12 * mm

    # -------------------------------------------------------------- KPIs
    kpis = [
        ("4,35", "млрд ₽", "Капитальные затраты", NAVY),
        ("13,6", "%", "IRR проекта", GREEN),
        ("12,1", "%", "Стоимость капитала", ACCENT),
        ("4,1", "года", "Срок окупаемости", NAVY),
    ]
    bw = (CW - 3 * 4 * mm) / 4
    for i, (val, unit, label, colour) in enumerate(kpis):
        x = M + i * (bw + 4 * mm)
        c.setFillColor(LIGHT)
        c.roundRect(x, y - 20 * mm, bw, 20 * mm, 2 * mm, fill=1, stroke=0)
        c.setFillColor(colour)
        c.rect(x, y - 20 * mm, 1.2 * mm, 20 * mm, fill=1, stroke=0)
        text(c, x + 5 * mm, y - 9 * mm, val, font="Inter-Bold", size=19, color=colour)
        vw = pdfmetrics.stringWidth(val, "Inter-Bold", 19)
        text(c, x + 5 * mm + vw + 1.5 * mm, y - 9 * mm, unit, font="Inter", size=8, color=MUTED)
        text(c, x + 5 * mm, y - 15.5 * mm, label, font="Inter", size=8, color=INK)
    y -= 20 * mm + 9 * mm

    # ------------------------------------------------------- two columns
    col_w = (CW - 8 * mm) / 2
    left_x, right_x = M, M + col_w + 8 * mm
    col_top = y

    # ---- left: the ask
    text(c, left_x, y, "Суть предложения", font="Inter-Bold", size=11, color=NAVY)
    y -= 3 * mm
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.2)
    c.line(left_x, y, left_x + 14 * mm, y)
    y -= 6 * mm
    y = wrap(
        c, left_x, y,
        "Программа заменяет десять площадок хранения энергии на контейнерные и "
        "модульные системы совокупной мощностью 252 МВт·ч. Ввод распределён на "
        "четыре года, максимум капитальных затрат приходится на 2026 год.",
        col_w, font="PTSerif", size=9.2, color=INK, leading=13,
    )
    y -= 3 * mm
    y = wrap(
        c, left_x, y,
        "Базовый сценарий создаёт стоимость, но запас прочности узкий: спред "
        "IRR к стоимости капитала составляет 1,5 п.п., а NPV без терминальной "
        "стоимости — 83 млн ₽.",
        col_w, font="PTSerif", size=9.2, color=INK, leading=13,
    )
    y -= 4 * mm

    text(c, left_x, y, "Условия выполнимости", font="Inter-Bold", size=11, color=NAVY)
    y -= 6 * mm
    for n, cond in [
        ("01", "Рамочный договор подписан до 31 октября 2026 года"),
        ("02", "Валовая маржа не ниже 41,2 % в 2026 году"),
        ("03", "Стоимость долга не выше 11,5 % на горизонте"),
    ]:
        text(c, left_x, y, n, font="Inter-Bold", size=9, color=ACCENT)
        end = wrap(c, left_x + 8 * mm, y, cond, col_w - 8 * mm,
                   font="Inter", size=8.8, color=INK, leading=11.5)
        y = end - 1.5 * mm

    left_bottom = y

    # ---- right: revenue split donut
    y = col_top
    text(c, right_x, y, "Выручка 2026 по сегментам", font="Inter-Bold", size=11, color=NAVY)
    y -= 3 * mm
    c.setStrokeColor(ACCENT)
    c.line(right_x, y, right_x + 14 * mm, y)
    y -= 30 * mm

    segs = [(0.551, NAVY), (0.388, ACCENT), (0.061, HexColor("#A9BDDB"))]
    donut(c, right_x + 18 * mm, y + 4 * mm, 16 * mm, 9 * mm, segs)

    legend = [
        ("Промышленный", "55,1 %", NAVY),
        ("Коммерческий", "38,8 %", ACCENT),
        ("Розничный", "6,1 %", HexColor("#A9BDDB")),
    ]
    ly = y + 14 * mm
    for label, share, colour in legend:
        c.setFillColor(colour)
        c.rect(right_x + 38 * mm, ly - 1 * mm, 2.6 * mm, 2.6 * mm, fill=1, stroke=0)
        text(c, right_x + 42.5 * mm, ly, label, font="Inter", size=8, color=INK)
        text(c, right_x + col_w, ly, share, font="Inter-Bold", size=8,
             color=colour, align="right")
        ly -= 6.5 * mm

    y -= 22 * mm
    right_bottom = y

    # ------------------------------------------------- scenarios table
    y = min(left_bottom, right_bottom) - 4 * mm
    text(c, M, y, "Сценарии", font="Inter-Bold", size=11, color=NAVY)
    y -= 7 * mm

    cols = [CW * 0.28, CW * 0.16, CW * 0.18, CW * 0.14, CW * 0.24]
    xs, acc = [], M
    for w in cols:
        xs.append(acc)
        acc += w

    rh = 8 * mm
    c.setFillColor(NAVY)
    c.rect(M, y - rh, CW, rh, fill=1, stroke=0)
    heads = ["Сценарий", "Рост выручки", "NPV, млн ₽", "IRR", "Вывод"]
    for i, h in enumerate(heads):
        if i == 0:
            text(c, xs[i] + 3 * mm, y - rh + 2.8 * mm, h, font="Inter-Bold", size=8.5, color=WHITE)
        else:
            text(c, xs[i] + cols[i] - 3 * mm, y - rh + 2.8 * mm, h,
                 font="Inter-Bold", size=8.5, color=WHITE, align="right")
    y -= rh

    rows = [
        ("Пессимистичный", "8,0 %", "−412", "9,1 %", "Не проходит порог", CORAL),
        ("Базовый", "16,5 %", "83", "13,6 %", "Проходит", GREEN),
        ("Оптимистичный", "24,0 %", "612", "18,4 %", "Проходит с запасом", GREEN),
    ]
    for i, (name, growth, npv, irr, verdict, vcol) in enumerate(rows):
        if i == 1:
            c.setFillColor(HexColor("#EAF1E9"))
            c.rect(M, y - rh, CW, rh, fill=1, stroke=0)
        elif i % 2 == 0:
            c.setFillColor(LIGHT)
            c.rect(M, y - rh, CW, rh, fill=1, stroke=0)
        bold = "Inter-Bold" if i == 1 else "Inter"
        text(c, xs[0] + 3 * mm, y - rh + 2.8 * mm, name, font=bold, size=8.5, color=INK)
        for j, v in enumerate([growth, npv, irr], start=1):
            text(c, xs[j] + cols[j] - 3 * mm, y - rh + 2.8 * mm, v,
                 font=bold, size=8.5, color=INK, align="right")
        text(c, xs[4] + cols[4] - 3 * mm, y - rh + 2.8 * mm, verdict,
             font=bold, size=8.5, color=vcol, align="right")
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(M, y - rh, M + CW, y - rh)
        y -= rh

    y -= 8 * mm

    # ----------------------------------------------------- decision box
    box_h = 22 * mm
    c.setFillColor(NAVY)
    c.roundRect(M, y - box_h, CW, box_h, 2 * mm, fill=1, stroke=0)
    text(c, M + 6 * mm, y - 7 * mm, "ЗАПРОС К СОВЕТУ ДИРЕКТОРОВ",
         font="Inter-Bold", size=8.5, color=HexColor("#8FA6D8"))
    wrap(c, M + 6 * mm, y - 12.5 * mm,
         "Утвердить программу в объёме 4,35 млрд ₽ и делегировать правлению "
         "подписание рамочного договора с поставщиком до 31 октября 2026 года.",
         CW - 12 * mm, font="Inter", size=10, color=WHITE, leading=13)
    y -= box_h + 9 * mm

    # ------------------------------------------- roll-out + risk register
    # Without this block the lower third of the page is empty, which on a
    # leave-behind reads as "we ran out of things to say".
    half = (CW - 8 * mm) / 2

    text(c, M, y, "Ввод мощностей, МВт·ч", font="Inter-Bold", size=10, color=NAVY)
    by = y - 7 * mm
    schedule = [("2026", 74, NAVY), ("2027", 86, NAVY),
                ("2028", 48, ACCENT), ("2029", 30, ACCENT), ("2030", 14, HexColor("#A9BDDB"))]
    peak = max(v for _, v, _ in schedule)
    bar_max = half - 26 * mm
    for label, value, colour in schedule:
        text(c, M, by, label, font="Inter", size=8, color=MUTED)
        c.setFillColor(LIGHT)
        c.rect(M + 11 * mm, by - 0.8 * mm, bar_max, 3.4 * mm, fill=1, stroke=0)
        c.setFillColor(colour)
        c.rect(M + 11 * mm, by - 0.8 * mm, bar_max * value / peak, 3.4 * mm, fill=1, stroke=0)
        text(c, M + half, by, str(value), font="Inter-Bold", size=8,
             color=INK, align="right")
        by -= 6.5 * mm

    rx = M + half + 8 * mm
    text(c, rx, y, "Ключевые риски", font="Inter-Bold", size=10, color=NAVY)
    ry = y - 7 * mm
    risks = [
        ("Срыв сроков поставки", "высокий", CORAL),
        ("Рост стоимости долга", "высокий", CORAL),
        ("Падение спроса в рознице", "средний", AMBER),
        ("Изменение тарифов", "низкий", GREEN),
    ]
    for name, level, colour in risks:
        c.setFillColor(colour)
        c.circle(rx + 1.4 * mm, ry + 1.2 * mm, 1.4 * mm, fill=1, stroke=0)
        text(c, rx + 5 * mm, ry, name, font="Inter", size=8.2, color=INK)
        badge_w = pdfmetrics.stringWidth(level, "Inter-Bold", 7) + 5 * mm
        c.setFillColor(colour)
        c.roundRect(rx + half - badge_w, ry - 1.2 * mm, badge_w, 4.6 * mm,
                    1 * mm, fill=1, stroke=0)
        text(c, rx + half - badge_w / 2, ry, level,
             font="Inter-Bold", size=7, color=WHITE, align="center")
        ry -= 6.5 * mm

    # ------------------------------------------------------------ footer
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.line(M, 18 * mm, M + CW, 18 * mm)
    text(c, M, 13 * mm,
         "Департамент стратегического развития · 16 августа 2026 года",
         font="Inter", size=7.5, color=MUTED)

    link_label = "Полная финансовая модель"
    text(c, M + CW, 13 * mm, link_label, font="Inter", size=7.5, color=ACCENT, align="right")
    lw = pdfmetrics.stringWidth(link_label, "Inter", 7.5)
    # A real clickable annotation, not blue text pretending to be a link.
    c.linkURL(
        "https://www.consultant.ru/",
        (M + CW - lw, 11.5 * mm, M + CW, 16 * mm),
        relative=0, thickness=0,
    )

    c.showPage()
    c.save()
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"wrote {path.relative_to(REPO)}")
