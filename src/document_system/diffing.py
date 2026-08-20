from __future__ import annotations

import difflib
import math
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

from .docx_extract import extract_docx
from .render import render_document
from .security import detect_format, inspect_zip
from .util import sha256_bytes, sha256_file, write_json


def _part_hashes(path: Path) -> dict[str, str]:
    inspect_zip(path)
    with zipfile.ZipFile(path) as archive:
        return {
            info.filename: sha256_bytes(archive.read(info.filename))
            for info in archive.infolist()
            if not info.filename.endswith("/")
        }


def _visual_difference(left: Path, right: Path, output: Path) -> dict[str, Any]:
    with Image.open(left) as left_image, Image.open(right) as right_image:
        left_rgb = left_image.convert("RGB")
        right_rgb = right_image.convert("RGB")
        if left_rgb.size != right_rgb.size:
            return {
                "comparable": False,
                "left_size": list(left_rgb.size),
                "right_size": list(right_rgb.size),
                "reason": "page dimensions differ",
            }
        difference = ImageChops.difference(left_rgb, right_rgb)
        stat = ImageStat.Stat(difference)
        squared = sum(value * value for value in stat.rms) / 3
        rms = math.sqrt(squared)
        bbox = difference.getbbox()
        amplified = difference.point(lambda value: min(255, value * 4))
        output.parent.mkdir(parents=True, exist_ok=True)
        amplified.save(output, format="PNG", optimize=True)
        total = max(1, left_rgb.width * left_rgb.height)
        changed = sum(1 for pixel in difference.convert("L").tobytes() if pixel > 8)
        return {
            "comparable": True,
            "rms": round(rms, 5),
            "changed_pixel_ratio": round(changed / total, 8),
            "difference_bbox": list(bbox) if bbox else None,
            "difference_image": str(output),
        }


def diff_docx(
    original: str | Path,
    modified: str | Path,
    *,
    output_report: str | Path | None = None,
    visual: bool = False,
    visual_dir: str | Path | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    left = Path(original)
    right = Path(modified)
    if detect_format(left) != "docx" or detect_format(right) != "docx":
        raise ValueError("diff_docx requires two DOCX files")
    left_hashes = _part_hashes(left)
    right_hashes = _part_hashes(right)
    left_names, right_names = set(left_hashes), set(right_hashes)
    changed = sorted(
        name for name in left_names & right_names if left_hashes[name] != right_hashes[name]
    )
    left_text = extract_docx(left, revisions="accept")["text"]
    right_text = extract_docx(right, revisions="accept")["text"]
    text_diff = list(
        difflib.unified_diff(
            left_text.splitlines(),
            right_text.splitlines(),
            fromfile=left.name,
            tofile=right.name,
            lineterm="",
        )
    )
    report: dict[str, Any] = {
        "original": {"path": str(left), "sha256": sha256_file(left)},
        "modified": {"path": str(right), "sha256": sha256_file(right)},
        "package": {
            "added_parts": sorted(right_names - left_names),
            "removed_parts": sorted(left_names - right_names),
            "changed_parts": changed,
            "unchanged_parts": len(left_names & right_names) - len(changed),
        },
        "text": {
            "changed": left_text != right_text,
            "unified_diff": text_diff,
            "original_characters": len(left_text),
            "modified_characters": len(right_text),
        },
        "visual": None,
    }
    if visual:
        destination = Path(visual_dir or right.parent / f"{right.stem}-visual-diff")
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="documentctl-diff-") as tmp:
            tmp_path = Path(tmp)
            left_render = render_document(left, tmp_path / "left", timeout=timeout)
            right_render = render_document(right, tmp_path / "right", timeout=timeout)
            left_pages = [Path(value) for value in left_render["pages"]]
            right_pages = [Path(value) for value in right_render["pages"]]
            page_results = []
            for index in range(max(len(left_pages), len(right_pages))):
                if index >= len(left_pages) or index >= len(right_pages):
                    page_results.append(
                        {
                            "page": index + 1,
                            "comparable": False,
                            "reason": "page exists in only one document",
                        }
                    )
                    continue
                page_results.append(
                    {
                        "page": index + 1,
                        **_visual_difference(
                            left_pages[index],
                            right_pages[index],
                            destination / f"diff-{index + 1:03d}.png",
                        ),
                    }
                )
            report["visual"] = {
                "original_pages": len(left_pages),
                "modified_pages": len(right_pages),
                "pages": page_results,
            }
    if output_report:
        write_json(output_report, report)
    return report
