from __future__ import annotations

import os
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .docx_extract import extract_docx
from .errors import DocumentSystemError
from .office_runtime import preferred_office_backend
from .opc import inspect_ooxml
from .pdf_extract import extract_pdf
from .pdf_qa import validate_pdf
from .pptx_extract import extract_pptx
from .pptx_qa import validate_pptx
from .qa import validate_docx
from .render import render_document
from .security import detect_format
from .util import sha256_file, write_json
from .xlsx_extract import extract_xlsx
from .xlsx_qa import validate_xlsx

SUPPORTED = {"docx", "xlsx", "pptx", "pdf"}


def collect_documents(inputs: Iterable[str | Path], *, recursive: bool = False) -> list[Path]:
    files: list[Path] = []
    for value in inputs:
        path = Path(value).resolve()
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            iterator = path.rglob("*") if recursive else path.glob("*")
            files.extend(candidate for candidate in iterator if candidate.is_file())
        else:
            raise FileNotFoundError(path)
    unique = sorted(set(files))
    return [path for path in unique if detect_format(path) in SUPPORTED]


def _inspect(path: Path) -> dict[str, Any]:
    fmt = detect_format(path)
    if fmt == "pdf":
        return extract_pdf(path)
    result = inspect_ooxml(path)
    result["semantic"] = {
        "docx": lambda: extract_docx(path),
        "xlsx": lambda: extract_xlsx(path, include_cells=False),
        "pptx": lambda: extract_pptx(path),
    }[fmt]()
    return result


def _validate(path: Path, *, render: bool, render_dir: Path) -> dict[str, Any]:
    fmt = detect_format(path)
    function = {
        "docx": validate_docx,
        "xlsx": validate_xlsx,
        "pptx": validate_pptx,
        "pdf": validate_pdf,
    }[fmt]
    return function(path, render=render, render_dir=render_dir if render else None)


def run_batch(
    inputs: Iterable[str | Path],
    output_dir: str | Path,
    *,
    action: str = "inspect",
    workers: int | None = None,
    recursive: bool = False,
    render: bool = False,
    timeout: int = 240,
) -> dict[str, Any]:
    if action not in {"inspect", "validate", "render"}:
        raise ValueError(f"Unsupported batch action: {action}")
    files = collect_documents(inputs, recursive=recursive)
    if not files:
        raise DocumentSystemError("No supported documents found")
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    worker_count = max(1, min(workers or min(4, os.cpu_count() or 1), 8, len(files)))
    # Each LibreOffice WASM process can approach 1 GB RSS. Parallel rendering on
    # the 4 GB Arena sandbox causes thrashing/timeouts, so serialize that path.
    if preferred_office_backend() == "wasm" and (
        action == "render" or (action == "validate" and render)
    ):
        worker_count = 1
    started = datetime.now(UTC)

    def execute(index: int, path: Path) -> dict[str, Any]:
        item_dir = destination / f"{index + 1:04d}-{path.stem}"
        item_dir.mkdir(parents=True, exist_ok=True)
        fmt = detect_format(path)
        if action == "inspect":
            result = _inspect(path)
        elif action == "validate":
            result = _validate(path, render=render, render_dir=item_dir / "render")
        else:
            result = render_document(path, item_dir / "render", timeout=timeout)
        report_path = item_dir / f"{action}.json"
        write_json(report_path, result)
        passed = result.get("passed", True) if isinstance(result, dict) else True
        return {
            "input": str(path),
            "format": fmt,
            "sha256": sha256_file(path),
            "status": "passed" if passed else "failed",
            "report": str(report_path),
        }

    results: list[dict[str, Any] | None] = [None] * len(files)
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="documentctl") as executor:
        futures = {executor.submit(execute, index, path): index for index, path in enumerate(files)}
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                results[index] = {
                    "input": str(files[index]),
                    "format": detect_format(files[index]),
                    "status": "failed",
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
    completed = [item for item in results if item is not None]
    failed = sum(item["status"] == "failed" for item in completed)
    manifest = {
        "action": action,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "workers": worker_count,
        "files": len(completed),
        "passed": len(completed) - failed,
        "failed": failed,
        "status": "passed" if failed == 0 else "failed",
        "items": completed,
    }
    write_json(destination / "manifest.json", manifest)
    return manifest
