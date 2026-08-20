from __future__ import annotations

import math
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps, ImageStat

from .errors import UnsupportedDocumentError
from .office_runtime import convert_with_office
from .security import detect_format
from .util import sha256_file, write_json


def raster_pdf(
    pdf_path: str | Path,
    output_dir: str | Path,
    *,
    dpi: int = 144,
    prefix: str = "page",
    max_pages: int = 2_000,
) -> list[Path]:
    source = Path(pdf_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(str(source))
    page_count = len(document)
    if page_count > max_pages:
        document.close()
        raise ValueError(f"PDF has {page_count} pages; render safety limit is {max_pages}")
    paths: list[Path] = []
    digits = max(3, len(str(len(document))))
    scale = dpi / 72.0
    try:
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=scale, rotation=0)
            image = bitmap.to_pil().convert("RGB")
            output = destination / f"{prefix}-{index + 1:0{digits}d}.png"
            image.save(output, format="PNG", optimize=True)
            paths.append(output)
            image.close()
            bitmap.close()
            page.close()
    finally:
        document.close()
    return paths


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def create_contact_sheets(
    images: Iterable[str | Path],
    output: str | Path,
    *,
    columns: int = 4,
    max_pages_per_sheet: int = 20,
    tile_width: int | None = None,
    tile_height: int | None = None,
) -> list[Path]:
    paths = [Path(value) for value in images]
    if not paths:
        raise ValueError("No images supplied for contact sheet")
    if tile_width is None or tile_height is None:
        with Image.open(paths[0]) as sample:
            aspect = sample.width / max(1, sample.height)
        if aspect > 1.2:
            tile_width = tile_width or 480
            tile_height = tile_height or round(tile_width / aspect)
        else:
            tile_width = tile_width or 360
            tile_height = tile_height or round(tile_width / max(0.55, aspect))
    columns = max(1, min(columns, 6))
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    label_height = 34
    gutter = 18
    background = "#E9EDF2"
    results: list[Path] = []
    font = _font(18)

    chunks = [paths[index : index + max_pages_per_sheet] for index in range(0, len(paths), max_pages_per_sheet)]
    for sheet_index, chunk in enumerate(chunks, start=1):
        rows = math.ceil(len(chunk) / columns)
        width = gutter + columns * (tile_width + gutter)
        height = gutter + rows * (tile_height + label_height + gutter)
        sheet = Image.new("RGB", (width, height), background)
        draw = ImageDraw.Draw(sheet)
        for index, path in enumerate(chunk):
            row, column = divmod(index, columns)
            x = gutter + column * (tile_width + gutter)
            y = gutter + row * (tile_height + label_height + gutter)
            with Image.open(path) as original:
                page = original.convert("RGB")
                page.thumbnail((tile_width, tile_height), Image.Resampling.LANCZOS)
                frame = Image.new("RGB", (tile_width, tile_height), "white")
                px = (tile_width - page.width) // 2
                py = (tile_height - page.height) // 2
                frame.paste(page, (px, py))
                frame = ImageOps.expand(frame, border=1, fill="#9AA4B2")
                sheet.paste(frame, (x, y))
            label = f"{path.stem}"
            bbox = draw.textbbox((0, 0), label, font=font)
            draw.text(
                (x + (tile_width - (bbox[2] - bbox[0])) / 2, y + tile_height + 7),
                label,
                fill="#243447",
                font=font,
            )
        result = (
            output_path
            if len(chunks) == 1
            else output_path.with_name(f"{output_path.stem}-{sheet_index:02d}{output_path.suffix or '.png'}")
        )
        if not result.suffix:
            result = result.with_suffix(".png")
        sheet.save(result, format="PNG", optimize=True)
        sheet.close()
        results.append(result)
    return results


def analyze_page_image(path: str | Path) -> dict[str, Any]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        gray = ImageOps.grayscale(rgb)
        stat = ImageStat.Stat(gray)
        white = Image.new("L", gray.size, 255)
        difference = ImageChops.difference(gray, white)
        bbox = difference.point(lambda value: 255 if value > 8 else 0).getbbox()
        histogram = gray.histogram()
        total = max(1, gray.width * gray.height)
        dark = sum(histogram[:245])
        very_dark = sum(histogram[:80])
        border = max(2, min(gray.size) // 100)
        border_pixels = []
        border_pixels.extend(gray.crop((0, 0, gray.width, border)).tobytes())
        border_pixels.extend(gray.crop((0, gray.height - border, gray.width, gray.height)).tobytes())
        border_pixels.extend(gray.crop((0, 0, border, gray.height)).tobytes())
        border_pixels.extend(gray.crop((gray.width - border, 0, gray.width, gray.height)).tobytes())
        edge_ink = sum(1 for pixel in border_pixels if pixel < 245) / max(1, len(border_pixels))
        return {
            "path": str(path),
            "width": rgb.width,
            "height": rgb.height,
            "mean_luminance": round(stat.mean[0], 3),
            "ink_coverage": round(dark / total, 6),
            "very_dark_coverage": round(very_dark / total, 6),
            "content_bbox": list(bbox) if bbox else None,
            "edge_ink_coverage": round(edge_ink, 6),
            "likely_blank": dark / total < 0.0005,
            "possible_edge_clipping": edge_ink > 0.02,
        }


def render_document(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    dpi: int = 144,
    contact_sheet: bool = True,
    timeout: int = 180,
) -> dict[str, Any]:
    source = Path(input_path).resolve()
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    fmt = detect_format(source)
    conversion: dict[str, Any] | None = None

    if fmt == "pdf":
        pdf = destination / source.name
        if source != pdf:
            shutil.copy2(source, pdf)
    elif fmt in {"docx", "xlsx", "pptx", "doc", "xls", "ppt", "odf"}:
        conversion = convert_with_office(source, destination, "pdf", timeout=timeout)
        pdf = Path(conversion["output"])
    else:
        raise UnsupportedDocumentError(f"Cannot render detected format {fmt}: {source}")

    pages_dir = destination / "pages"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)
    pages = raster_pdf(pdf, pages_dir, dpi=dpi)
    sheets: list[Path] = []
    if contact_sheet:
        sheets = create_contact_sheets(pages, destination / "contact-sheet.png")
    page_analysis = [analyze_page_image(page) for page in pages]
    report = {
        "input": str(source),
        "input_sha256": sha256_file(source),
        "format": fmt,
        "pdf": str(pdf),
        "pages": [str(path) for path in pages],
        "page_count": len(pages),
        "contact_sheets": [str(path) for path in sheets],
        "dpi": dpi,
        "conversion": conversion,
        "analysis": page_analysis,
        "summary": {
            "blank_pages": [index + 1 for index, item in enumerate(page_analysis) if item["likely_blank"]],
            "possible_edge_clipping_pages": [
                index + 1 for index, item in enumerate(page_analysis) if item["possible_edge_clipping"]
            ],
        },
    }
    write_json(destination / "render-report.json", report)
    return report
