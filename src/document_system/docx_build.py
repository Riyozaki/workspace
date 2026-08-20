from __future__ import annotations

import importlib.resources
import json
import math
import tempfile
from pathlib import Path
from typing import Any

import jsonschema
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import (
    WD_CELL_VERTICAL_ALIGNMENT,
    WD_ROW_HEIGHT_RULE,
    WD_TABLE_ALIGNMENT,
)
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from .util import read_json

DEFAULT_THEME = {
    "primary": "24445C",
    "secondary": "3F6B7D",
    "accent": "C7863B",
    "text": "24323D",
    "muted": "657681",
    "light": "EEF3F5",
    "font": "Arial",
    "heading_font": "Arial",
}

ALIGNMENT = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}

TC_PR_ORDER = (
    "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
    "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark",
    "headers", "cellIns", "cellDel", "cellMerge", "tcPrChange",
)
TBL_PR_ORDER = (
    "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
    "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd",
    "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption",
    "tblDescription", "tblPrChange",
)
BORDER_ORDER = (
    "top", "left", "bottom", "right", "insideH", "insideV", "tl2br", "tr2bl",
)
MARGIN_ORDER = ("top", "left", "bottom", "right")


def _local_name(element: Any) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _insert_ordered(parent: Any, element: Any, order: tuple[str, ...]) -> None:
    name = _local_name(element)
    try:
        rank = order.index(name)
    except ValueError:
        parent.append(element)
        return
    for index, child in enumerate(parent):
        try:
            child_rank = order.index(_local_name(child))
        except ValueError:
            continue
        if child_rank > rank:
            parent.insert(index, element)
            return
    parent.append(element)


def _hex(value: str) -> str:
    value = value.strip().lstrip("#").upper()
    if len(value) != 6 or any(char not in "0123456789ABCDEF" for char in value):
        raise ValueError(f"Expected six-digit RGB color, got {value!r}")
    return value


def _rgb(value: str) -> RGBColor:
    value = _hex(value)
    return RGBColor.from_string(value)


def _set_cell_shading(cell: Any, fill: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    shading = properties.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        _insert_ordered(properties, shading, TC_PR_ORDER)
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), _hex(fill))


def _set_cell_margins(cell: Any, top: int = 90, start: int = 110, bottom: int = 90, end: int = 110) -> None:
    properties = cell._tc.get_or_add_tcPr()
    margins = properties.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        _insert_ordered(properties, margins, TC_PR_ORDER)
    for side, value in (("top", top), ("left", start), ("bottom", bottom), ("right", end)):
        node = margins.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            _insert_ordered(margins, node, MARGIN_ORDER)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _set_cell_border(cell: Any, **edges: dict[str, Any]) -> None:
    properties = cell._tc.get_or_add_tcPr()
    borders = properties.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        _insert_ordered(properties, borders, TC_PR_ORDER)
    for edge_name, values in edges.items():
        edge_name = {"start": "left", "end": "right"}.get(edge_name, edge_name)
        tag = f"w:{edge_name}"
        edge = borders.find(qn(tag))
        if edge is None:
            edge = OxmlElement(tag)
            _insert_ordered(borders, edge, BORDER_ORDER)
        edge.set(qn("w:val"), values.get("val", "single"))
        edge.set(qn("w:sz"), str(values.get("sz", 4)))
        edge.set(qn("w:space"), str(values.get("space", 0)))
        edge.set(qn("w:color"), _hex(values.get("color", "D9E0E4")))


def _set_repeat_table_header(row: Any) -> None:
    properties = row._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    # Presence alone means on. Omitting w:val avoids transitional/strict enum drift.
    properties.append(repeat)


def _prevent_row_split(row: Any) -> None:
    properties = row._tr.get_or_add_trPr()
    properties.append(OxmlElement("w:cantSplit"))


def _set_fixed_table(table: Any, width_twips: int | None = None) -> None:
    properties = table._tbl.tblPr
    layout = properties.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        _insert_ordered(properties, layout, TBL_PR_ORDER)
    layout.set(qn("w:type"), "fixed")
    if width_twips:
        width = properties.find(qn("w:tblW"))
        if width is None:
            width = OxmlElement("w:tblW")
            _insert_ordered(properties, width, TBL_PR_ORDER)
        width.set(qn("w:w"), str(width_twips))
        width.set(qn("w:type"), "dxa")


def _set_run_font(run: Any, font_name: str, language: str | None = None) -> None:
    run.font.name = font_name
    properties = run._element.get_or_add_rPr()
    fonts = properties.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        properties.insert(0, fonts)
    for key in ("ascii", "hAnsi", "cs"):
        fonts.set(qn(f"w:{key}"), font_name)
    fonts.set(qn("w:eastAsia"), "Noto Sans CJK SC" if language and language.lower().startswith(("zh", "ja", "ko")) else font_name)
    if language:
        lang = properties.find(qn("w:lang"))
        if lang is None:
            lang = OxmlElement("w:lang")
            properties.append(lang)
        lang.set(qn("w:val"), language)
        lang.set(qn("w:bidi"), language)


def _set_style_font(style: Any, font_name: str, size: int | float, color: str, *, bold: bool = False) -> None:
    style.font.name = font_name
    style.font.size = Pt(size)
    style.font.color.rgb = _rgb(color)
    style.font.bold = bold
    properties = style.element.get_or_add_rPr()
    fonts = properties.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        properties.insert(0, fonts)
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{key}"), font_name)


def _add_field(paragraph: Any, instruction: str, placeholder: str = "") -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin.set(qn("w:dirty"), "true")
    instruction_node = OxmlElement("w:instrText")
    instruction_node.set(qn("xml:space"), "preserve")
    instruction_node.text = f" {instruction} "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = placeholder
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction_node, separate, text, end])


def _add_hyperlink(paragraph: Any, text: str, url: str, color: str, font: str, language: str) -> None:
    relationship_id = paragraph.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship_id)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    run.append(properties)
    color_node = OxmlElement("w:color")
    color_node.set(qn("w:val"), _hex(color))
    properties.append(color_node)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    properties.append(underline)
    fonts = OxmlElement("w:rFonts")
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{key}"), font)
    properties.insert(0, fonts)
    lang = OxmlElement("w:lang")
    lang.set(qn("w:val"), language)
    properties.append(lang)
    text_node = OxmlElement("w:t")
    text_node.text = text
    run.append(text_node)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _add_runs(paragraph: Any, block: dict[str, Any], theme: dict[str, str], language: str) -> None:
    runs = block.get("runs")
    if runs is None:
        runs = [{"text": block.get("text", "")}]
    for item in runs:
        if item.get("link"):
            _add_hyperlink(
                paragraph,
                item["text"],
                item["link"],
                item.get("color", theme["secondary"]),
                item.get("font", theme["font"]),
                language,
            )
            continue
        run = paragraph.add_run(item.get("text", ""))
        _set_run_font(run, item.get("font", theme["font"]), language)
        run.bold = item.get("bold")
        run.italic = item.get("italic")
        run.underline = item.get("underline")
        if item.get("color"):
            run.font.color.rgb = _rgb(item["color"])
        if item.get("size_pt"):
            run.font.size = Pt(item["size_pt"])


def _format_paragraph(paragraph: Any, block: dict[str, Any]) -> None:
    paragraph.alignment = ALIGNMENT.get(block.get("align", "left"), WD_ALIGN_PARAGRAPH.LEFT)
    fmt = paragraph.paragraph_format
    if "space_after_pt" in block:
        fmt.space_after = Pt(block["space_after_pt"])
    if "keep_with_next" in block:
        fmt.keep_with_next = block["keep_with_next"]
    if "keep_together" in block:
        fmt.keep_together = block["keep_together"]
    fmt.widow_control = True


def _set_page(section: Any, page: dict[str, Any]) -> None:
    size = page.get("size", "A4")
    orientation = page.get("orientation", "portrait")
    dimensions = {"A4": (210, 297), "Letter": (215.9, 279.4)}[size]
    width, height = dimensions
    if orientation == "landscape":
        section.orientation = WD_ORIENT.LANDSCAPE
        width, height = height, width
    else:
        section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Mm(width)
    section.page_height = Mm(height)
    section.top_margin = Mm(page.get("margin_top_mm", 22))
    section.right_margin = Mm(page.get("margin_right_mm", 20))
    section.bottom_margin = Mm(page.get("margin_bottom_mm", 20))
    section.left_margin = Mm(page.get("margin_left_mm", 23))
    section.header_distance = Mm(10)
    section.footer_distance = Mm(10)


def _configure_styles(document: Document, theme: dict[str, str], language: str) -> None:
    styles = document.styles
    normal = styles["Normal"]
    _set_style_font(normal, theme["font"], 10.5, theme["text"])
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.15
    normal.paragraph_format.widow_control = True

    heading_sizes = {1: 20, 2: 15, 3: 12.5, 4: 11}
    for level, size in heading_sizes.items():
        style = styles[f"Heading {level}"]
        _set_style_font(style, theme["heading_font"], size, theme["primary"], bold=True)
        style.paragraph_format.space_before = Pt(16 if level == 1 else 11)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.keep_together = True
        style.paragraph_format.widow_control = True

    _set_style_font(styles["Title"], theme["heading_font"], 30, theme["primary"], bold=True)
    styles["Title"].paragraph_format.space_after = Pt(12)
    _set_style_font(styles["Subtitle"], theme["font"], 14, theme["muted"])
    _set_style_font(styles["Caption"], theme["font"], 9, theme["muted"])
    styles["Caption"].paragraph_format.space_before = Pt(4)
    styles["Caption"].paragraph_format.space_after = Pt(9)

    for name in ("List Bullet", "List Bullet 2", "List Bullet 3", "List Number", "List Number 2", "List Number 3"):
        if name in styles:
            _set_style_font(styles[name], theme["font"], 10.5, theme["text"])
            styles[name].paragraph_format.space_after = Pt(3)
            styles[name].paragraph_format.widow_control = True

    settings = document.settings.element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        later_settings = {
            "hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars",
            "rsids", "mathPr", "uiCompat97To2003", "themeFontLang",
            "clrSchemeMapping", "doNotIncludeSubdocsInStats", "chartTrackingRefBased",
            "docId", "discardImageEditingData", "defaultImageDpi", "conflictMode",
            "decimalSymbol", "listSeparator",
        }
        insertion = next(
            (
                index
                for index, child in enumerate(settings)
                if _local_name(child) in later_settings
            ),
            len(settings),
        )
        settings.insert(insertion, update)
    update.set(qn("w:val"), "true")

    # Default document language helps spellchecking and hyphenation in Word.
    language_node = settings.find(qn("w:themeFontLang"))
    if language_node is None:
        language_node = OxmlElement("w:themeFontLang")
        settings.append(language_node)
    language_node.set(qn("w:val"), language)


def _add_header_footer(document: Document, spec: dict[str, Any], theme: dict[str, str], language: str) -> None:
    header_spec = spec.get("header", {})
    footer_spec = spec.get("footer", {})
    for section in document.sections:
        section.different_first_page_header_footer = bool(spec.get("cover")) and not header_spec.get("show_on_first_page", False)
        if header_spec:
            header = section.header
            table = header.add_table(rows=1, cols=2, width=section.page_width - section.left_margin - section.right_margin)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            _set_fixed_table(table)
            for cell in table.rows[0].cells:
                _set_cell_margins(cell, 0, 0, 0, 0)
                _set_cell_border(cell, bottom={"color": theme["light"], "sz": 7})
            left = table.cell(0, 0).paragraphs[0]
            right = table.cell(0, 1).paragraphs[0]
            left.alignment = WD_ALIGN_PARAGRAPH.LEFT
            right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for paragraph, text in ((left, header_spec.get("left", "")), (right, header_spec.get("right", ""))):
                run = paragraph.add_run(text)
                _set_run_font(run, theme["font"], language)
                run.font.size = Pt(8)
                run.font.color.rgb = _rgb(theme["muted"])
        if footer_spec:
            footer = section.footer
            table = footer.add_table(rows=1, cols=2, width=section.page_width - section.left_margin - section.right_margin)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            _set_fixed_table(table)
            for cell in table.rows[0].cells:
                _set_cell_margins(cell, 0, 0, 0, 0)
                _set_cell_border(cell, top={"color": theme["light"], "sz": 7})
            left = table.cell(0, 0).paragraphs[0]
            right = table.cell(0, 1).paragraphs[0]
            left.alignment = WD_ALIGN_PARAGRAPH.LEFT
            right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run = left.add_run(footer_spec.get("left", ""))
            _set_run_font(run, theme["font"], language)
            run.font.size = Pt(8)
            run.font.color.rgb = _rgb(theme["muted"])
            if footer_spec.get("page_numbers", True):
                label = footer_spec.get("page_number_label", "")
                run = right.add_run(label)
                _set_run_font(run, theme["font"], language)
                run.font.size = Pt(8)
                run.font.color.rgb = _rgb(theme["muted"])
                _add_field(right, "PAGE", "1")
                if footer_spec.get("right"):
                    tail = right.add_run(footer_spec["right"])
                    _set_run_font(tail, theme["font"], language)
                    tail.font.size = Pt(8)
                    tail.font.color.rgb = _rgb(theme["muted"])
            else:
                run = right.add_run(footer_spec.get("right", ""))
                _set_run_font(run, theme["font"], language)
                run.font.size = Pt(8)
                run.font.color.rgb = _rgb(theme["muted"])


def _add_cover(document: Document, cover: dict[str, Any], theme: dict[str, str], language: str, base_dir: Path) -> None:
    accent = document.add_table(rows=1, cols=1)
    accent.alignment = WD_TABLE_ALIGNMENT.CENTER
    accent.autofit = False
    accent.rows[0].height = Mm(6)
    accent.rows[0].height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    _set_cell_shading(accent.cell(0, 0), theme["accent"])
    _set_cell_margins(accent.cell(0, 0), 0, 0, 0, 0)
    accent.cell(0, 0).text = ""

    spacer = document.add_paragraph()
    spacer.paragraph_format.space_after = Pt(70)
    if cover.get("eyebrow"):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(10)
        run = paragraph.add_run(cover["eyebrow"].upper())
        _set_run_font(run, theme["font"], language)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = _rgb(theme["accent"])

    title = document.add_paragraph(style="Title")
    title.paragraph_format.keep_with_next = True
    title.add_run(cover["title"])
    if cover.get("subtitle"):
        subtitle = document.add_paragraph(style="Subtitle")
        subtitle.paragraph_format.space_after = Pt(20)
        subtitle.add_run(cover["subtitle"])

    if cover.get("image"):
        image_path = (base_dir / cover["image"]).resolve()
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run().add_picture(str(image_path), width=Mm(150))

    information = document.add_table(rows=1, cols=1)
    information.alignment = WD_TABLE_ALIGNMENT.LEFT
    _set_fixed_table(information)
    cell = information.cell(0, 0)
    _set_cell_shading(cell, theme["light"])
    _set_cell_margins(cell, 160, 200, 160, 200)
    lines = [cover.get("organization"), cover.get("date")]
    for line in [value for value in lines if value]:
        paragraph = cell.add_paragraph() if cell.paragraphs[0].text else cell.paragraphs[0]
        run = paragraph.add_run(line)
        _set_run_font(run, theme["font"], language)
        run.font.size = Pt(10)
        run.font.color.rgb = _rgb(theme["text"])

    if cover.get("confidentiality"):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(18)
        run = paragraph.add_run(cover["confidentiality"].upper())
        _set_run_font(run, theme["font"], language)
        run.bold = True
        run.font.size = Pt(8)
        run.font.color.rgb = _rgb(theme["accent"])
    document.add_page_break()


def _add_toc(document: Document, toc: bool | dict[str, Any], theme: dict[str, str], language: str) -> None:
    settings = toc if isinstance(toc, dict) else {}
    title = settings.get("title", "Содержание")
    document.add_heading(title, level=1)
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(12)
    minimum = settings.get("min_level", 1)
    maximum = settings.get("max_level", 3)
    _add_field(paragraph, f'TOC \\o "{minimum}-{maximum}" \\h \\z \\u', "Обновите оглавление при открытии документа")
    if settings.get("page_break_after", True):
        document.add_page_break()


def _add_table(document: Document, block: dict[str, Any], theme: dict[str, str], language: str) -> None:
    headers = block.get("headers", [])
    rows = block.get("rows", [])
    column_count = max(len(headers), max((len(row) for row in rows), default=0))
    if column_count == 0:
        raise ValueError("Table must contain headers or rows")
    table = document.add_table(rows=1 if headers else 0, cols=column_count)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    section = document.sections[-1]
    available_emu = section.page_width - section.left_margin - section.right_margin
    available_mm = available_emu / 36_000
    available_twips = round(available_mm * 56.692913)
    _set_fixed_table(table, available_twips)
    widths_pct = block.get("widths_pct") or [100 / column_count] * column_count
    if len(widths_pct) != column_count or not math.isclose(sum(widths_pct), 100, rel_tol=0.03, abs_tol=1.0):
        raise ValueError(f"Table widths_pct must have {column_count} values summing to 100")
    widths = [Mm(available_mm * value / 100) for value in widths_pct]

    def fill_cell(cell: Any, value: Any, *, header: bool = False) -> None:
        config = value if isinstance(value, dict) else {"text": value}
        text = "" if config.get("text") is None else str(config.get("text"))
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        _set_cell_margins(cell)
        if config.get("fill"):
            _set_cell_shading(cell, config["fill"])
        elif header:
            _set_cell_shading(cell, theme["primary"])
        paragraph = cell.paragraphs[0]
        paragraph.alignment = ALIGNMENT.get(config.get("align", "left"), WD_ALIGN_PARAGRAPH.LEFT)
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(text)
        _set_run_font(run, theme["font"], language)
        run.font.size = Pt(9)
        run.bold = bool(config.get("bold", header))
        run.font.color.rgb = _rgb(config.get("color", "FFFFFF" if header else theme["text"]))
        border = {"color": "D7E0E5", "sz": 4}
        _set_cell_border(cell, top=border, bottom=border, start=border, end=border)

    if headers:
        header_row = table.rows[0]
        _set_repeat_table_header(header_row)
        _prevent_row_split(header_row)
        for index in range(column_count):
            fill_cell(header_row.cells[index], headers[index] if index < len(headers) else "", header=True)
            header_row.cells[index].width = widths[index]

    for row_index, values in enumerate(rows):
        row = table.add_row()
        _prevent_row_split(row)
        for index in range(column_count):
            value = values[index] if index < len(values) else ""
            if block.get("zebra", True) and row_index % 2 == 1 and not isinstance(value, dict):
                value = {"text": value, "fill": "F6F8F9"}
            fill_cell(row.cells[index], value)
            row.cells[index].width = widths[index]

    if block.get("caption"):
        caption = document.add_paragraph(style="Caption")
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption.add_run(block["caption"])


def _add_callout(document: Document, block: dict[str, Any], theme: dict[str, str], language: str) -> None:
    table = document.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_fixed_table(table)
    cell = table.cell(0, 0)
    _set_cell_shading(cell, block.get("fill", theme["light"]))
    _set_cell_margins(cell, 140, 190, 140, 190)
    border = block.get("border", theme["accent"])
    _set_cell_border(
        cell,
        start={"color": border, "sz": 18},
        top={"color": block.get("fill", theme["light"]), "sz": 1},
        bottom={"color": block.get("fill", theme["light"]), "sz": 1},
        end={"color": block.get("fill", theme["light"]), "sz": 1},
    )
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    _add_runs(paragraph, block, theme, language)


def _make_chart(block: dict[str, Any], theme: dict[str, str], path: Path) -> None:
    labels = block.get("labels", [])
    series = block.get("series", [])
    kind = block.get("kind", "bar")
    if not labels or not series:
        raise ValueError("Chart requires labels and series")
    colors = [f"#{theme['primary']}", f"#{theme['accent']}", f"#{theme['secondary']}", "#7A8F9A"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 13})
    fig, ax = plt.subplots(figsize=(8.0, 4.4), constrained_layout=True)
    if kind == "pie":
        values = series[0]["values"]
        ax.pie(values, labels=labels, autopct="%1.0f%%", colors=colors[: len(values)], startangle=90, wedgeprops={"linewidth": 1, "edgecolor": "white"})
        ax.axis("equal")
    elif kind in {"bar", "horizontal_bar"}:
        count = len(series)
        positions = list(range(len(labels)))
        width = 0.8 / count
        for index, item in enumerate(series):
            offsets = [value + (index - (count - 1) / 2) * width for value in positions]
            if kind == "bar":
                ax.bar(offsets, item["values"], width=width, label=item["name"], color=colors[index % len(colors)])
            else:
                ax.barh(offsets, item["values"], height=width, label=item["name"], color=colors[index % len(colors)])
        if kind == "bar":
            ax.set_xticks(positions, labels)
            ax.grid(axis="y", alpha=0.18)
        else:
            ax.set_yticks(positions, labels)
            ax.grid(axis="x", alpha=0.18)
        if count > 1:
            ax.legend(frameon=False, ncols=min(count, 3))
    elif kind == "line":
        for index, item in enumerate(series):
            ax.plot(labels, item["values"], marker="o", linewidth=2.2, label=item["name"], color=colors[index % len(colors)])
        ax.grid(axis="y", alpha=0.18)
        if len(series) > 1:
            ax.legend(frameon=False, ncols=min(len(series), 3))
    else:
        raise ValueError(f"Unsupported chart kind: {kind}")
    if block.get("title"):
        ax.set_title(block["title"], loc="left", color=f"#{theme['text']}", fontweight="bold")
    if block.get("y_label") and kind != "pie":
        ax.set_ylabel(block["y_label"])
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.savefig(path, dpi=180, transparent=False, facecolor="white")
    plt.close(fig)


def _add_content(document: Document, content: list[dict[str, Any]], theme: dict[str, str], language: str, base_dir: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="documentctl-charts-") as tmp:
        chart_dir = Path(tmp)
        for index, block in enumerate(content):
            kind = block["type"]
            if kind == "heading":
                paragraph = document.add_heading(level=block.get("level", 1))
                _add_runs(paragraph, block, theme, language)
                _format_paragraph(paragraph, {**block, "keep_with_next": True, "keep_together": True})
            elif kind == "paragraph":
                paragraph = document.add_paragraph(style=block.get("style"))
                _add_runs(paragraph, block, theme, language)
                _format_paragraph(paragraph, block)
            elif kind in {"bullets", "numbered"}:
                base_style = "List Bullet" if kind == "bullets" else "List Number"
                for item in block.get("items", []):
                    config = item if isinstance(item, dict) else {"text": item, "level": 0}
                    level = min(2, int(config.get("level", 0)))
                    style = base_style if level == 0 else f"{base_style} {level + 1}"
                    paragraph = document.add_paragraph(style=style)
                    _add_runs(paragraph, {"text": config["text"]}, theme, language)
                    _format_paragraph(paragraph, {"space_after_pt": 3})
            elif kind == "table":
                _add_table(document, block, theme, language)
            elif kind == "callout":
                _add_callout(document, block, theme, language)
            elif kind == "image":
                path = (base_dir / block["path"]).resolve()
                paragraph = document.add_paragraph()
                paragraph.alignment = ALIGNMENT.get(block.get("align", "center"), WD_ALIGN_PARAGRAPH.CENTER)
                kwargs: dict[str, Any] = {}
                if block.get("width_mm"):
                    kwargs["width"] = Mm(block["width_mm"])
                if block.get("height_mm"):
                    kwargs["height"] = Mm(block["height_mm"])
                paragraph.add_run().add_picture(str(path), **kwargs)
                if block.get("caption"):
                    caption = document.add_paragraph(style="Caption")
                    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    caption.add_run(block["caption"])
            elif kind == "chart":
                path = chart_dir / f"chart-{index:03d}.png"
                _make_chart(block, theme, path)
                paragraph = document.add_paragraph()
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                paragraph.add_run().add_picture(str(path), width=Mm(block.get("width_mm", 155)))
                if block.get("caption") or block.get("note"):
                    caption = document.add_paragraph(style="Caption")
                    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    caption.add_run(block.get("caption") or block.get("note", ""))
            elif kind == "page_break":
                document.add_page_break()
            elif kind == "spacer":
                paragraph = document.add_paragraph()
                paragraph.paragraph_format.space_after = Pt(block.get("height_pt", 12))
            else:  # schema should have caught it
                raise ValueError(f"Unsupported content block type: {kind}")


def validate_spec(spec: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath("schemas/docx-spec.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(spec)
    toc = spec.get("toc")
    if isinstance(toc, dict) and toc.get("min_level", 1) > toc.get("max_level", 3):
        raise ValueError("toc.min_level must be <= toc.max_level")


def build_docx(spec: dict[str, Any], output_path: str | Path, *, base_dir: str | Path | None = None) -> Path:
    validate_spec(spec)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    base = Path(base_dir or ".").resolve()
    theme = {**DEFAULT_THEME, **spec.get("theme", {})}
    theme = {key: _hex(value) if key in {"primary", "secondary", "accent", "text", "muted", "light"} else value for key, value in theme.items()}
    language = spec.get("language", "ru-RU")

    document = Document()
    _set_page(document.sections[0], spec.get("page", {}))
    _configure_styles(document, theme, language)
    properties = document.core_properties
    metadata = spec.get("metadata", {})
    for key in ("title", "subject", "author", "keywords", "category", "comments"):
        if metadata.get(key) is not None:
            setattr(properties, key, metadata[key])
    properties.language = language

    _add_header_footer(document, spec, theme, language)
    if spec.get("cover"):
        _add_cover(document, spec["cover"], theme, language, base)
    if spec.get("toc"):
        _add_toc(document, spec["toc"], theme, language)
    _add_content(document, spec["content"], theme, language, base)

    # Avoid a trailing empty paragraph becoming an extra blank page after a table.
    if document.paragraphs and not document.paragraphs[-1].text:
        document.paragraphs[-1].paragraph_format.space_after = Pt(0)
        document.paragraphs[-1].paragraph_format.line_spacing = Pt(1)
    document.save(destination)
    return destination


def build_docx_from_file(spec_path: str | Path, output_path: str | Path) -> Path:
    source = Path(spec_path).resolve()
    return build_docx(read_json(source), output_path, base_dir=source.parent)
