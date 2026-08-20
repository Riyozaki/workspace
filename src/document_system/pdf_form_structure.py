from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pdfplumber
from PIL import Image, ImageDraw, ImageFont

from .render import raster_pdf
from .util import write_json


def _intersection_ratio(first: dict[str, float], second: dict[str, float]) -> float:
    left = max(first["x"], second["x"])
    top = max(first["y"], second["y"])
    right = min(first["x"] + first["width"], second["x"] + second["width"])
    bottom = min(first["y"] + first["height"], second["y"] + second["height"])
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    minimum = min(first["width"] * first["height"], second["width"] * second["height"])
    return intersection / max(1, minimum)


def _label_for(candidate: dict[str, float], words: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    center = candidate["y"] + candidate["height"] / 2
    left_words = [
        word
        for word in words
        if word["x1"] <= candidate["x"] + 3
        and 0 <= candidate["x"] - word["x1"] <= 220
        and abs((word["top"] + word["bottom"]) / 2 - center) <= max(10, candidate["height"])
    ]
    if left_words:
        nearest_top = min(left_words, key=lambda word: candidate["x"] - word["x1"])["top"]
        line = [word for word in left_words if abs(word["top"] - nearest_top) < 3]
        line.sort(key=lambda word: word["x0"])
        return " ".join(word["text"] for word in line), "left"
    above = [
        word
        for word in words
        if 0 <= candidate["y"] - word["bottom"] <= 35
        and word["x1"] >= candidate["x"] - 10
        and word["x0"] <= candidate["x"] + candidate["width"] + 10
    ]
    if above:
        nearest_top = max(word["top"] for word in above)
        line = [word for word in above if abs(word["top"] - nearest_top) < 3]
        line.sort(key=lambda word: word["x0"])
        return " ".join(word["text"] for word in line), "above"
    return None, None


def infer_pdf_form_structure(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    pages = []
    total = 0
    with pdfplumber.open(source) as document:
        for page_number, page in enumerate(document.pages, start=1):
            words = page.extract_words(keep_blank_chars=False, use_text_flow=True)
            candidates: list[dict[str, Any]] = []
            for rect in page.rects:
                width = float(rect["x1"] - rect["x0"])
                height = float(rect["bottom"] - rect["top"])
                if 7 <= width <= 450 and 7 <= height <= 45:
                    field_type = "checkbox" if 0.7 <= width / max(height, 1) <= 1.3 and width <= 25 else "text-box"
                    candidates.append(
                        {
                            "type": field_type,
                            "x": round(float(rect["x0"]), 2),
                            "y": round(float(rect["top"]), 2),
                            "width": round(width, 2),
                            "height": round(height, 2),
                            "source": "rectangle",
                        }
                    )
            for line in page.lines:
                width = abs(float(line["x1"] - line["x0"]))
                height = abs(float(line["bottom"] - line["top"]))
                if width >= 30 and height <= 2:
                    candidates.append(
                        {
                            "type": "text-line",
                            "x": round(float(min(line["x0"], line["x1"])), 2),
                            "y": round(max(0.0, float(line["top"]) - 16), 2),
                            "width": round(width, 2),
                            "height": 18.0,
                            "source": "line",
                        }
                    )
            deduplicated: list[dict[str, Any]] = []
            for candidate in sorted(candidates, key=lambda item: (item["y"], item["x"], item["width"])):
                if any(_intersection_ratio(candidate, existing) > 0.75 for existing in deduplicated):
                    continue
                label, position = _label_for(candidate, words)
                candidate["label"] = label
                candidate["label_position"] = position
                candidate["confidence"] = round(0.88 if label else 0.48, 2)
                candidate["field_id"] = f"p{page_number}-f{len(deduplicated) + 1}"
                deduplicated.append(candidate)
            total += len(deduplicated)
            pages.append(
                {
                    "page": page_number,
                    "width": float(page.width),
                    "height": float(page.height),
                    "fields": deduplicated,
                }
            )
    return {
        "path": str(source),
        "page_count": len(pages),
        "field_count": total,
        "pages": pages,
        "coordinate_system": "PDF points from top-left",
        "warning": "Candidates are geometric inferences and require visual confirmation before filling.",
    }


def create_form_structure_images(
    path: str | Path,
    structure: dict[str, Any],
    output_dir: str | Path,
    *,
    dpi: int = 144,
) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="documentctl-form-structure-") as temporary:
        pages = raster_pdf(path, temporary, dpi=dpi)
        outputs = []
        font = ImageFont.load_default()
        for page_path, page_info in zip(pages, structure["pages"], strict=True):
            with Image.open(page_path) as original:
                image = original.convert("RGB")
            draw = ImageDraw.Draw(image)
            scale_x = image.width / page_info["width"]
            scale_y = image.height / page_info["height"]
            for field in page_info["fields"]:
                box = (
                    round(field["x"] * scale_x),
                    round(field["y"] * scale_y),
                    round((field["x"] + field["width"]) * scale_x),
                    round((field["y"] + field["height"]) * scale_y),
                )
                draw.rectangle(box, outline="#E53935", width=3)
                label = f"{field['field_id']} {field.get('label') or '?'}"
                draw.text((box[0], max(0, box[1] - 14)), label, fill="#E53935", font=font)
            output = destination / f"form-structure-{page_info['page']:03d}.png"
            image.save(output, format="PNG", optimize=True)
            image.close()
            outputs.append(output)
    return outputs


def infer_and_save_form_structure(
    path: str | Path,
    output_json: str | Path,
    *,
    image_dir: str | Path | None = None,
    dpi: int = 144,
) -> dict[str, Any]:
    structure = infer_pdf_form_structure(path)
    if image_dir:
        structure["validation_images"] = [
            str(value)
            for value in create_form_structure_images(path, structure, image_dir, dpi=dpi)
        ]
    write_json(output_json, structure)
    return structure
