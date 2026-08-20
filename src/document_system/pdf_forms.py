from __future__ import annotations

import importlib.resources
import io
import json
from pathlib import Path
from typing import Any

import jsonschema
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .errors import DocumentSystemError
from .pdf_build import _register_fonts
from .util import read_json


class PdfFormError(DocumentSystemError):
    pass


def fill_pdf_form(
    input_path: str | Path,
    output_path: str | Path,
    values: dict[str, Any],
    *,
    password: str | None = None,
) -> dict[str, Any]:
    reader = PdfReader(input_path, strict=True)
    if reader.is_encrypted and (not password or reader.decrypt(password) == 0):
        raise PdfFormError("Unable to unlock encrypted PDF form")
    fields = reader.get_fields() or {}
    missing = sorted(set(values) - set(fields))
    if missing:
        raise PdfFormError(f"Form fields not found: {', '.join(missing)}")
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    for page in writer.pages:
        writer.update_page_form_field_values(page, values, auto_regenerate=False)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        writer.write(handle)
    return {
        "output": str(destination),
        "fields_updated": sorted(values),
        "field_count": len(values),
    }


def validate_overlay_plan(plan: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath("schemas/pdf-overlay.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(plan)


def _overlay_for_page(width: float, height: float, items: list[dict[str, Any]], base: Path) -> Any:
    regular, bold, _italic, _bold_italic = _register_fonts()
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    for item in items:
        x = item["x"]
        top = item["y"]
        box_width = item.get("width", 100)
        box_height = item.get("height", item.get("font_size", 10) * 1.4)
        if x + box_width > width or top + box_height > height:
            raise PdfFormError(
                f"Overlay item on page {item['page']} exceeds page bounds: "
                f"({x}, {top}, {box_width}, {box_height}) vs ({width}, {height})"
            )
        y = height - top - box_height
        color = item.get("color", "000000")
        pdf.setFillColorRGB(int(color[:2], 16) / 255, int(color[2:4], 16) / 255, int(color[4:], 16) / 255)
        pdf.setStrokeColorRGB(int(color[:2], 16) / 255, int(color[2:4], 16) / 255, int(color[4:], 16) / 255)
        kind = item["type"]
        if kind == "text":
            if "text" not in item:
                raise PdfFormError("Text overlay requires text")
            font_size = item.get("font_size", 10)
            pdf.setFont(regular, font_size)
            lines = item["text"].splitlines() or [""]
            for line_index, line in enumerate(lines):
                baseline = y + box_height - font_size * (line_index + 1)
                if item.get("align") == "center":
                    pdf.drawCentredString(x + box_width / 2, baseline, line)
                elif item.get("align") == "right":
                    pdf.drawRightString(x + box_width, baseline, line)
                else:
                    pdf.drawString(x, baseline, line)
        elif kind == "check":
            line_width = item.get("line_width", 1.8)
            pdf.setLineWidth(line_width)
            pdf.line(x, y + box_height * 0.45, x + box_width * 0.35, y + box_height * 0.08)
            pdf.line(x + box_width * 0.35, y + box_height * 0.08, x + box_width, y + box_height)
        elif kind == "rectangle":
            pdf.setLineWidth(item.get("line_width", 1))
            pdf.rect(x, y, box_width, box_height, stroke=1, fill=0)
        elif kind == "image":
            if not item.get("path"):
                raise PdfFormError("Image overlay requires path")
            path = (base / item["path"]).resolve()
            pdf.drawImage(ImageReader(str(path)), x, y, box_width, box_height, preserveAspectRatio=True, anchor="c", mask="auto")
    pdf.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def overlay_pdf(
    input_path: str | Path,
    output_path: str | Path,
    plan: dict[str, Any],
    *,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    validate_overlay_plan(plan)
    reader = PdfReader(input_path, strict=True)
    if reader.is_encrypted:
        raise PdfFormError("Overlay input must be unlocked first")
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in plan["items"]:
        if item["page"] > len(reader.pages):
            raise PdfFormError(f"Overlay page {item['page']} exceeds PDF page count {len(reader.pages)}")
        grouped.setdefault(item["page"], []).append(item)
    writer = PdfWriter()
    base = Path(base_dir or ".").resolve()
    for number, page in enumerate(reader.pages, start=1):
        writer.add_page(page)
        if number in grouped:
            target = writer.pages[-1]
            overlay = _overlay_for_page(
                float(target.mediabox.width), float(target.mediabox.height), grouped[number], base
            )
            target.merge_page(overlay)
    if reader.metadata:
        writer.add_metadata({str(key): str(value) for key, value in reader.metadata.items() if value is not None})
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        writer.write(handle)
    return {
        "output": str(destination),
        "pages": len(writer.pages),
        "items": len(plan["items"]),
        "items_by_page": {str(page): len(items) for page, items in sorted(grouped.items())},
    }


def overlay_pdf_file(input_path: str | Path, output_path: str | Path, plan_path: str | Path) -> dict[str, Any]:
    source = Path(plan_path).resolve()
    return overlay_pdf(input_path, output_path, read_json(source), base_dir=source.parent)
