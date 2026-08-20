from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .errors import UnsupportedDocumentError
from .office_runtime import convert_with_office
from .render import render_document
from .security import detect_format

MODERN_TARGETS = {"docx", "xlsx", "pptx"}
LEGACY_TO_MODERN = {"doc": "docx", "xls": "xlsx", "ppt": "pptx"}
FILTERS = {
    "docx": "Office Open XML Text",
    "xlsx": "Calc MS Excel 2007 XML",
    "pptx": "Impress MS PowerPoint 2007 XML",
}


def convert_document(
    input_path: str | Path,
    output: str | Path,
    *,
    target: str,
    timeout: int = 240,
    dpi: int = 144,
) -> dict[str, Any]:
    source = Path(input_path).resolve()
    destination = Path(output).resolve()
    source_format = detect_format(source)
    target = target.lower().lstrip(".")

    if target == "images":
        destination.mkdir(parents=True, exist_ok=True)
        report = render_document(source, destination, dpi=dpi, timeout=timeout)
        return {
            "input": str(source),
            "source_format": source_format,
            "target": "images",
            "output": str(destination),
            "pages": report["page_count"],
            "files": report["pages"],
            "contact_sheets": report["contact_sheets"],
        }

    if target == source_format:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source != destination:
            shutil.copy2(source, destination)
        return {
            "input": str(source),
            "source_format": source_format,
            "target": target,
            "output": str(destination),
            "lossy": False,
            "copied": True,
        }

    if target == "pdf" and source_format in {
        "docx",
        "xlsx",
        "pptx",
        "doc",
        "xls",
        "ppt",
        "odf",
    }:
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = convert_with_office(source, destination.parent, "pdf", timeout=timeout)
        produced = Path(result["output"])
        if produced != destination:
            shutil.move(produced, destination)
        return {
            "input": str(source),
            "source_format": source_format,
            "target": "pdf",
            "output": str(destination),
            "lossy": source_format in {"doc", "xls", "ppt", "odf"},
            "conversion": result,
        }

    if target in MODERN_TARGETS and source_format in {"doc", "xls", "ppt", "odf"}:
        expected = LEGACY_TO_MODERN.get(source_format)
        if expected and expected != target:
            raise UnsupportedDocumentError(
                f"Legacy {source_format} should convert to {expected}, not {target}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = convert_with_office(
            source,
            destination.parent,
            target,
            filter_name=FILTERS[target],
            timeout=timeout,
        )
        produced = Path(result["output"])
        if produced != destination:
            shutil.move(produced, destination)
        return {
            "input": str(source),
            "source_format": source_format,
            "target": target,
            "output": str(destination),
            "lossy": True,
            "conversion": result,
        }

    raise UnsupportedDocumentError(
        f"Unsupported conversion: {source_format} -> {target}. "
        "The system does not claim high-fidelity PDF-to-Office reconstruction."
    )
