from __future__ import annotations

import importlib.metadata
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .blender_runtime import (
    blender_runtime_info,
    find_cad_python,
    find_gltf_transform,
    find_headless_libraries,
    repository_root,
)
from .build import build_model
from .gltf_validator import find_gltf_validator
from .validate import validate_model


def _version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _npm_version(name: str) -> str | None:
    package = repository_root() / "node_modules" / name / "package.json"
    try:
        return json.loads(package.read_text(encoding="utf-8"))["version"]
    except (OSError, KeyError, json.JSONDecodeError):
        return None


def _self_test() -> dict[str, Any]:
    spec = {
        "version": "1.0",
        "materials": [{"id": "test", "base_color": "#3F7CAC", "metallic": 0.1, "roughness": 0.4}],
        "objects": [
            {"id": "body", "type": "rounded_box", "size": [1.0, 0.7, 0.4], "material": "test", "bevel": {"width": 0.06, "segments": 3}},
            {"id": "cap", "type": "sphere", "radius": 0.24, "location": [0, 0, 0.3], "material": "test", "segments": 24, "smooth": True},
        ],
    }
    with tempfile.TemporaryDirectory(prefix="modelctl-self-test-") as temporary:
        root = Path(temporary)
        # The portable builder always proves core geometry; Blender has separate integration tests.
        result = build_model(spec, root / "test.glb", backend="trimesh")
        validation = validate_model(root / "test.glb", max_triangles=100_000)
        return {
            "build": Path(result["output"]).is_file(),
            "validation": validation["passed"],
            "triangles": validation["inspection"]["scene"]["triangles"] if validation["inspection"] else None,
            "passed": Path(result["output"]).is_file() and validation["passed"],
        }


def doctor(*, self_test: bool = False) -> dict[str, Any]:
    blender = blender_runtime_info()
    validator = find_gltf_validator()
    transform = find_gltf_transform()
    cad = find_cad_python()
    report = {
        "modelctl": "0.7.0",
        "python_packages": {
            "trimesh": _version("trimesh"),
            "manifold3d": _version("manifold3d"),
        },
        "runtimes": {
            "blender": blender,
            "headless_compatibility_shims": str(find_headless_libraries()) if find_headless_libraries() else None,
            "cadquery_python": str(cad) if cad else None,
            "gltf_validator": str(validator) if validator else None,
            "gltf_transform": str(transform) if transform else None,
            "model_viewer": _npm_version("@google/model-viewer"),
            "nvidia_smi": shutil.which("nvidia-smi"),
        },
        "capabilities": {
            "procedural_mesh_creation": _version("trimesh") is not None,
            "blender_procedural_creation": blender.get("available", False),
            "cycles_cpu_rendering": blender.get("available", False),
            "gltf_validation": validator is not None,
            "gltf_optimization": transform is not None,
            "interactive_web_viewer": _npm_version("@google/model-viewer") is not None,
            "parametric_brep_cad": cad is not None,
            "local_generative_3d": False,
            "gpu_available": shutil.which("nvidia-smi") is not None,
        },
        "self_test": _self_test() if self_test else None,
    }
    report["core_ready"] = all(
        report["capabilities"][name]
        for name in ("procedural_mesh_creation", "gltf_validation", "gltf_optimization", "interactive_web_viewer")
    )
    return report
