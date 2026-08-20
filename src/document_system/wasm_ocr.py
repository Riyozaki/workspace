from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .errors import ToolUnavailableError


def find_wasm_ocr() -> Path | None:
    root = Path(__file__).resolve().parents[2]
    wrapper = root / "scripts/wasm-ocr.mjs"
    trained = root / "node_modules/@tesseract.js-data/eng/4.0.0/eng.traineddata.gz"
    if shutil.which("node") and wrapper.is_file() and trained.is_file():
        return wrapper
    return None


def wasm_ocr_version() -> str | None:
    return "tesseract.js@7.0.0" if find_wasm_ocr() else None


def recognize_images_with_wasm(
    images: Iterable[str | Path],
    *,
    language: str,
    timeout: int = 300,
) -> dict[str, Any]:
    wrapper = find_wasm_ocr()
    node = shutil.which("node")
    if wrapper is None or node is None:
        raise ToolUnavailableError(
            "Tesseract WASM runtime unavailable. Run npm install; bundled languages are eng and rus."
        )
    paths = [str(Path(value).resolve()) for value in images]
    result = subprocess.run(
        [node, str(wrapper), language, *paths],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise ToolUnavailableError(
            f"Tesseract WASM failed: exit={result.returncode}; stderr={result.stderr[-8000:]!r}"
        )
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise ToolUnavailableError(
            f"Tesseract WASM returned invalid JSON: {result.stdout[-4000:]!r}"
        ) from exc
