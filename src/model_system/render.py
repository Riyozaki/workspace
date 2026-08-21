from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat

from .blender_runtime import run_blender_worker
from .security import inspect_glb_container
from .util import sha256_file, write_json


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ):
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _analyze(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        gray = ImageOps.grayscale(rgb)
        histogram = gray.histogram()
        total = max(1, gray.width * gray.height)
        return {
            "path": str(path),
            "width": rgb.width,
            "height": rgb.height,
            "mean_luminance": round(ImageStat.Stat(gray).mean[0], 3),
            "near_black_fraction": round(sum(histogram[:8]) / total, 6),
            "near_white_fraction": round(sum(histogram[248:]) / total, 6),
            "likely_blank": max(histogram) / total > 0.995,
        }


def create_contact_sheet(images: list[Path], output: Path) -> Path:
    with Image.open(images[0]) as sample:
        tile = min(512, max(sample.width, sample.height))
    label_height = 42
    gutter = 18
    columns = 2
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile + (columns + 1) * gutter, rows * (tile + label_height) + (rows + 1) * gutter), "#E9EDF2")
    draw = ImageDraw.Draw(sheet)
    font = _font(20)
    for index, path in enumerate(images):
        row, column = divmod(index, columns)
        x = gutter + column * (tile + gutter)
        y = gutter + row * (tile + label_height + gutter)
        with Image.open(path) as original:
            image = original.convert("RGB")
            image.thumbnail((tile, tile), Image.Resampling.LANCZOS)
            frame = Image.new("RGB", (tile, tile), "#111827")
            frame.paste(image, ((tile - image.width) // 2, (tile - image.height) // 2))
            sheet.paste(frame, (x, y))
        label = path.stem
        box = draw.textbbox((0, 0), label, font=font)
        draw.text((x + (tile - (box[2] - box[0])) / 2, y + tile + 8), label, font=font, fill="#243447")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=True)
    sheet.close()
    return output


def render_model(
    model_path: str | Path,
    output_dir: str | Path,
    *,
    resolution: int = 512,
    samples: int = 24,
    views: list[str] | None = None,
    background: str = "#162333",
    transparent: bool = False,
    timeout: int = 900,
) -> dict[str, Any]:
    source = Path(model_path).resolve()
    inspect_glb_container(source)
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    options = {
        "resolution": resolution,
        "samples": samples,
        "views": views or ["perspective", "front", "right", "back"],
        "background": background,
        "transparent": transparent,
    }
    options_path = destination / "render-options.json"
    options_path.write_text(json.dumps(options, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    worker = run_blender_worker(
        ["render", str(source), str(destination / "views"), "--options", str(options_path)],
        timeout=timeout,
    )
    images = [Path(value) for value in worker["images"]]
    contact_sheet = create_contact_sheet(images, destination / "contact-sheet.png")
    analysis = [_analyze(path) for path in images]
    report = {
        "input": str(source),
        "input_sha256": sha256_file(source),
        "renderer": "Blender Cycles CPU",
        "runtime": worker.get("blender"),
        "views": [str(path) for path in images],
        "contact_sheet": str(contact_sheet),
        "analysis": analysis,
        "summary": {"blank_views": [item["path"] for item in analysis if item["likely_blank"]]},
        "settings": options,
        "bounds": worker.get("bounds"),
    }
    write_json(destination / "render-report.json", report)
    return report
