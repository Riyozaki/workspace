from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
import pytesseract
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .errors import ToolUnavailableError
from .pdf_build import _register_fonts
from .wasm_ocr import find_wasm_ocr, recognize_images_with_wasm


def _native_ocr(
    source: Path,
    destination: Path,
    language: str,
    dpi: int,
    timeout_per_page: int,
) -> dict[str, Any]:
    document = pdfium.PdfDocument(str(source))
    writer = PdfWriter()
    page_stats = []
    scale = dpi / 72
    try:
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil().convert("RGB")
            data = pytesseract.image_to_pdf_or_hocr(
                image,
                extension="pdf",
                lang=language,
                config=f"--dpi {dpi}",
                timeout=timeout_per_page,
            )
            result_page = PdfReader(io.BytesIO(data)).pages[0]
            writer.add_page(result_page)
            text = result_page.extract_text() or ""
            page_stats.append(
                {"page": index + 1, "characters": len(text), "words": len(text.split())}
            )
            image.close()
            bitmap.close()
            page.close()
    finally:
        document.close()
    with destination.open("wb") as handle:
        writer.write(handle)
    return {
        "engine": "tesseract-native",
        "pages": len(writer.pages),
        "page_stats": page_stats,
    }


def _wasm_ocr(
    source: Path,
    destination: Path,
    language: str,
    dpi: int,
    timeout_per_page: int,
) -> dict[str, Any]:
    document = pdfium.PdfDocument(str(source))
    scale = dpi / 72
    page_sizes: list[tuple[float, float]] = []
    with tempfile.TemporaryDirectory(prefix="documentctl-ocr-wasm-") as temporary:
        root = Path(temporary)
        images = []
        try:
            for index in range(len(document)):
                page = document[index]
                width, height = page.get_size()
                page_sizes.append((width, height))
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil().convert("RGB")
                path = root / f"page-{index + 1:04d}.png"
                image.save(path, format="PNG", optimize=True)
                images.append(path)
                image.close()
                bitmap.close()
                page.close()
        finally:
            document.close()
        recognized = recognize_images_with_wasm(
            images,
            language=language,
            timeout=max(300, timeout_per_page * len(images)),
        )
        fonts = _register_fonts()
        writer = PdfWriter()
        page_stats = []
        for index, (image_path, page_size, result) in enumerate(
            zip(images, page_sizes, recognized["results"], strict=True),
            start=1,
        ):
            width, height = page_size
            buffer = io.BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=(width, height))
            pdf.drawImage(
                ImageReader(str(image_path)),
                0,
                0,
                width=width,
                height=height,
                preserveAspectRatio=False,
                mask="auto",
            )
            text_object = pdf.beginText(2, height - 6)
            text_object.setFont(fonts[0], 5)
            text_object.setTextRenderMode(3)  # invisible but searchable
            for line in result["text"].splitlines():
                text_object.textLine(line)
            pdf.drawText(text_object)
            pdf.showPage()
            pdf.save()
            buffer.seek(0)
            writer.add_page(PdfReader(buffer).pages[0])
            text = result["text"]
            page_stats.append(
                {
                    "page": index,
                    "characters": len(text),
                    "words": len(text.split()),
                    "duration_ms": result.get("durationMs"),
                }
            )
        with destination.open("wb") as handle:
            writer.write(handle)
    return {
        "engine": recognized["engine"],
        "pages": len(writer.pages),
        "page_stats": page_stats,
    }


def ocr_pdf(
    input_path: str | Path,
    output_path: str | Path,
    *,
    language: str = "eng",
    dpi: int = 300,
    timeout_per_page: int = 120,
) -> dict[str, Any]:
    source = Path(input_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("tesseract") is not None:
        result = _native_ocr(source, destination, language, dpi, timeout_per_page)
    elif find_wasm_ocr() is not None:
        result = _wasm_ocr(source, destination, language, dpi, timeout_per_page)
    else:
        raise ToolUnavailableError(
            "Neither native Tesseract nor the pinned Tesseract.js WASM runtime is available"
        )
    return {
        "input": str(source),
        "output": str(destination),
        "language": language,
        "dpi": dpi,
        **result,
    }
