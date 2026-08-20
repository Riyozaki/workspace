from __future__ import annotations

import importlib.resources
import io
import json
from pathlib import Path
from typing import Any

import jsonschema
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from .errors import DocumentSystemError
from .util import read_json


class PdfTransformError(DocumentSystemError):
    pass


def parse_page_range(value: str | None, page_count: int) -> list[int]:
    if not value or value.lower() == "all":
        return list(range(page_count))
    result: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise PdfTransformError(f"Invalid descending page range: {token}")
            result.extend(range(start - 1, end))
        else:
            result.append(int(token) - 1)
    if any(index < 0 or index >= page_count for index in result):
        raise PdfTransformError(f"Page range {value!r} exceeds document with {page_count} pages")
    return result


def _watermark_page(width: float, height: float, config: dict[str, Any]) -> Any:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    color = config.get("color", "808080")
    pdf.setFillColorRGB(int(color[0:2], 16) / 255, int(color[2:4], 16) / 255, int(color[4:6], 16) / 255)
    if hasattr(pdf, "setFillAlpha"):
        pdf.setFillAlpha(config.get("opacity", 0.18))
    pdf.setFont("Helvetica-Bold", config.get("font_size", 48))
    pdf.translate(width / 2, height / 2)
    pdf.rotate(config.get("angle", 35))
    pdf.drawCentredString(0, 0, config["text"])
    pdf.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def validate_transform_plan(plan: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath("schemas/pdf-transform.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(plan)


def transform_pdf(plan: dict[str, Any], output_path: str | Path, *, base_dir: str | Path | None = None) -> dict[str, Any]:
    validate_transform_plan(plan)
    base = Path(base_dir or ".").resolve()
    writer = PdfWriter()
    source_pages: list[dict[str, Any]] = []
    for input_config in plan["inputs"]:
        path = (base / input_config["path"]).resolve()
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted and (not input_config.get("password") or reader.decrypt(input_config["password"]) == 0):
            raise PdfTransformError(f"Cannot unlock encrypted input: {path}")
        selected = parse_page_range(input_config.get("pages"), len(reader.pages))
        for index in selected:
            writer.add_page(reader.pages[index])
            source_pages.append({"path": str(path), "page": index + 1})

    for rotation in plan.get("rotate", []):
        for index in parse_page_range(rotation["pages"], len(writer.pages)):
            writer.pages[index].rotate(rotation["degrees"])
    if plan.get("watermark"):
        for page in writer.pages:
            page.merge_page(_watermark_page(float(page.mediabox.width), float(page.mediabox.height), plan["watermark"]))
    if plan.get("metadata"):
        metadata = {
            (key if key.startswith("/") else "/" + key.title()): value
            for key, value in plan["metadata"].items()
        }
        writer.add_metadata(metadata)
    if plan.get("encrypt"):
        config = plan["encrypt"]
        writer.encrypt(config["user_password"], config.get("owner_password") or config["user_password"], algorithm="AES-256")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        writer.write(handle)
    return {
        "output": str(destination),
        "pages": len(writer.pages),
        "source_pages": source_pages,
        "watermarked": bool(plan.get("watermark")),
        "encrypted": bool(plan.get("encrypt")),
    }


def transform_pdf_file(plan_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    source = Path(plan_path).resolve()
    return transform_pdf(read_json(source), output_path, base_dir=source.parent)
