from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def find_project() -> Path | None:
    candidates = [
        Path.cwd() / "tools/openxml-validator/OpenXmlValidator.csproj",
        Path(__file__).resolve().parents[2] / "tools/openxml-validator/OpenXmlValidator.csproj",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def find_standalone_validator() -> Path | None:
    root = Path(__file__).resolve().parents[2]
    candidates = [
        root / "node_modules/.bin/ooxml-validator",
        root / "node_modules/@xarsh/ooxml-validator-linux-x64/ooxml-validator",
    ]
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_mode & 0o111:
            return candidate
    return None


def openxml_validator_available() -> bool:
    return find_standalone_validator() is not None or (
        shutil.which("dotnet") is not None and find_project() is not None
    )


def _validate_standalone(path: str | Path, timeout: int) -> dict[str, Any]:
    validator = find_standalone_validator()
    if validator is None:
        raise FileNotFoundError("standalone OOXML validator")
    try:
        result = subprocess.run(
            [str(validator), str(Path(path).resolve())],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "available": True,
            "provider": "@xarsh/ooxml-validator@0.3.0",
            "valid": False,
            "fatal": True,
            "reason": f"validator timed out after {timeout}s",
        }
    try:
        source = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "available": True,
            "provider": "@xarsh/ooxml-validator@0.3.0",
            "valid": False,
            "fatal": True,
            "reason": "standalone validator returned non-JSON output",
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "returncode": result.returncode,
        }
    return {
        "available": True,
        "provider": "@xarsh/ooxml-validator@0.3.0",
        "validator": "Microsoft Open XML SDK / Microsoft365",
        "valid": bool(source.get("ok")),
        "error_count": len(source.get("errors", [])),
        "errors": source.get("errors", []),
        "returncode": result.returncode,
        "stderr": result.stderr.strip()[-4000:] or None,
    }


def validate_with_openxml_sdk(path: str | Path, timeout: int = 180) -> dict[str, Any]:
    if find_standalone_validator() is not None:
        return _validate_standalone(path, timeout)
    dotnet = shutil.which("dotnet")
    project = find_project()
    if dotnet is None or project is None:
        return {
            "available": False,
            "valid": None,
            "reason": "dotnet not found" if dotnet is None else "validator project not found",
        }
    command = [
        dotnet,
        "run",
        "--project",
        str(project),
        "--configuration",
        "Release",
        "--",
        str(Path(path).resolve()),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"available": True, "valid": False, "fatal": True, "reason": f"validator timed out after {timeout}s"}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "available": True,
            "valid": False,
            "fatal": True,
            "reason": "validator returned non-JSON output",
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "returncode": result.returncode,
        }
    payload["available"] = True
    payload["provider"] = "local-dotnet-openxml-sdk"
    payload["returncode"] = result.returncode
    if result.stderr.strip():
        payload["stderr"] = result.stderr.strip()[-4000:]
    return payload
