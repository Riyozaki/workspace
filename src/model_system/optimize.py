from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import Any

from .blender_runtime import find_gltf_transform
from .errors import ModelingToolUnavailableError
from .security import inspect_glb_container
from .util import sha256_file
from .validate import validate_model


def optimize_model(
    input_path: str | Path,
    output_path: str | Path,
    *,
    compression: str = "none",
    texture_size: int = 2048,
    simplify_ratio: float | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    if compression not in {"none", "meshopt", "draco"}:
        raise ValueError("compression must be none, meshopt, or draco")
    if not 64 <= texture_size <= 8192:
        raise ValueError("texture_size must be between 64 and 8192")
    if simplify_ratio is not None and not 0.01 <= simplify_ratio <= 1:
        raise ValueError("simplify_ratio must be between 0.01 and 1")
    source = Path(input_path).resolve()
    destination = Path(output_path).resolve()
    if source == destination:
        raise ValueError("Optimization never overwrites the source model")
    inspect_glb_container(source)
    executable = find_gltf_transform()
    if executable is None:
        raise ModelingToolUnavailableError("glTF Transform is unavailable; run npm ci")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(executable),
        "optimize",
        str(source),
        str(destination),
        "--compress",
        "false" if compression == "none" else compression,
        "--texture-compress",
        "webp",
        "--texture-size",
        str(texture_size),
        "--simplify",
        "true" if simplify_ratio is not None else "false",
    ]
    if simplify_ratio is not None:
        command.extend(["--simplify-ratio", str(simplify_ratio)])
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "NO_COLOR": "1"},
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise ModelingToolUnavailableError(f"glTF optimization timed out after {timeout}s") from exc
    if process.returncode != 0 or not destination.is_file():
        raise ModelingToolUnavailableError(
            f"glTF optimization failed with exit {process.returncode}: {stderr[-8000:] or stdout[-4000:]}"
        )
    validation = validate_model(destination)
    if not validation["passed"]:
        destination.unlink(missing_ok=True)
        raise ModelingToolUnavailableError("Optimized model failed validation; output was removed")
    return {
        "input": str(source),
        "output": str(destination),
        "compression": compression,
        "simplify_ratio": simplify_ratio,
        "input_bytes": source.stat().st_size,
        "output_bytes": destination.stat().st_size,
        "reduction_fraction": round(1 - destination.stat().st_size / max(1, source.stat().st_size), 6),
        "input_sha256": sha256_file(source),
        "output_sha256": sha256_file(destination),
        "validation": validation["summary"],
        "stdout": stdout.strip()[-4000:],
        "stderr": stderr.strip()[-4000:] or None,
    }
