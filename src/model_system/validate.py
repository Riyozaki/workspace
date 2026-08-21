from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .gltf_validator import validate_gltf
from .inspect import inspect_model
from .util import write_json


def _issue(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def validate_model(
    path: str | Path,
    *,
    output_report: str | Path | None = None,
    profile: str = "render",
    max_triangles: int = 1_000_000,
    require_materials: bool = True,
    require_gltf_validator: bool = True,
    strict: bool = False,
) -> dict[str, Any]:
    if profile not in {"web", "render", "print"}:
        raise ValueError("profile must be web, render, or print")
    issues: list[dict[str, str]] = []
    try:
        inspection = inspect_model(path)
    except Exception as exc:
        inspection = None
        issues.append(_issue("error", "model-parse-failed", str(exc)))

    official = validate_gltf(path) if Path(path).suffix.lower() == ".glb" else {"available": False, "valid": None}
    if official.get("available"):
        if official.get("valid") is False:
            issues.append(_issue("error", "gltf-invalid", f"Khronos validator reported {official.get('errors')} error(s)"))
        if official.get("warnings"):
            issues.append(_issue("warning", "gltf-warning", f"Khronos validator reported {official['warnings']} warning(s)"))
    elif require_gltf_validator:
        issues.append(_issue("error", "gltf-validator-unavailable", str(official.get("reason", "validator unavailable"))))

    if inspection:
        scene = inspection["scene"]
        if not scene["geometry_instances"]:
            issues.append(_issue("error", "empty-scene", "Model contains no mesh geometry"))
        if scene["triangles"] > max_triangles:
            issues.append(
                _issue(
                    "error",
                    "triangle-budget-exceeded",
                    f"Model has {scene['triangles']} triangles; budget is {max_triangles}",
                )
            )
        if require_materials and scene["material_count"] == 0:
            issues.append(_issue("error", "materials-required", "Model has no named material"))
        extents = scene.get("extents_m")
        if extents and any(value <= 0 for value in extents):
            issues.append(_issue("error", "degenerate-bounds", f"Model has non-positive extent: {extents}"))
        for geometry in inspection["geometries"]:
            name = geometry["name"]
            if not geometry["finite_vertices"]:
                issues.append(_issue("error", "non-finite-vertex", f"{name}: contains NaN or infinite coordinates"))
            if geometry["degenerate_triangles"]:
                issues.append(
                    _issue(
                        "error",
                        "degenerate-triangles",
                        f"{name}: {geometry['degenerate_triangles']} zero-area triangle(s)",
                    )
                )
            if geometry["nonmanifold_edges"]:
                issues.append(
                    _issue(
                        "error",
                        "nonmanifold-edges",
                        f"{name}: {geometry['nonmanifold_edges']} edge(s) belong to more than two faces",
                    )
                )
            if not geometry["winding_consistent"]:
                issues.append(_issue("error", "inconsistent-winding", f"{name}: face winding is inconsistent"))
            if profile == "print":
                if not geometry["watertight"] or geometry["boundary_edges"]:
                    issues.append(
                        _issue(
                            "error",
                            "not-watertight",
                            f"{name}: print profile requires a closed watertight shell",
                        )
                    )
                if not geometry["is_volume"]:
                    issues.append(_issue("error", "not-positive-volume", f"{name}: is not a positive solid volume"))
            elif not geometry["watertight"]:
                issues.append(_issue("warning", "open-surface", f"{name}: mesh is not watertight"))

    counts = Counter(item["severity"] for item in issues)
    passed = counts["error"] == 0 and (not strict or counts["warning"] == 0)
    report = {
        "path": str(Path(path).resolve()),
        "format": Path(path).suffix.lower().lstrip("."),
        "profile": profile,
        "strict": strict,
        "passed": passed,
        "summary": {"errors": counts["error"], "warnings": counts["warning"], "info": counts["info"]},
        "issues": issues,
        "inspection": inspection,
        "gltf_validator": official,
    }
    if output_report:
        write_json(output_report, report)
    return report
