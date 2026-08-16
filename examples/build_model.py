#!/usr/bin/env python3
"""
Worked example: a small financial model with real formulas, the house colour
conventions, and a recalculation pass.

    .venv/bin/python examples/build_model.py

Then the two steps that actually matter:

    .venv/bin/python tools/recalc.py .workdir/Финансовая_модель.xlsx
    .venv/bin/python tools/validate.py .workdir/Финансовая_модель.xlsx
    .venv/bin/python tools/render.py  .workdir/Финансовая_модель.xlsx -o .workdir/qa

Note what is *not* here: no computed constants. Every derived number is a
formula, so the sheet still works when someone changes an assumption. That is
the whole point of delivering a spreadsheet rather than a table.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / ".workdir" / "Финансовая_модель.xlsx"

# House conventions (see skills/xlsx/SKILL.md)
BLUE = "FF0000FF"     # hardcoded input
BLACK = "FF1F2933"    # formula
YELLOW = "FFFFFF00"   # fill in me
HEADER_BG = "FF1E3A5F"
BAND = "FFF4F6F9"

MONEY = '#,##0;(#,##0);-'
PCT = '0.0%'
YEARS = ["2026", "2027", "2028", "2029", "2030"]

thin = Side(style="thin", color="FFD5D9E0")
border = Border(left=thin, right=thin, top=thin, bottom=thin)


def header(cell, text: str) -> None:
    cell.value = text
    cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFFFF")
    cell.fill = PatternFill("solid", fgColor=HEADER_BG)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = border


def label(cell, text: str, bold: bool = False, indent: int = 0) -> None:
    cell.value = text
    cell.font = Font(name="Arial", size=10, bold=bold, color=BLACK)
    cell.alignment = Alignment(indent=indent)
    cell.border = border


def inp(cell, value, fmt: str = MONEY) -> None:
    """A hardcoded input: blue text, yellow fill — the user may edit these."""
    cell.value = value
    cell.font = Font(name="Arial", size=10, color=BLUE)
    cell.fill = PatternFill("solid", fgColor=YELLOW)
    cell.number_format = fmt
    cell.border = border


def formula(cell, expr: str, fmt: str = MONEY, bold: bool = False) -> None:
    cell.value = expr
    cell.font = Font(name="Arial", size=10, bold=bold, color=BLACK)
    cell.number_format = fmt
    cell.border = border


def build() -> Path:
    wb = Workbook()

    # ----------------------------------------------------------- assumptions
    ws = wb.active
    ws.title = "Допущения"
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 16

    ws["A1"] = "Допущения модели"
    ws["A1"].font = Font(name="Arial", size=13, bold=True, color=BLACK)
    ws["A2"] = "Жёлтые ячейки — вводные, их можно менять. Остальное считается формулами."
    ws["A2"].font = Font(name="Arial", size=9, italic=True, color="FF667085")

    rows = [
        ("Выручка базового года, млн ₽", 1250, MONEY),
        ("Темп роста выручки, % в год", 0.18, PCT),
        ("Валовая маржа, %", 0.34, PCT),
        ("Операционные расходы, % от выручки", 0.19, PCT),
        ("Ставка налога, %", 0.20, PCT),
        ("Ставка дисконтирования, %", 0.15, PCT),
    ]
    for offset, (name, value, fmt) in enumerate(rows):
        row = 4 + offset
        label(ws.cell(row=row, column=1), name)
        inp(ws.cell(row=row, column=2), value, fmt)

    ws["A11"] = "Источник: управленческая отчётность за 2025 год; темп роста — план развития."
    ws["A11"].font = Font(name="Arial", size=9, italic=True, color="FF667085")

    # --------------------------------------------------------------- forecast
    fc = wb.create_sheet("Прогноз")
    fc.column_dimensions["A"].width = 34
    for i in range(len(YEARS)):
        fc.column_dimensions[get_column_letter(2 + i)].width = 14

    fc["A1"] = "Финансовый прогноз, млн ₽"
    fc["A1"].font = Font(name="Arial", size=13, bold=True, color=BLACK)

    header(fc.cell(row=3, column=1), "Показатель")
    for i, year in enumerate(YEARS):
        # Years as text, or they render as "2 026" under a thousands format.
        head = fc.cell(row=3, column=2 + i)
        header(head, year)
        head.number_format = "@"

    def line(row: int, name: str, make: callable, fmt: str = MONEY,
             bold: bool = False, indent: int = 0) -> None:
        label(fc.cell(row=row, column=1), name, bold=bold, indent=indent)
        for i in range(len(YEARS)):
            col = get_column_letter(2 + i)
            formula(fc.cell(row=row, column=2 + i), make(i, col), fmt, bold)
        if row % 2 == 0:
            for i in range(len(YEARS) + 1):
                fc.cell(row=row, column=1 + i).fill = PatternFill("solid", fgColor=BAND)

    # Every assumption is referenced, never inlined.
    line(4, "Выручка",
         lambda i, c: "=Допущения!$B$4" if i == 0
         else f"={get_column_letter(1 + i)}4*(1+Допущения!$B$5)")
    line(5, "Себестоимость", lambda i, c: f"=-{c}4*(1-Допущения!$B$6)", indent=1)
    line(6, "Валовая прибыль", lambda i, c: f"={c}4+{c}5", bold=True)
    line(7, "Операционные расходы", lambda i, c: f"=-{c}4*Допущения!$B$7", indent=1)
    line(8, "EBIT", lambda i, c: f"={c}6+{c}7", bold=True)
    line(9, "Налог", lambda i, c: f"=-MAX(0,{c}8)*Допущения!$B$8", indent=1)
    line(10, "Чистая прибыль", lambda i, c: f"={c}8+{c}9", bold=True)
    line(12, "Рентабельность по EBIT",
         lambda i, c: f"=IFERROR({c}8/{c}4,0)", fmt=PCT)   # guard the denominator
    line(13, "Дисконтирующий множитель",
         lambda i, c: f"=1/(1+Допущения!$B$9)^{i + 1}", fmt="0.000")
    line(14, "Дисконтированная прибыль", lambda i, c: f"={c}10*{c}13", bold=True)

    last = get_column_letter(1 + len(YEARS))
    label(fc.cell(row=16, column=1), "NPV прибыли за период", bold=True)
    formula(fc.cell(row=16, column=2), f"=SUM(B14:{last}14)", MONEY, bold=True)

    fc["A18"] = "Все производные значения — формулы. Изменение допущения пересчитывает прогноз."
    fc["A18"].font = Font(name="Arial", size=9, italic=True, color="FF667085")

    fc.freeze_panes = "B4"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    return OUT


def main() -> int:
    path = build()
    print(f"wrote {path}")

    # openpyxl leaves formulas with no cached value: without this the file
    # reads as empty to pandas, to previews, and to anything but Excel.
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "recalc.py"), str(path)],
        capture_output=True, text=True,
    )
    print(result.stdout.strip() or result.stderr.strip())
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
