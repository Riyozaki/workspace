from __future__ import annotations

import importlib.resources
import io
import json
from pathlib import Path
from typing import Any

import jsonschema
import pypdfium2 as pdfium
from PIL import ImageDraw
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .errors import DocumentSystemError
from .pdf_extract import extract_pdf
from .util import read_json


class PdfRedactionError(DocumentSystemError):
    pass


def validate_redaction_plan(plan: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath(
        "schemas/pdf-redact.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(plan)


def redact_pdf(
    input_path: str | Path,
    output_path: str | Path,
    plan: dict[str, Any],
) -> dict[str, Any]:
    validate_redaction_plan(plan)
    source = Path(input_path)
    dpi = plan.get("dpi", 300)
    scale = dpi / 72
    document = pdfium.PdfDocument(str(source))
    page_count = len(document)
    grouped: dict[int, list[dict[str, Any]]] = {}
    for rectangle in plan["rectangles"]:
        if rectangle["page"] > page_count:
            document.close()
            raise PdfRedactionError(
                f"Redaction page {rectangle['page']} exceeds page count {page_count}"
            )
        grouped.setdefault(rectangle["page"], []).append(rectangle)
    writer = PdfWriter()
    page_reports = []
    try:
        for index in range(len(document)):
            page_number = index + 1
            page = document[index]
            width_pt, height_pt = page.get_size()
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil().convert("RGB")
            draw = ImageDraw.Draw(image)
            for rectangle in grouped.get(page_number, []):
                if (
                    rectangle["x"] + rectangle["width"] > width_pt
                    or rectangle["y"] + rectangle["height"] > height_pt
                ):
                    raise PdfRedactionError(
                        f"Redaction rectangle exceeds page {page_number} bounds"
                    )
                color = "#" + rectangle.get("color", "000000")
                box = (
                    round(rectangle["x"] * scale),
                    round(rectangle["y"] * scale),
                    round((rectangle["x"] + rectangle["width"]) * scale),
                    round((rectangle["y"] + rectangle["height"]) * scale),
                )
                draw.rectangle(box, fill=color)
            image_buffer = io.BytesIO()
            image.save(image_buffer, format="PNG", optimize=True)
            image_buffer.seek(0)
            page_buffer = io.BytesIO()
            pdf = canvas.Canvas(page_buffer, pagesize=(width_pt, height_pt))
            pdf.drawImage(
                ImageReader(image_buffer),
                0,
                0,
                width=width_pt,
                height=height_pt,
                preserveAspectRatio=False,
                mask="auto",
            )
            pdf.showPage()
            pdf.save()
            page_buffer.seek(0)
            writer.add_page(PdfReader(page_buffer).pages[0])
            page_reports.append(
                {
                    "page": page_number,
                    "rectangles": len(grouped.get(page_number, [])),
                    "width_pt": width_pt,
                    "height_pt": height_pt,
                }
            )
            image.close()
            bitmap.close()
            page.close()
    finally:
        document.close()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    writer.add_metadata(
        {
            "/Title": "Redacted document",
            "/Producer": "documentctl secure raster redaction",
        }
    )
    with destination.open("wb") as handle:
        writer.write(handle)
    extracted = extract_pdf(destination)
    failed_terms = [
        term for term in plan.get("verify_absent", []) if term.casefold() in extracted["text"].casefold()
    ]
    if failed_terms:
        raise PdfRedactionError(
            "Redacted output still exposes text terms: " + ", ".join(failed_terms)
        )
    return {
        "input": str(source),
        "output": str(destination),
        "mode": "secure-raster-reconstruction",
        "dpi": dpi,
        "pages": page_reports,
        "rectangles": len(plan["rectangles"]),
        "text_objects_remaining": extracted["characters"],
        "verified_absent": plan.get("verify_absent", []),
        "warning": (
            "Raster reconstruction removes original text/object streams. "
            "Visual review and OCR verification are still required to prove boxes cover intended content."
        ),
    }


def redact_pdf_file(
    input_path: str | Path,
    output_path: str | Path,
    plan_path: str | Path,
) -> dict[str, Any]:
    return redact_pdf(input_path, output_path, read_json(plan_path))
