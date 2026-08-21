from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Any

from .errors import ModelingToolUnavailableError


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def find_blender_python() -> Path | None:
    configured = os.environ.get("MODEL_SYSTEM_BLENDER_PYTHON")
    candidates = [Path(configured).expanduser() if configured else None, repository_root() / ".cache/model-runtime/blender/bin/python"]
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            # Preserve the venv entry-point path. Resolving its symlink to
            # /usr/bin/python would discard the venv's bpy site-packages.
            return candidate.absolute()
    return None


def find_headless_libraries() -> Path | None:
    configured = os.environ.get("MODEL_SYSTEM_HEADLESS_LIBS")
    candidates = [Path(configured).expanduser() if configured else None, repository_root() / ".cache/model-runtime/headless-libs"]
    for candidate in candidates:
        if candidate and (candidate / "libGL.so.1").is_file():
            return candidate.resolve()
    return None


def blender_runtime_info() -> dict[str, Any]:
    runtime_file = repository_root() / ".cache/model-runtime/blender-runtime.json"
    if runtime_file.is_file():
        try:
            return json.loads(runtime_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    python = find_blender_python()
    return {"available": python is not None, "python": str(python) if python else None, "version": None}


def run_blender_worker(arguments: list[str], *, timeout: int = 600) -> dict[str, Any]:
    python = find_blender_python()
    worker = repository_root() / "tools/blender/model_worker.py"
    if python is None or not worker.is_file():
        raise ModelingToolUnavailableError("Blender Python runtime is unavailable; run scripts/bootstrap-modeling.sh")
    env = os.environ.copy()
    libraries = find_headless_libraries()
    if libraries:
        current = env.get("LD_LIBRARY_PATH")
        env["LD_LIBRARY_PATH"] = str(libraries) + (f":{current}" if current else "")
    process = subprocess.Popen(
        [str(python), str(worker), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
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
        raise ModelingToolUnavailableError(f"Blender worker timed out after {timeout}s") from exc
    if process.returncode != 0:
        raise ModelingToolUnavailableError(
            f"Blender worker failed with exit {process.returncode}: {stderr[-8000:] or stdout[-4000:]}"
        )
    try:
        result = json.loads(stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise ModelingToolUnavailableError(f"Blender worker returned no JSON result: {stderr[-4000:]}") from exc
    result["stdout_tail"] = stdout.strip()[-4000:]
    result["stderr_tail"] = stderr.strip()[-4000:] or None
    return result


def find_cad_python() -> Path | None:
    configured = os.environ.get("MODEL_SYSTEM_CAD_PYTHON")
    candidates = [Path(configured).expanduser() if configured else None, repository_root() / ".cache/model-runtime/cad/bin/python"]
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.absolute()
    return None


def find_gltf_transform() -> Path | None:
    executable = repository_root() / "node_modules/.bin/gltf-transform"
    return executable if executable.is_file() else (Path(value) if (value := shutil.which("gltf-transform")) else None)
