from __future__ import annotations

import importlib.metadata
import platform
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .docx_build import build_docx
from .libreoffice import find_soffice, soffice_version
from .microsoft_oracle import microsoft_oracle_available
from .office_runtime import available_office_backends, preferred_office_backend
from .openxml_sdk import find_standalone_validator, openxml_validator_available
from .pdf_build import build_pdf
from .pdf_ocr import ocr_pdf
from .pdf_qa import validate_pdf
from .pptx_build import build_pptx
from .pptx_qa import validate_pptx
from .qa import validate_docx
from .wasm_ocr import find_wasm_ocr, wasm_ocr_version
from .wasm_office import wasm_office_version
from .xlsx_build import build_xlsx
from .xlsx_qa import validate_xlsx

PACKAGES = [
    "lxml",
    "python-docx",
    "openpyxl",
    "pandas",
    "python-pptx",
    "pypdf",
    "pypdfium2",
    "pdfplumber",
    "reportlab",
    "pytesseract",
]


def _package_versions() -> dict[str, str | None]:
    result = {}
    for name in PACKAGES:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def _font_inventory() -> dict[str, bool]:
    paths = {
        "dejavu_sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "dejavu_sans_bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "carlito": "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
        "caladea": "/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf",
    }
    return {name: Path(path).exists() for name, path in paths.items()}


def _self_test() -> dict[str, Any]:
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="documentctl-doctor-") as temporary:
        root = Path(temporary)
        docx = build_docx(
            {
                "footer": {"page_numbers": True},
                "content": [
                    {"type": "heading", "level": 1, "text": "Self test"},
                    {"type": "paragraph", "text": "DOCX pipeline"},
                ],
            },
            root / "test.docx",
        )
        results["docx"] = validate_docx(docx)["passed"]
        xlsx = build_xlsx(
            {
                "sheets": [
                    {
                        "name": "Model",
                        "cells": [
                            {"cell": "A1", "value": 2, "style": "input"},
                            {"cell": "A2", "formula": "=A1*2", "style": "formula"},
                        ],
                    }
                ]
            },
            root / "test.xlsx",
        )
        results["xlsx"] = validate_xlsx(xlsx)["passed"]
        pptx = build_pptx(
            {"slides": [{"layout": "title", "title": "Self test", "subtitle": "PPTX pipeline"}]},
            root / "test.pptx",
        )
        results["pptx"] = validate_pptx(pptx)["passed"]
        pdf = build_pdf(
            {"content": [{"type": "heading", "level": 1, "text": "Self test"}]},
            root / "test.pdf",
        )
        results["pdf"] = validate_pdf(pdf, render=True, render_dir=root / "pdf-render")["passed"]
        ocr = ocr_pdf(pdf, root / "test-ocr.pdf", language="eng", dpi=150)
        results["ocr"] = ocr["pages"] == 1 and validate_pdf(
            root / "test-ocr.pdf", require_text=["Self test"]
        )["passed"]
    results["passed"] = all(results.values())
    return results


def doctor(*, self_test: bool = False) -> dict[str, Any]:
    soffice = find_soffice()
    office_backends = available_office_backends()
    office_backend = preferred_office_backend()
    tesseract = shutil.which("tesseract")
    dotnet = shutil.which("dotnet")
    fonts = _font_inventory()
    packages = _package_versions()
    report: dict[str, Any] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "packages": packages,
        "external_tools": {
            "soffice": str(soffice) if soffice else None,
            "soffice_version": soffice_version(soffice),
            "libreoffice_wasm": wasm_office_version(),
            "preferred_office_backend": office_backend,
            "tesseract": tesseract,
            "tesseract_wasm": wasm_ocr_version(),
            "dotnet": dotnet,
            "ooxml_validator": (
                str(find_standalone_validator())
                if find_standalone_validator()
                else None
            ),
        },
        "fonts": fonts,
        "capabilities": {
            "docx_structural": packages["python-docx"] is not None,
            "xlsx_structural": packages["openpyxl"] is not None,
            "pptx_structural": packages["python-pptx"] is not None,
            "pdf_full": packages["pypdf"] is not None and packages["pypdfium2"] is not None and fonts["dejavu_sans"],
            "office_rendering": office_backend is not None,
            "office_backends": office_backends,
            "openxml_sdk_validation": openxml_validator_available(),
            "ocr": (
                tesseract is not None and packages["pytesseract"] is not None
            ) or find_wasm_ocr() is not None,
            "microsoft_graph_oracle": microsoft_oracle_available(),
        },
        "self_test": _self_test() if self_test else None,
    }
    report["core_ready"] = all(
        report["capabilities"][key]
        for key in ("docx_structural", "xlsx_structural", "pptx_structural", "pdf_full")
    )
    return report
