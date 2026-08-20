from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .errors import ToolUnavailableError
from .libreoffice import convert_with_soffice, find_soffice
from .wasm_office import convert_with_wasm_office, find_wasm_office


def available_office_backends() -> dict[str, bool]:
    return {
        "native": find_soffice() is not None,
        "wasm": find_wasm_office() is not None,
    }


def preferred_office_backend() -> str | None:
    configured = os.environ.get("DOCUMENT_SYSTEM_OFFICE_BACKEND", "auto").lower()
    available = available_office_backends()
    if configured in {"native", "wasm"}:
        return configured if available[configured] else None
    if available["native"]:
        return "native"
    if available["wasm"]:
        return "wasm"
    return None


def convert_with_office(
    input_path: str | Path,
    output_dir: str | Path,
    target_format: str,
    *,
    timeout: int = 240,
    filter_name: str | None = None,
) -> dict[str, Any]:
    backend = preferred_office_backend()
    if backend == "native":
        result = convert_with_soffice(
            input_path,
            output_dir,
            target_format,
            timeout=timeout,
            filter_name=filter_name,
        )
        result["backend"] = "libreoffice-native"
        return result
    if backend == "wasm":
        source = Path(input_path).resolve()
        output = Path(output_dir).resolve() / f"{source.stem}.{target_format}"
        return convert_with_wasm_office(
            source,
            output,
            target_format,
            timeout=timeout,
        )
    raise ToolUnavailableError(
        "No Office renderer is available. Install native LibreOffice or run npm install "
        "to provision the pinned LibreOffice WASM backend."
    )
