from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def find_gltf_validator() -> Path | None:
    root = Path(__file__).resolve().parents[2]
    wrapper = root / "scripts/gltf-validate.mjs"
    package = root / "node_modules/gltf-validator/package.json"
    return wrapper if shutil.which("node") and wrapper.is_file() and package.is_file() else None


def validate_gltf(path: str | Path, *, timeout: int = 120) -> dict[str, Any]:
    wrapper = find_gltf_validator()
    node = shutil.which("node")
    if wrapper is None or node is None:
        return {"available": False, "valid": None, "reason": "Run npm ci to install gltf-validator"}
    completed = subprocess.run(
        [node, str(wrapper), str(Path(path).resolve())],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    try:
        report = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {
            "available": True,
            "valid": False,
            "returncode": completed.returncode,
            "reason": completed.stderr.strip()[-4000:] or "Validator returned no JSON report",
        }
    issues = report.get("issues", {})
    return {
        "available": True,
        "provider": "KhronosGroup/glTF-Validator 2.0.0-dev.3.10",
        "valid": int(issues.get("numErrors", 0)) == 0,
        "errors": int(issues.get("numErrors", 0)),
        "warnings": int(issues.get("numWarnings", 0)),
        "infos": int(issues.get("numInfos", 0)),
        "hints": int(issues.get("numHints", 0)),
        "messages": issues.get("messages", []),
        "info": report.get("info", {}),
        "returncode": completed.returncode,
        "stderr": completed.stderr.strip()[-4000:] or None,
    }
