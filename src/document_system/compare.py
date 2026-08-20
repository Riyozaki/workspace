from __future__ import annotations

import difflib
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .diffing import _visual_difference
from .docx_extract import extract_docx
from .errors import UnsupportedDocumentError
from .pdf_extract import extract_pdf
from .pptx_extract import extract_pptx
from .render import render_document
from .security import detect_format, inspect_zip
from .util import sha256_bytes, sha256_file, write_json
from .xlsx_extract import extract_xlsx


def _package_hashes(path: Path) -> dict[str, str]:
    inspect_zip(path)
    with zipfile.ZipFile(path) as archive:
        return {
            info.filename: sha256_bytes(archive.read(info.filename))
            for info in archive.infolist()
            if not info.filename.endswith("/")
        }


def _semantic_text(path: Path, fmt: str) -> str:
    if fmt == "docx":
        return extract_docx(path, revisions="accept")["text"]
    if fmt == "xlsx":
        workbook = extract_xlsx(path, include_cells=True, max_cells_per_sheet=100_000)
        lines: list[str] = []
        for sheet in workbook["sheets"]:
            lines.append(f"## {sheet['name']} [{sheet['state']}]")
            for cell in sheet.get("cells") or []:
                lines.append(f"{sheet['name']}!{cell['cell']}\t{cell['value']!r}\t{cell['number_format']}")
        return "\n".join(lines)
    if fmt == "pptx":
        deck = extract_pptx(path)
        return "\n\n".join(
            f"## Slide {slide['number']}: {slide['title'] or ''}\n{slide['text']}\n[notes] {slide['notes'] or ''}"
            for slide in deck["slides"]
        )
    if fmt == "pdf":
        return extract_pdf(path)["text"]
    raise UnsupportedDocumentError(f"Semantic comparison is unsupported for {fmt}")


def compare_documents(
    original: str | Path,
    modified: str | Path,
    *,
    output_report: str | Path | None = None,
    visual: bool = False,
    visual_dir: str | Path | None = None,
    timeout: int = 240,
) -> dict[str, Any]:
    left = Path(original).resolve()
    right = Path(modified).resolve()
    left_format = detect_format(left)
    right_format = detect_format(right)
    if left_format != right_format:
        raise UnsupportedDocumentError(
            f"Comparison requires matching formats; detected {left_format} and {right_format}"
        )
    fmt = left_format
    if fmt not in {"docx", "xlsx", "pptx", "pdf"}:
        raise UnsupportedDocumentError(f"Comparison is unsupported for {fmt}")

    left_text = _semantic_text(left, fmt)
    right_text = _semantic_text(right, fmt)
    report: dict[str, Any] = {
        "format": fmt,
        "original": {"path": str(left), "sha256": sha256_file(left)},
        "modified": {"path": str(right), "sha256": sha256_file(right)},
        "identical": sha256_file(left) == sha256_file(right),
        "semantic": {
            "changed": left_text != right_text,
            "original_characters": len(left_text),
            "modified_characters": len(right_text),
            "unified_diff": list(
                difflib.unified_diff(
                    left_text.splitlines(),
                    right_text.splitlines(),
                    fromfile=left.name,
                    tofile=right.name,
                    lineterm="",
                )
            ),
        },
        "package": None,
        "visual": None,
    }
    if fmt in {"docx", "xlsx", "pptx"}:
        left_parts = _package_hashes(left)
        right_parts = _package_hashes(right)
        common = set(left_parts) & set(right_parts)
        changed = sorted(name for name in common if left_parts[name] != right_parts[name])
        report["package"] = {
            "added_parts": sorted(set(right_parts) - set(left_parts)),
            "removed_parts": sorted(set(left_parts) - set(right_parts)),
            "changed_parts": changed,
            "unchanged_parts": len(common) - len(changed),
        }

    if visual:
        destination = Path(visual_dir or right.parent / f"{right.stem}-visual-diff").resolve()
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="documentctl-compare-") as temporary:
            root = Path(temporary)
            left_render = render_document(left, root / "left", timeout=timeout)
            right_render = render_document(right, root / "right", timeout=timeout)
            left_pages = [Path(value) for value in left_render["pages"]]
            right_pages = [Path(value) for value in right_render["pages"]]
            pages: list[dict[str, Any]] = []
            for index in range(max(len(left_pages), len(right_pages))):
                if index >= len(left_pages) or index >= len(right_pages):
                    pages.append(
                        {
                            "page": index + 1,
                            "comparable": False,
                            "reason": "page exists in only one document",
                        }
                    )
                else:
                    pages.append(
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
                "pages": pages,
            }
    if output_report:
        write_json(output_report, report)
    return report
