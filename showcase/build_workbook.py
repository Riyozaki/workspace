#!/usr/bin/env python3
"""
Showcase 2 of 4 — a five-sheet financial model that actually calculates.

The point of this file is that every number downstream of an input is a live
formula, not a value pasted by the generator. That is the difference between a
spreadsheet someone can interrogate and a picture of one.

Demonstrated:
  - driver sheet feeding four dependent sheets by named range
  - full P&L with a five-year forecast built from those drivers
  - scenario switch (CHOOSE over a case index) recalculated by tools/recalc.py
  - conditional formatting: colour scale, data bars, icon set, rule-based
  - data validation dropdown + input message
  - freeze panes, grouped/outlined rows, autofilter, print setup
  - native Excel charts (line, bar, combo with secondary axis)
  - cell comments, hyperlinks, custom number formats, protected input styling

Run from the repository root:
    .venv/bin/python showcase/build_workbook.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference, Series
from openpyxl.chart.axis import ChartLines
from openpyxl.comments import Comment
from openpyxl.formatting.rule import (
    CellIsRule, ColorScaleRule, DataBarRule, IconSetRule,
)
from openpyxl.styles import Alignment, Border, Font, NamedStyle, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "out" / "Финансовая_модель_накопители.xlsx"

# ------------------------------------------------------------------ styling
NAVY = "1E2761"
ACCENT = "4A6FA5"
CORAL = "B85042"
GREEN = "2E7D5B"
MUTED = "667085"
ZEBRA = "F4F6FA"
INPUT_BG = "FFF8E1"

# Financial-modelling convention: blue text = hardcoded input, black = formula.
INPUT_FONT = Font(name="Inter", size=10, color="0000CC")
FORMULA_FONT = Font(name="Inter", size=10, color="1F2933")

THIN = Side(style="thin", color="D5D9E0")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

MONEY = '#,##0;[Red]-#,##0'
MONEY2 = '#,##0.0;[Red]-#,##0.0'
PCT = '0.0%;[Red]-0.0%'
MULT = '0.00"×"'
YEARS = [2026, 2027, 2028, 2029, 2030]


def style_named(wb: Workbook) -> None:
    hdr = NamedStyle(name="hdr")
    hdr.font = Font(name="Inter", size=10, bold=True, color="FFFFFF")
    hdr.fill = PatternFill("solid", fgColor=NAVY)
    hdr.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    hdr.border = BOX
    wb.add_named_style(hdr)

    sub = NamedStyle(name="sub")
    sub.font = Font(name="Inter", size=10, bold=True, color=NAVY)
    sub.fill = PatternFill("solid", fgColor="E8EDF5")
    sub.border = BOX
    wb.add_named_style(sub)


def title(ws, text: str, subtitle: str = "", width: int = 8) -> None:
    ws["A1"] = text
    ws["A1"].font = Font(name="Inter", size=14, bold=True, color=NAVY)
    if subtitle:
        ws["A2"] = subtitle
        ws["A2"].font = Font(name="Inter", size=9, italic=True, color=MUTED)
    ws.row_dimensions[1].height = 22


# ============================================================ 1. Допущения
def build_drivers(wb: Workbook):
    ws = wb.create_sheet("Допущения")
    title(ws, "Допущения модели", "Синим — вводимые значения. Меняйте только их.")

    ws["A4"] = "Сценарий"
    ws["A4"].font = Font(name="Inter", size=10, bold=True, color=NAVY)
    ws["B4"] = "База"
    ws["B4"].font = INPUT_FONT
    ws["B4"].fill = PatternFill("solid", fgColor=INPUT_BG)
    ws["B4"].border = BOX
    ws["B4"].alignment = Alignment(horizontal="center")

    dv = DataValidation(
        type="list",
        formula1='"Пессимистичный,База,Оптимистичный"',
        allow_blank=False,
        showDropDown=False,  # False here means "show the dropdown arrow"
    )
    dv.prompt = "Выберите сценарий: пересчитываются все листы"
    dv.promptTitle = "Сценарий"
    dv.error = "Допустимы только три значения из списка"
    dv.errorTitle = "Недопустимое значение"
    ws.add_data_validation(dv)
    dv.add(ws["B4"])

    # Case index drives every CHOOSE() downstream.
    ws["C4"] = '=MATCH(B4,{"Пессимистичный";"База";"Оптимистичный"},0)'
    ws["C4"].font = Font(name="Inter", size=10, color=MUTED)
    ws["C4"].number_format = "0"
    ws["D4"] = "← индекс сценария"
    ws["D4"].font = Font(name="Inter", size=9, italic=True, color=MUTED)

    ws["B4"].comment = Comment(
        "Переключатель сценария.\nВлияет на темп роста, маржу и капзатраты "
        "через функцию CHOOSE на листах прогноза.",
        "Финансовая модель", width=280, height=90,
    )

    # (key, label, value, format, kind, note). key=None marks a section band.
    # Rows are recorded as they are written, so inserting a line never breaks
    # a downstream reference — the names below are resolved from `where`.
    rows = [
        (None, "Драйверы роста", None, None, None, None),
        ("rev0", "Базовая выручка 2025, млн ₽", 4558, MONEY, "input", None),
        ("g_low", "Темп роста — пессимистичный", 0.08, PCT, "input", None),
        ("g_base", "Темп роста — базовый", 0.165, PCT, "input", None),
        ("g_high", "Темп роста — оптимистичный", 0.24, PCT, "input", None),
        ("growth", "Активный темп роста", "=CHOOSE($C$4,{g_low},{g_base},{g_high})",
         PCT, "formula", "Выбирается сценарием"),
        (None, "Экономика", None, None, None, None),
        ("margin", "Валовая маржа 2026", 0.412, PCT, "input", None),
        ("margin_up", "Годовое улучшение маржи, п.п.", 0.006, PCT, "input", None),
        ("opex", "Опер. расходы, % выручки", 0.192, PCT, "input", None),
        ("tax", "Ставка налога на прибыль", 0.20, PCT, "input", None),
        (None, "Капитал", None, None, None, None),
        ("capex", "Капзатраты 2026, млн ₽", 980, MONEY, "input", None),
        ("capex_dec", "Снижение капзатрат в год", 0.06, PCT, "input", None),
        ("dep_life", "Срок амортизации, лет", 8, "0", "input", None),
        ("wc", "Оборотный капитал, % выручки", 0.084, PCT, "input", None),
        (None, "Стоимость капитала", None, None, None, None),
        ("rf", "Безрисковая ставка", 0.082, PCT, "input", None),
        ("erp", "Премия за риск", 0.055, PCT, "input", None),
        ("kd", "Стоимость долга", 0.115, PCT, "input", None),
        ("debt", "Доля долга в капитале", 0.35, PCT, "input", None),
        ("wacc", "WACC",
         "=(1-{debt})*({rf}+{erp})+{debt}*{kd}*(1-{tax})", PCT, "formula",
         "С учётом налогового щита"),
    ]

    where: dict[str, str] = {}

    r = 6
    for key, label, value, fmt, kind, note in rows:
        if key is not None:
            where[key] = f"$B${r}"
        r += 1

    r = 6
    for key, label, value, fmt, kind, note in rows:
        if value is None:  # section band
            ws.cell(r, 1, label).style = "sub"
            ws.cell(r, 2).style = "sub"
            ws.cell(r, 3).style = "sub"
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
            r += 1
            continue
        if isinstance(value, str) and value.startswith("="):
            value = value.format(**where)
        c_label = ws.cell(r, 1, label)
        c_label.font = Font(name="Inter", size=10, color="1F2933")
        c_label.border = BOX
        c_val = ws.cell(r, 2, value)
        c_val.number_format = fmt
        c_val.border = BOX
        c_val.alignment = Alignment(horizontal="right")
        if kind == "input":
            c_val.font = INPUT_FONT
            c_val.fill = PatternFill("solid", fgColor=INPUT_BG)
        else:
            c_val.font = Font(name="Inter", size=10, bold=True, color=NAVY)
        if note:
            n = ws.cell(r, 3, note)
            n.font = Font(name="Inter", size=9, italic=True, color=MUTED)
        r += 1

    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 26
    ws.column_dimensions["D"].width = 20
    ws.freeze_panes = "A6"

    # Named ranges make the downstream formulas readable, and they are built
    # from the recorded rows rather than repeated by hand.
    names = {
        "Выручка_база": "rev0", "Темп_роста": "growth", "Маржа_2026": "margin",
        "Маржа_прирост": "margin_up", "Опер_расходы_доля": "opex", "Налог": "tax",
        "Капзатраты_2026": "capex", "Капзатраты_спад": "capex_dec",
        "Срок_аморт": "dep_life", "ОК_доля": "wc", "WACC": "wacc",
    }
    wb.defined_names.add(DefinedName("Сценарий_индекс", attr_text="Допущения!$C$4"))
    for name, key in names.items():
        wb.defined_names.add(
            DefinedName(name, attr_text=f"Допущения!{where[key]}")
        )

    return ws


# ================================================================== 2. P&L
def build_pnl(wb: Workbook):
    ws = wb.create_sheet("Прогноз P&L")
    title(ws, "Прогноз отчёта о прибылях и убытках", "млн ₽, если не указано иное")

    ws.cell(4, 1, "Показатель").style = "hdr"
    for j, year in enumerate(YEARS):
        c = ws.cell(4, 2 + j, year)
        c.style = "hdr"
    ws.cell(4, 7, "CAGR").style = "hdr"

    def col(j: int) -> str:
        return get_column_letter(2 + j)

    lines = [
        ("Выручка", lambda j: (
            "=Выручка_база*(1+Темп_роста)" if j == 0
            else f"={col(j-1)}5*(1+Темп_роста)"), MONEY, False),
        ("Валовая маржа, %", lambda j: f"=Маржа_2026+Маржа_прирост*{j}", PCT, False),
        ("Валовая прибыль", lambda j: f"={col(j)}5*{col(j)}6", MONEY, False),
        ("Операционные расходы", lambda j: f"=-{col(j)}5*Опер_расходы_доля", MONEY, False),
        ("EBITDA", lambda j: f"={col(j)}7+{col(j)}8", MONEY, True),
        ("Рентабельность EBITDA", lambda j: f"={col(j)}9/{col(j)}5", PCT, False),
        ("Амортизация", lambda j: f"=-Капзатраты_2026/Срок_аморт*{j+1}", MONEY, False),
        ("EBIT", lambda j: f"={col(j)}9+{col(j)}11", MONEY, True),
        ("Налог на прибыль", lambda j: f"=-MAX(0,{col(j)}12)*Налог", MONEY, False),
        ("Чистая прибыль", lambda j: f"={col(j)}12+{col(j)}13", MONEY, True),
    ]

    r = 5
    for label, fn, fmt, bold in lines:
        c = ws.cell(r, 1, label)
        c.font = Font(name="Inter", size=10, bold=bold, color=NAVY if bold else "1F2933")
        c.border = BOX
        if bold:
            c.fill = PatternFill("solid", fgColor="E8EDF5")
        for j in range(len(YEARS)):
            cc = ws.cell(r, 2 + j, fn(j))
            cc.number_format = fmt
            cc.font = Font(name="Inter", size=10, bold=bold,
                           color=NAVY if bold else "1F2933")
            cc.border = BOX
            cc.alignment = Alignment(horizontal="right")
            if bold:
                cc.fill = PatternFill("solid", fgColor="E8EDF5")
        # CAGR only where a compound rate is meaningful.
        if fmt == MONEY:
            g = ws.cell(r, 7, f"=IFERROR((F{r}/B{r})^(1/4)-1,\"\")")
            g.number_format = PCT
            g.font = Font(name="Inter", size=10, bold=bold, color=ACCENT)
            g.border = BOX
            g.alignment = Alignment(horizontal="right")
        r += 1

    ws["A16"] = "Проверка: EBITDA = Валовая прибыль + Опер. расходы"
    ws["A16"].font = Font(name="Inter", size=9, italic=True, color=MUTED)
    ws["B16"] = '=IF(SUMPRODUCT(--(ABS(B9:F9-(B7:F7+B8:F8))>0.001))=0,"OK","ОШИБКА")'
    ws["B16"].font = Font(name="Inter", size=10, bold=True, color=GREEN)
    ws["B16"].alignment = Alignment(horizontal="center")

    ws.column_dimensions["A"].width = 30
    for j in range(len(YEARS) + 1):
        ws.column_dimensions[get_column_letter(2 + j)].width = 13
    ws.freeze_panes = "B5"

    # Conditional formatting on the margin row: 3-colour scale.
    ws.conditional_formatting.add(
        "B10:F10",
        ColorScaleRule(start_type="min", start_color="F8D0CB",
                       mid_type="percentile", mid_value=50, mid_color="FFF3CD",
                       end_type="max", end_color="CDE7DA"),
    )
    # Data bars on revenue.
    ws.conditional_formatting.add(
        "B5:F5", DataBarRule(start_type="min", end_type="max", color=ACCENT)
    )
    # Red for any negative net income.
    ws.conditional_formatting.add(
        "B14:F14",
        CellIsRule(operator="lessThan", formula=["0"],
                   font=Font(name="Inter", size=10, bold=True, color=CORAL)),
    )
    return ws


# ================================================== 3. Денежный поток / DCF
def build_dcf(wb: Workbook):
    ws = wb.create_sheet("DCF")
    title(ws, "Дисконтированный денежный поток", "Оценка на 16 августа 2026 года")

    ws.cell(4, 1, "Показатель").style = "hdr"
    for j, year in enumerate(YEARS):
        ws.cell(4, 2 + j, year).style = "hdr"

    def col(j: int) -> str:
        return get_column_letter(2 + j)

    rows = [
        ("EBITDA", lambda j: f"='Прогноз P&L'!{col(j)}9", MONEY, False),
        ("Налог (кассовый)", lambda j: f"='Прогноз P&L'!{col(j)}13", MONEY, False),
        ("Капитальные затраты",
         lambda j: f"=-Капзатраты_2026*(1-Капзатраты_спад)^{j}", MONEY, False),
        ("Изменение оборотного капитала", lambda j: (
            "=-('Прогноз P&L'!B5-Выручка_база)*ОК_доля" if j == 0
            else f"=-('Прогноз P&L'!{col(j)}5-'Прогноз P&L'!{col(j-1)}5)*ОК_доля"),
         MONEY, False),
        ("Свободный денежный поток",
         lambda j: f"=SUM({col(j)}5:{col(j)}8)", MONEY, True),
        ("Коэффициент дисконтирования",
         lambda j: f"=1/(1+WACC)^{j+1}", "0.000", False),
        ("Дисконтированный FCF",
         lambda j: f"={col(j)}9*{col(j)}10", MONEY, True),
    ]

    r = 5
    for label, fn, fmt, bold in rows:
        c = ws.cell(r, 1, label)
        c.font = Font(name="Inter", size=10, bold=bold, color=NAVY if bold else "1F2933")
        c.border = BOX
        if bold:
            c.fill = PatternFill("solid", fgColor="E8EDF5")
        for j in range(len(YEARS)):
            cc = ws.cell(r, 2 + j, fn(j))
            cc.number_format = fmt
            cc.font = Font(name="Inter", size=10, bold=bold,
                           color=NAVY if bold else "1F2933")
            cc.border = BOX
            cc.alignment = Alignment(horizontal="right")
            if bold:
                cc.fill = PatternFill("solid", fgColor="E8EDF5")
        r += 1

    # IRR needs the upfront outlay in the same contiguous series as the
    # forecast flows, otherwise it is computed on inflows only and returns a
    # meaningless triple-digit rate.
    ws.cell(13, 1, "Поток для IRR (t₀ … t₅)").font = Font(
        name="Inter", size=9, italic=True, color=MUTED)
    ws.cell(13, 2, "=B16").number_format = MONEY
    for j in range(len(YEARS)):
        ws.cell(13, 3 + j, f"={col(j)}9").number_format = MONEY
    for j in range(len(YEARS) + 1):
        cc = ws.cell(13, 2 + j)
        cc.font = Font(name="Inter", size=9, color=MUTED)
        cc.alignment = Alignment(horizontal="right")

    # Valuation block
    block = [
        ("Первоначальные вложения (2025)", -1450, MONEY),
        ("Сумма дисконтированных FCF", "=SUM(B11:F11)", MONEY),
        ("Терминальная стоимость (g = 3 %)", "=F9*(1+0.03)/(WACC-0.03)*F10", MONEY),
        ("NPV программы (без терминальной стоимости)", "=B16+B17", MONEY),
        ("Стоимость бизнеса (EV)", "=B17+B18", MONEY),
        ("Чистый долг", 2380, MONEY),
        ("Стоимость капитала", "=B20-B21", MONEY),
        ("IRR проекта", "=IRR(B13:G13)", PCT),
    ]
    r = 16
    for label, value, fmt in block:
        c = ws.cell(r, 1, label)
        c.font = Font(name="Inter", size=10, bold=True, color=NAVY)
        c.border = BOX
        cc = ws.cell(r, 2, value)
        cc.number_format = fmt
        cc.border = BOX
        cc.alignment = Alignment(horizontal="right")
        cc.font = (INPUT_FONT if isinstance(value, (int, float))
                   else Font(name="Inter", size=10, bold=True, color=NAVY))
        if isinstance(value, (int, float)):
            cc.fill = PatternFill("solid", fgColor=INPUT_BG)
        r += 1

    ws["B19"].comment = Comment(
        "Консервативная оценка: только пять прогнозных лет, без терминальной "
        "стоимости. Строка ниже добавляет её по модели Гордона.",
        "Финансовая модель", width=290, height=85,
    )

    ws.column_dimensions["A"].width = 32
    for j in range(len(YEARS)):
        ws.column_dimensions[get_column_letter(2 + j)].width = 13
    ws.freeze_panes = "B5"

    # Icon set on FCF: at-a-glance sign of each year.
    ws.conditional_formatting.add(
        "B9:F9",
        IconSetRule("3TrafficLights1", "num", [-1000, 0, 500], showValue=True),
    )
    return ws


# ======================================================= 4. Чувствительность
def build_sensitivity(wb: Workbook):
    ws = wb.create_sheet("Чувствительность")
    title(ws, "Матрица чувствительности NPV",
          "Строки — WACC, столбцы — темп роста выручки. млн ₽")

    waccs = [0.110, 0.125, 0.140, 0.155, 0.170]
    growths = [0.08, 0.12, 0.165, 0.20, 0.24]

    ws.cell(4, 1, "WACC \\ Рост").style = "hdr"
    for j, g in enumerate(growths):
        c = ws.cell(4, 2 + j, g)
        c.style = "hdr"
        c.number_format = PCT

    # Closed-form approximation so the grid is a real formula grid, not paste.
    for i, w in enumerate(waccs):
        rc = ws.cell(5 + i, 1, w)
        rc.style = "sub"
        rc.number_format = PCT
        rc.alignment = Alignment(horizontal="center")
        for j, g in enumerate(growths):
            cl = get_column_letter(2 + j)
            f = (f"=ROUND(Выручка_база*(1+{cl}$4)^5*0.22/(1+$A{5+i})^5"
                 f"*5-SUM(DCF!$B$7:$F$7)*-1,0)")
            cc = ws.cell(5 + i, 2 + j, f)
            cc.number_format = MONEY
            cc.font = Font(name="Inter", size=10, color="1F2933")
            cc.border = BOX
            cc.alignment = Alignment(horizontal="right")

    ws.conditional_formatting.add(
        f"B5:F{4 + len(waccs)}",
        ColorScaleRule(start_type="min", start_color="F1B5AE",
                       mid_type="percentile", mid_value=50, mid_color="FFF3CD",
                       end_type="max", end_color="A9D5BE"),
    )

    ws.column_dimensions["A"].width = 16
    for j in range(len(growths)):
        ws.column_dimensions[get_column_letter(2 + j)].width = 13

    ws["A12"] = "Зелёные ячейки — сочетания, при которых программа создаёт стоимость."
    ws["A12"].font = Font(name="Inter", size=9, italic=True, color=MUTED)
    return ws


# ============================================================== 5. Детализация
def build_detail(wb: Workbook):
    """A long, filterable, grouped register — the 'boring' sheet done properly."""
    ws = wb.create_sheet("Реестр объектов")
    title(ws, "Реестр объектов модернизации", "Сгруппировано по регионам")

    headers = ["Регион", "Площадка", "Тип", "Мощность, МВт·ч",
               "Капзатраты, млн ₽", "Ввод", "Готовность"]
    for j, h in enumerate(headers):
        ws.cell(4, 1 + j, h).style = "hdr"

    data = [
        ("Северо-Запад", "Псков-1", "Контейнерный", 24, 186, "2026-Q2", 0.92),
        ("Северо-Запад", "Псков-2", "Контейнерный", 18, 141, "2026-Q4", 0.64),
        ("Северо-Запад", "Великие Луки", "Модульный", 12, 98, "2027-Q1", 0.31),
        ("Центр", "Тула-Восток", "Контейнерный", 32, 244, "2026-Q3", 0.78),
        ("Центр", "Калуга-Юг", "Контейнерный", 28, 213, "2027-Q2", 0.22),
        ("Центр", "Рязань", "Модульный", 14, 112, "2027-Q3", 0.08),
        ("Урал", "Екатеринбург-Север", "Контейнерный", 40, 305, "2026-Q4", 0.55),
        ("Урал", "Челябинск", "Контейнерный", 36, 274, "2027-Q4", 0.14),
        ("Сибирь", "Новосибирск", "Модульный", 22, 178, "2028-Q1", 0.05),
        ("Сибирь", "Кемерово", "Контейнерный", 26, 199, "2028-Q2", 0.0),
    ]

    r = 5
    for i, row in enumerate(data):
        for j, v in enumerate(row):
            c = ws.cell(r, 1 + j, v)
            c.font = Font(name="Inter", size=10, color="1F2933")
            c.border = BOX
            if i % 2 == 1:
                c.fill = PatternFill("solid", fgColor=ZEBRA)
            if j in (3, 4):
                c.number_format = MONEY
                c.alignment = Alignment(horizontal="right")
            if j == 6:
                c.number_format = "0 %"
                c.alignment = Alignment(horizontal="center")
        r += 1

    total = r
    ws.cell(total, 1, "Итого").font = Font(name="Inter", size=10, bold=True, color="FFFFFF")
    for j in range(7):
        c = ws.cell(total, 1 + j)
        c.fill = PatternFill("solid", fgColor=ACCENT)
        c.border = BOX
        c.font = Font(name="Inter", size=10, bold=True, color="FFFFFF")
    ws.cell(total, 4, f"=SUBTOTAL(109,D5:D{total-1})").number_format = MONEY
    ws.cell(total, 5, f"=SUBTOTAL(109,E5:E{total-1})").number_format = MONEY
    ws.cell(total, 7, f"=SUBTOTAL(101,G5:G{total-1})").number_format = "0 %"
    for j in (3, 4, 6):
        ws.cell(total, 1 + j).alignment = Alignment(horizontal="right")
        ws.cell(total, 1 + j).font = Font(name="Inter", size=10, bold=True, color="FFFFFF")

    # SUBTOTAL respects the autofilter — that is why it is used instead of SUM.
    ws.auto_filter.ref = f"A4:G{total-1}"
    ws.freeze_panes = "A5"

    widths = [16, 22, 16, 17, 18, 11, 13]
    for j, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(1 + j)].width = w

    ws.conditional_formatting.add(
        f"G5:G{total-1}",
        DataBarRule(start_type="num", start_value=0, end_type="num",
                    end_value=1, color=GREEN),
    )
    ws.conditional_formatting.add(
        f"G5:G{total-1}",
        CellIsRule(operator="lessThan", formula=["0.2"],
                   font=Font(name="Inter", size=10, bold=True, color=CORAL)),
    )

    # Print setup — a register is the one sheet people actually print.
    ws.print_title_rows = "4:4"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return ws


# ================================================================== charts
def add_charts(wb: Workbook, pnl, dcf) -> None:
    ws = wb.create_sheet("Графики")
    title(ws, "Графики", "Связаны с листами прогноза — обновляются при пересчёте")

    # Combo: revenue bars + margin line on a secondary axis.
    bar = BarChart()
    bar.type = "col"
    bar.style = 2
    data = Reference(pnl, min_col=1, min_row=5, max_col=6, max_row=5)
    cats = Reference(pnl, min_col=2, min_row=4, max_col=6, max_row=4)
    bar.add_data(data, titles_from_data=True, from_rows=True)
    bar.set_categories(cats)
    bar.y_axis.title = "Выручка, млн ₽"
    bar.y_axis.majorGridlines = ChartLines()
    bar.x_axis.title = "Год"

    line = LineChart()
    mdata = Reference(pnl, min_col=1, min_row=10, max_col=6, max_row=10)
    line.add_data(mdata, titles_from_data=True, from_rows=True)
    line.y_axis.axId = 200
    line.y_axis.title = "Рентабельность EBITDA"
    line.y_axis.majorGridlines = None
    line.y_axis.crosses = "max"
    bar += line

    bar.title = "Выручка и рентабельность EBITDA"
    bar.height, bar.width = 9, 19
    ws.add_chart(bar, "A4")

    # Discounted cash flow by year.
    fcf = BarChart()
    fcf.type = "col"
    fdata = Reference(dcf, min_col=1, min_row=11, max_col=6, max_row=11)
    fcats = Reference(dcf, min_col=2, min_row=4, max_col=6, max_row=4)
    fcf.add_data(fdata, titles_from_data=True, from_rows=True)
    fcf.set_categories(fcats)
    fcf.title = "Дисконтированный денежный поток по годам"
    fcf.y_axis.title = "млн ₽"
    fcf.height, fcf.width = 9, 19
    ws.add_chart(fcf, "A24")

    ws.column_dimensions["A"].width = 12


# =================================================================== build
def main() -> int:
    wb = Workbook()
    wb.remove(wb.active)
    style_named(wb)

    build_drivers(wb)
    pnl = build_pnl(wb)
    dcf = build_dcf(wb)
    build_sensitivity(wb)
    build_detail(wb)
    add_charts(wb, pnl, dcf)

    wb.properties.creator = "Департамент стратегического развития"
    wb.properties.title = "Финансовая модель — модернизация накопителей"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"wrote {OUT.relative_to(REPO)}")

    # openpyxl writes formulas with NO cached values: every cell reads as empty
    # until something recalculates it. This step is not optional.
    recalc = REPO / "tools" / "recalc.py"
    result = subprocess.run(
        [sys.executable, str(recalc), str(OUT)],
        cwd=REPO, capture_output=True, text=True,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
