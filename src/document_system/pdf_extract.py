from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pdfplumber
from pypdf import PdfReader

from .errors import UnsupportedDocumentError
from .security import detect_format
from .util import sha256_file

PLACEHOLDER_RE = re.compile(r"\{\{[^{}\n]{1,120}\}\}|<<[^<>\n]{1,120}>>|\b(?:TODO|TBD)\b", re.IGNORECASE)
RISK_TOKENS = {
    b"/JavaScript": "javascript",
    b"/Launch": "launch-action",
    b"/EmbeddedFiles": "embedded-files",
    b"/RichMedia": "rich-media",
    b"/XFA": "xfa-form",
}


def _serialize_field(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_serialize_field(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_field(item) for key, item in value.items()}
    return str(value)


def extract_pdf(
    path: str | Path,
    *,
    password: str | None = None,
    extract_tables: bool = False,
    max_table_pages: int = 100,
    max_pages: int = 5_000,
    max_bytes: int = 1024 * 1024 * 1024,
) -> dict[str, Any]:
    source = Path(path)
    if source.stat().st_size > max_bytes:
        raise UnsupportedDocumentError(
            f"PDF is {source.stat().st_size} bytes; safety limit is {max_bytes}"
        )
    if detect_format(source) != "pdf":
        raise UnsupportedDocumentError(f"Not a PDF: {source}")
    reader = PdfReader(source, strict=True)
    encrypted = reader.is_encrypted
    if encrypted:
        if not password or reader.decrypt(password) == 0:
            return {
                "path": str(source),
                "sha256": sha256_file(source),
                "encrypted": True,
                "unlocked": False,
                "page_count": None,
            }

    if len(reader.pages) > max_pages:
        raise UnsupportedDocumentError(
            f"PDF has {len(reader.pages)} pages; safety limit is {max_pages}"
        )

    found_risks: set[str] = set()
    tail = b""
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value = tail + chunk
            found_risks.update(label for token, label in RISK_TOKENS.items() if token in value)
            tail = value[-64:]
    catalog = reader.trailer.get("/Root")
    if catalog:
        catalog = catalog.get_object()
        open_action = catalog.get("/OpenAction")
        if open_action and hasattr(open_action, "get_object"):
            open_action = open_action.get_object()
        if isinstance(open_action, dict):
            action_type = str(open_action.get("/S", ""))
            if action_type and action_type not in {"/GoTo"}:
                found_risks.add(f"open-action:{action_type.lstrip('/')}")
        additional = catalog.get("/AA")
        if additional:
            found_risks.add("catalog-additional-actions")
    risks = sorted(found_risks)
    pages: list[dict[str, Any]] = []
    placeholders: list[dict[str, Any]] = []
    total_text = []
    fonts: set[str] = set()
    unembedded_fonts: set[str] = set()
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        total_text.append(text)
        for match in PLACEHOLDER_RE.finditer(text):
            placeholders.append({"page": number, "value": match.group(0)})
        media = page.mediabox
        crop = page.cropbox
        resources = page.get("/Resources", {})
        if hasattr(resources, "get_object"):
            resources = resources.get_object()
        font_dict = resources.get("/Font", {}) if isinstance(resources, dict) else {}
        if hasattr(font_dict, "get_object"):
            font_dict = font_dict.get_object()
        page_fonts = []
        for _key, font_ref in (font_dict.items() if isinstance(font_dict, dict) else []):
            font = font_ref.get_object()
            name = str(font.get("/BaseFont", "unknown"))
            page_fonts.append(name)
            fonts.add(name)
            descriptor = font.get("/FontDescriptor")
            embedded = False
            if descriptor:
                descriptor = descriptor.get_object()
                embedded = any(descriptor.get(key) is not None for key in ("/FontFile", "/FontFile2", "/FontFile3"))
            # Standard 14 fonts need not be embedded; every other font should be.
            standard = any(name.lstrip("/").startswith(base) for base in ("Helvetica", "Times", "Courier", "Symbol", "ZapfDingbats"))
            if not embedded and not standard:
                unembedded_fonts.add(name)
        xobjects = resources.get("/XObject", {}) if isinstance(resources, dict) else {}
        if hasattr(xobjects, "get_object"):
            xobjects = xobjects.get_object()
        image_count = 0
        for _key, obj_ref in (xobjects.items() if isinstance(xobjects, dict) else []):
            obj = obj_ref.get_object()
            if obj.get("/Subtype") == "/Image":
                image_count += 1
        annotations = page.get("/Annots", []) or []
        pages.append(
            {
                "number": number,
                "width_pt": float(media.width),
                "height_pt": float(media.height),
                "crop_box": [float(crop.left), float(crop.bottom), float(crop.right), float(crop.top)],
                "rotation": int(page.get("/Rotate", 0) or 0),
                "characters": len(text),
                "words": len(text.split()),
                "text": text,
                "fonts": sorted(page_fonts),
                "images": image_count,
                "annotations": len(annotations),
            }
        )

    fields = reader.get_fields() or {}
    tables: list[dict[str, Any]] = []
    if extract_tables and len(reader.pages) <= max_table_pages:
        with pdfplumber.open(source, password=password) as document:
            for page_number, page in enumerate(document.pages, start=1):
                for table_number, table in enumerate(page.extract_tables(), start=1):
                    tables.append(
                        {
                            "page": page_number,
                            "table": table_number,
                            "rows": table,
                            "row_count": len(table),
                            "column_count": max((len(row) for row in table), default=0),
                        }
                    )

    metadata = reader.metadata or {}
    return {
        "path": str(source),
        "sha256": sha256_file(source),
        "bytes": source.stat().st_size,
        "encrypted": encrypted,
        "unlocked": True,
        "page_count": len(reader.pages),
        "pages": pages,
        "text": "\n\n".join(total_text),
        "characters": sum(len(value) for value in total_text),
        "words": sum(len(value.split()) for value in total_text),
        "metadata": {str(key): _serialize_field(value) for key, value in metadata.items()},
        "form_fields": {str(name): _serialize_field(value) for name, value in fields.items()},
        "form_field_count": len(fields),
        "fonts": sorted(fonts),
        "unembedded_fonts": sorted(unembedded_fonts),
        "risk_features": risks,
        "placeholders": placeholders,
        "tables": tables,
    }
