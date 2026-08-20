from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Any

from .errors import ToolUnavailableError


def find_wasm_office() -> Path | None:
    root = Path(__file__).resolve().parents[2]
    wrapper = root / "scripts/wasm-office.mjs"
    wasm = root / "node_modules/@matbee/libreoffice-converter/wasm/soffice.wasm"
    if shutil.which("node") and wrapper.is_file() and wasm.is_file():
        return wrapper
    return None


def wasm_office_version() -> str | None:
    return "@matbee/libreoffice-converter@2.7.2" if find_wasm_office() else None


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    """Stop the wrapper and all WASM pthread workers without leaking memory."""

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def convert_with_wasm_office(
    input_path: str | Path,
    output_path: str | Path,
    target_format: str,
    *,
    timeout: int = 240,
) -> dict[str, Any]:
    wrapper = find_wasm_office()
    node = shutil.which("node")
    if wrapper is None or node is None:
        raise ToolUnavailableError(
            "LibreOffice WASM runtime is unavailable. Run npm install from the repository root."
        )
    source = Path(input_path).resolve()
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [node, str(wrapper), str(source), str(destination), target_format]
    # Cold WASM compilation can take over a minute on a constrained 2-vCPU
    # sandbox. Keep a safe floor, but recover from a wedged worker promptly.
    timeout = max(timeout, 120)
    max_attempts = 2
    timed_out_attempts = 0

    for attempt in range(1, max_attempts + 1):
        # Never mistake stale or partially materialized output for a successful
        # retry. Source documents are always kept separate and untouched.
        destination.unlink(missing_ok=True)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            timed_out_attempts += 1
            _kill_process_group(process)
            process.communicate()
            if attempt < max_attempts:
                continue
            raise ToolUnavailableError(
                f"LibreOffice WASM conversion timed out after {max_attempts} attempts "
                f"({timeout}s each)"
            ) from exc

        # The converter's WASM worker may survive its wrapper as an orphan and
        # retain ~1 GB of memory. Wrapper and descendants share this group.
        _kill_process_group(process)
        if process.returncode != 0 or not destination.is_file():
            raise ToolUnavailableError(
                "LibreOffice WASM conversion failed. "
                f"exit={process.returncode}; stdout={stdout[-4000:]!r}; stderr={stderr[-8000:]!r}"
            )
        try:
            metadata = json.loads(stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            metadata = {}
        return {
            "output": str(destination),
            "backend": "libreoffice-wasm",
            "version": wasm_office_version(),
            "metadata": metadata,
            "attempts": attempt,
            "timed_out_attempts": timed_out_attempts,
            "stdout": stdout.strip()[-4000:],
            "stderr": stderr.strip()[-8000:],
            "returncode": process.returncode,
        }

    raise AssertionError("unreachable")
