from __future__ import annotations

import html
import importlib.resources
import json
import tempfile
from pathlib import Path
from typing import Any

import jsonschema
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from .util import read_json

DEFAULT_THEME = {
    "primary": "24445C",
    "secondary": "3F6B7D",
    "accent": "C7863B",
    "text": "24323D",
    "muted": "657681",
    "light": "EEF3F5",
    "positive": "26734D",
    "negative": "B54343",
}


def _color(value: str) -> colors.Color:
    return colors.HexColor("#" + value.strip().lstrip("#"))


def _register_fonts() -> tuple[str, str, str, str]:
    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        ),
    ]
    for regular, bold, italic, bold_italic in candidates:
        if Path(regular).exists() and Path(bold).exists():
            italic = italic if Path(italic).exists() else regular
            bold_italic = bold_italic if Path(bold_italic).exists() else bold
            names = ("DS-Sans", "DS-Sans-Bold", "DS-Sans-Italic", "DS-Sans-BoldItalic")
            for name, path in zip(names, (regular, bold, italic, bold_italic), strict=True):
                if name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(name, path))
            pdfmetrics.registerFontFamily(names[0], normal=names[0], bold=names[1], italic=names[2], boldItalic=names[3])
            return names
    return ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique")


class DocumentTemplate(BaseDocTemplate):
    def __init__(self, *args: Any, header: str, footer: str, theme: dict[str, str], metadata: dict[str, str], **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.header_text = header
        self.footer_text = footer
        self.theme = theme
        self.metadata_values = metadata
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body")
        self.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=self._draw_page))
        self._heading_counter = 0

    def _draw_page(self, canvas: Any, doc: Any) -> None:
        canvas.saveState()
        for key, setter in (
            ("title", canvas.setTitle),
            ("author", canvas.setAuthor),
            ("subject", canvas.setSubject),
            ("keywords", canvas.setKeywords),
        ):
            if self.metadata_values.get(key):
                setter(self.metadata_values[key])
        canvas.setStrokeColor(_color(self.theme["light"]))
        canvas.setLineWidth(0.6)
        canvas.line(self.leftMargin, self.pagesize[1] - 14 * mm, self.pagesize[0] - self.rightMargin, self.pagesize[1] - 14 * mm)
        canvas.line(self.leftMargin, 13 * mm, self.pagesize[0] - self.rightMargin, 13 * mm)
        canvas.setFillColor(_color(self.theme["muted"]))
        canvas.setFont("DS-Sans" if "DS-Sans" in pdfmetrics.getRegisteredFontNames() else "Helvetica", 8)
        if self.header_text:
            canvas.drawString(self.leftMargin, self.pagesize[1] - 11 * mm, self.header_text)
        if self.footer_text:
            canvas.drawString(self.leftMargin, 9 * mm, self.footer_text)
        canvas.drawRightString(self.pagesize[0] - self.rightMargin, 9 * mm, str(doc.page))
        canvas.restoreState()

    def beforeDocument(self) -> None:
        self._heading_counter = 0

    def afterFlowable(self, flowable: Any) -> None:
        if isinstance(flowable, Paragraph) and flowable.style.name.startswith("Heading"):
            level = int(flowable.style.name[-1]) - 1
            self._heading_counter += 1
            key = f"heading-{self._heading_counter}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(), key, level=level, closed=False)
            self.notify("TOCEntry", (level, flowable.getPlainText(), self.page, key))


def validate_pdf_spec(spec: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath("schemas/pdf-spec.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(spec)


def _styles(theme: dict[str, str], fonts: tuple[str, str, str, str]) -> dict[str, ParagraphStyle]:
    regular, bold, italic, _bold_italic = fonts
    base = getSampleStyleSheet()
    return {
        "Body": ParagraphStyle("Body", parent=base["BodyText"], fontName=regular, fontSize=10.3, leading=14.5, textColor=_color(theme["text"]), alignment=TA_JUSTIFY, spaceAfter=7),
        "Heading1": ParagraphStyle("Heading1", parent=base["Heading1"], fontName=bold, fontSize=19, leading=23, textColor=_color(theme["primary"]), spaceBefore=13, spaceAfter=7, keepWithNext=True),
        "Heading2": ParagraphStyle("Heading2", parent=base["Heading2"], fontName=bold, fontSize=14, leading=18, textColor=_color(theme["secondary"]), spaceBefore=10, spaceAfter=5, keepWithNext=True),
        "Heading3": ParagraphStyle("Heading3", parent=base["Heading3"], fontName=bold, fontSize=11.5, leading=15, textColor=_color(theme["text"]), spaceBefore=8, spaceAfter=4, keepWithNext=True),
        # The TOC title deliberately does not use a Heading* style name. Otherwise
        # DocumentTemplate.afterFlowable() would include "Содержание" in the TOC.
        "TocTitle": ParagraphStyle("TocTitle", parent=base["Heading1"], fontName=bold, fontSize=19, leading=23, textColor=_color(theme["primary"]), spaceBefore=13, spaceAfter=10, keepWithNext=True),
        # ReportLab's TableOfContents defaults to Helvetica. That font cannot
        # represent Cyrillic, so generated PDFs used to contain rows of black
        # missing-glyph squares even though the body fonts were embedded.
        "Toc1": ParagraphStyle("Toc1", fontName=bold, fontSize=10.5, leading=14, leftIndent=0, firstLineIndent=0, textColor=_color(theme["text"]), spaceBefore=4),
        "Toc2": ParagraphStyle("Toc2", fontName=regular, fontSize=9.5, leading=13, leftIndent=12, firstLineIndent=0, textColor=_color(theme["text"]), spaceBefore=2),
        "Toc3": ParagraphStyle("Toc3", fontName=regular, fontSize=9, leading=12, leftIndent=24, firstLineIndent=0, textColor=_color(theme["muted"]), spaceBefore=1),
        "Caption": ParagraphStyle("Caption", fontName=italic, fontSize=8.5, leading=11, textColor=_color(theme["muted"]), alignment=TA_CENTER, spaceBefore=3, spaceAfter=8),
        "CoverKicker": ParagraphStyle("CoverKicker", fontName=bold, fontSize=10, leading=13, textColor=_color(theme["accent"]), spaceAfter=14),
        "CoverTitle": ParagraphStyle("CoverTitle", fontName=bold, fontSize=30, leading=36, textColor=_color(theme["primary"]), spaceAfter=16),
        "CoverSubtitle": ParagraphStyle("CoverSubtitle", fontName=regular, fontSize=15, leading=20, textColor=_color(theme["muted"]), spaceAfter=28),
        "Small": ParagraphStyle("Small", fontName=regular, fontSize=8.5, leading=11, textColor=_color(theme["muted"])),
        "Callout": ParagraphStyle("Callout", fontName=regular, fontSize=10.5, leading=15, textColor=_color(theme["text"])),
        "TableHeader": ParagraphStyle("TableHeader", fontName=bold, fontSize=8.5, leading=11, textColor=colors.white),
    }


def _rich_text(block: dict[str, Any], theme: dict[str, str]) -> str:
    if "runs" not in block:
        return html.escape(block.get("text", "")).replace("\n", "<br/>")
    values = []
    for run in block["runs"]:
        value = html.escape(run["text"]).replace("\n", "<br/>")
        if run.get("bold"):
            value = f"<b>{value}</b>"
        if run.get("italic"):
            value = f"<i>{value}</i>"
        if run.get("color"):
            value = f'<font color="#{run["color"]}">{value}</font>'
        if run.get("link"):
            value = f'<a href="{html.escape(run["link"], quote=True)}" color="#{theme["secondary"]}">{value}</a>'
        values.append(value)
    return "".join(values)


def _make_chart(block: dict[str, Any], theme: dict[str, str], path: Path) -> None:
    labels = block.get("labels", [])
    series = block.get("series", [])
    kind = block.get("kind", "bar")
    if not labels or not series or any(len(item["values"]) != len(labels) for item in series):
        raise ValueError("Chart labels and series lengths must match")
    palette = [f"#{theme['primary']}", f"#{theme['accent']}", f"#{theme['secondary']}", "#80919A"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(8, 4.2), constrained_layout=True)
    if kind == "pie":
        ax.pie(series[0]["values"], labels=labels, autopct="%1.0f%%", startangle=90, colors=palette)
        ax.axis("equal")
    elif kind in {"bar", "horizontal_bar"}:
        positions = list(range(len(labels)))
        width = 0.8 / len(series)
        for index, item in enumerate(series):
            offsets = [value + (index - (len(series) - 1) / 2) * width for value in positions]
            if kind == "bar":
                ax.bar(offsets, item["values"], width, label=item["name"], color=palette[index % len(palette)])
            else:
                ax.barh(offsets, item["values"], width, label=item["name"], color=palette[index % len(palette)])
        (ax.set_xticks if kind == "bar" else ax.set_yticks)(positions, labels)
        ax.legend(frameon=False)
        ax.grid(axis="y" if kind == "bar" else "x", alpha=0.2)
    else:
        for index, item in enumerate(series):
            ax.plot(labels, item["values"], marker="o", linewidth=2, label=item["name"], color=palette[index % len(palette)])
        ax.legend(frameon=False)
        ax.grid(axis="y", alpha=0.2)
    if block.get("title"):
        ax.set_title(block["title"], loc="left", fontweight="bold")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.savefig(path, dpi=180, facecolor="white")
    plt.close(fig)


def build_pdf(spec: dict[str, Any], output_path: str | Path, *, base_dir: str | Path | None = None) -> Path:
    validate_pdf_spec(spec)
    fonts = _register_fonts()
    theme = {**DEFAULT_THEME, **spec.get("theme", {})}
    for key in DEFAULT_THEME:
        _color(theme[key])
    styles = _styles(theme, fonts)
    page = spec.get("page", {})
    pagesize = A4 if page.get("size", "A4") == "A4" else LETTER
    if page.get("orientation") == "landscape":
        pagesize = landscape(pagesize)
    margins = {
        "topMargin": page.get("margin_top_mm", 22) * mm,
        "rightMargin": page.get("margin_right_mm", 20) * mm,
        "bottomMargin": max(18, page.get("margin_bottom_mm", 20)) * mm,
        "leftMargin": page.get("margin_left_mm", 23) * mm,
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    base = Path(base_dir or ".").resolve()
    metadata = spec.get("metadata", {})
    document = DocumentTemplate(
        str(destination),
        pagesize=pagesize,
        header=spec.get("header", ""),
        footer=spec.get("footer", ""),
        theme=theme,
        metadata=metadata,
        **margins,
    )
    story: list[Any] = []
    cover = spec.get("cover")
    if cover:
        story.extend(
            [
                Spacer(1, 24 * mm),
                Table([[""]], colWidths=[document.width], rowHeights=[5 * mm], style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), _color(theme["accent"]))])),
                Spacer(1, 22 * mm),
                Paragraph(html.escape(cover.get("kicker", "")).upper(), styles["CoverKicker"]),
                Paragraph(html.escape(cover["title"]), styles["CoverTitle"]),
                Paragraph(html.escape(cover.get("subtitle", "")), styles["CoverSubtitle"]),
                Spacer(1, 20 * mm),
                Table(
                    [[Paragraph(html.escape(value), styles["Body"])] for value in (cover.get("organization"), cover.get("date")) if value],
                    colWidths=[document.width],
                    style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), _color(theme["light"])), ("BOX", (0, 0), (-1, -1), 0.5, _color(theme["light"])), ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12)]),
                ),
                Spacer(1, 12 * mm),
                Paragraph(html.escape(cover.get("confidentiality", "")).upper(), styles["Small"]),
                PageBreak(),
            ]
        )
    if spec.get("toc"):
        toc = TableOfContents()
        toc.levelStyles = [styles["Toc1"], styles["Toc2"], styles["Toc3"]]
        story.extend([Paragraph("Содержание", styles["TocTitle"]), toc, PageBreak()])

    with tempfile.TemporaryDirectory(prefix="documentctl-pdf-charts-") as tmp:
        chart_dir = Path(tmp)
        for index, block in enumerate(spec["content"]):
            kind = block["type"]
            if kind == "heading":
                story.append(Paragraph(_rich_text(block, theme), styles[f"Heading{block.get('level', 1)}"]))
            elif kind == "paragraph":
                story.append(Paragraph(_rich_text(block, theme), styles["Body"]))
            elif kind == "bullets":
                items = [ListItem(Paragraph(html.escape(value), styles["Body"]), leftIndent=12) for value in block.get("items", [])]
                story.append(ListFlowable(items, bulletType="bullet", start="circle", leftIndent=18, bulletFontName=fonts[0], bulletFontSize=8))
                story.append(Spacer(1, 4))
            elif kind == "table":
                headers = block.get("headers", [])
                rows = block.get("rows", [])
                columns = len(headers)
                if not columns or any(len(row) > columns for row in rows):
                    raise ValueError("PDF table requires headers and compatible rows")
                data = [[Paragraph(html.escape(str(value)), styles["TableHeader"]) for value in headers]]
                data.extend([Paragraph(html.escape("" if value is None else str(value)), styles["Small"]) for value in row] + [""] * (columns - len(row)) for row in rows)
                widths = block.get("widths_pct") or [100 / columns] * columns
                table = Table(data, colWidths=[document.width * value / 100 for value in widths], repeatRows=1 if block.get("repeat_header", True) else 0, hAlign="LEFT")
                table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), _color(theme["primary"])), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), fonts[1]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.35, _color(theme["light"])), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _color(theme["light"])])]))
                story.append(table)
                if block.get("caption"):
                    story.append(Paragraph(html.escape(block["caption"]), styles["Caption"]))
            elif kind == "callout":
                table = Table([[Paragraph(_rich_text(block, theme), styles["Callout"])]], colWidths=[document.width])
                table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _color(theme["light"])), ("LINEBEFORE", (0, 0), (0, -1), 4, _color(theme["accent"])), ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
                story.append(KeepTogether([table, Spacer(1, 6)]))
            elif kind == "image":
                image_path = (base / block["path"]).resolve()
                image = Image(str(image_path), width=block.get("width_mm", 150) * mm, height=block.get("height_mm", 90) * mm, hAlign="CENTER")
                story.append(image)
                if block.get("caption"):
                    story.append(Paragraph(html.escape(block["caption"]), styles["Caption"]))
            elif kind == "chart":
                chart_path = chart_dir / f"chart-{index}.png"
                _make_chart(block, theme, chart_path)
                story.append(Image(str(chart_path), width=160 * mm, height=84 * mm, hAlign="CENTER"))
                if block.get("caption") or block.get("source"):
                    story.append(Paragraph(html.escape(block.get("caption") or block.get("source", "")), styles["Caption"]))
            elif kind == "page_break":
                story.append(PageBreak())
            elif kind == "spacer":
                story.append(Spacer(1, block.get("height_pt", 12)))
        document.multiBuild(story)
    return destination


def build_pdf_from_file(spec_path: str | Path, output_path: str | Path) -> Path:
    source = Path(spec_path).resolve()
    return build_pdf(read_json(source), output_path, base_dir=source.parent)
