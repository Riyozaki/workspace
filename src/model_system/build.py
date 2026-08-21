from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from .blender_runtime import find_blender_python, run_blender_worker
from .spec import unit_scale, validate_model_spec
from .util import read_json, sha256_file


def _rgba(value: str, alpha: float = 1.0) -> list[int]:
    raw = value.lstrip("#")
    result = [int(raw[index : index + 2], 16) for index in (0, 2, 4)]
    embedded_alpha = int(raw[6:8], 16) / 255 if len(raw) == 8 else 1.0
    return [*result, round(255 * alpha * embedded_alpha)]


def _material(config: dict[str, Any]) -> trimesh.visual.material.PBRMaterial:
    emission = config.get("emission_color")
    emissive = [value / 255 for value in _rgba(emission)[:3]] if emission else None
    return trimesh.visual.material.PBRMaterial(
        name=config.get("name") or config["id"],
        baseColorFactor=_rgba(config["base_color"], float(config.get("alpha", 1.0))),
        metallicFactor=float(config.get("metallic", 0.0)),
        roughnessFactor=float(config.get("roughness", 0.5)),
        emissiveFactor=emissive,
    )


def _primitive(config: dict[str, Any], unit: float) -> trimesh.Trimesh:
    kind = config["type"]
    segments = int(config.get("segments", 48))
    if kind in {"box", "rounded_box", "plane"}:
        extents = np.asarray(config["size"], dtype=float) * unit
        return trimesh.creation.box(extents=extents)
    if kind == "sphere":
        return trimesh.creation.uv_sphere(
            radius=float(config["radius"]) * unit,
            count=[segments, max(8, segments // 2)],
        )
    if kind == "cylinder":
        return trimesh.creation.cylinder(
            radius=float(config["radius"]) * unit,
            height=float(config["depth"]) * unit,
            sections=segments,
        )
    if kind == "cone":
        top = float(config.get("top_radius", 0.0)) * unit
        if top:
            return trimesh.creation.conical_frustum(
                radius_top=top,
                radius_base=float(config["radius"]) * unit,
                height=float(config["depth"]) * unit,
                sections=segments,
            )
        return trimesh.creation.cone(
            radius=float(config["radius"]) * unit,
            height=float(config["depth"]) * unit,
            sections=segments,
        )
    if kind == "torus":
        return trimesh.creation.torus(
            major_radius=float(config["major_radius"]) * unit,
            minor_radius=float(config["minor_radius"]) * unit,
            major_sections=segments,
            minor_sections=max(8, segments // 3),
        )
    raise ValueError(f"Unsupported object type: {kind}")


def _transform(config: dict[str, Any], unit: float) -> np.ndarray:
    location = np.asarray(config.get("location", (0, 0, 0)), dtype=float) * unit
    rotation = np.radians(np.asarray(config.get("rotation_deg", (0, 0, 0)), dtype=float))
    scale = np.asarray(config.get("scale", (1, 1, 1)), dtype=float)
    return trimesh.transformations.concatenate_matrices(
        trimesh.transformations.translation_matrix(location),
        trimesh.transformations.euler_matrix(*rotation, axes="sxyz"),
        trimesh.transformations.scale_and_translate(scale=scale),
    )


def _build_with_trimesh(spec: dict[str, Any], output_path: Path) -> dict[str, Any]:
    unit = unit_scale(spec)
    materials = {item["id"]: _material(item) for item in spec.get("materials", [])}
    scene = trimesh.Scene(base_frame="world")
    warnings: list[str] = []
    for config in spec["objects"]:
        mesh = _primitive(config, unit)
        material_id = config.get("material")
        if material_id:
            mesh.visual = trimesh.visual.TextureVisuals(material=materials[material_id])
        if config["type"] == "rounded_box" or config.get("bevel"):
            warnings.append(f"{config['id']}: portable fallback does not apply bevel; provision Blender for final output")
        scene.add_geometry(
            mesh,
            node_name=config.get("name") or config["id"],
            geom_name=config["id"],
            transform=_transform(config, unit),
            metadata={"model_spec_id": config["id"]},
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()
    if suffix == ".glb":
        output_path.write_bytes(scene.export(file_type="glb"))
    elif suffix == ".obj":
        exported = scene.export(file_type="obj")
        output_path.write_text(exported if isinstance(exported, str) else exported.decode(), encoding="utf-8")
    elif suffix == ".stl":
        geometry = scene.to_geometry()
        output_path.write_bytes(geometry.export(file_type="stl"))
    else:
        raise ValueError("Supported outputs are .glb, .obj, and .stl")
    return {
        "backend": "trimesh",
        "trimesh": trimesh.__version__,
        "objects": len(spec["objects"]),
        "materials": len(materials),
        "warnings": warnings,
    }


def build_model(
    spec: dict[str, Any],
    output_path: str | Path,
    *,
    backend: str = "auto",
    timeout: int = 600,
) -> dict[str, Any]:
    validate_model_spec(spec)
    destination = Path(output_path).resolve()
    if backend not in {"auto", "blender", "trimesh"}:
        raise ValueError("backend must be auto, blender, or trimesh")
    selected = "blender" if backend == "auto" and find_blender_python() else backend
    if selected == "auto":
        selected = "trimesh"
    if selected == "blender":
        if destination.suffix.lower() != ".glb":
            raise ValueError("Blender declarative builder currently emits .glb only")
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Pass a canonical snapshot of the already validated in-memory object.
        # Never let the isolated worker reread a mutable/untrusted source path.
        with tempfile.TemporaryDirectory(prefix="modelctl-spec-", dir=destination.parent) as temporary:
            safe_spec = Path(temporary) / "spec.json"
            safe_spec.write_text(
                json.dumps(spec, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = run_blender_worker(["build", str(safe_spec), str(destination)], timeout=timeout)
        result["backend"] = "blender-python"
        result["warnings"] = []
    else:
        result = _build_with_trimesh(spec, destination)
    result.update(
        {
            "output": str(destination),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
        }
    )
    return result


def build_model_from_file(
    spec_path: str | Path,
    output_path: str | Path,
    *,
    backend: str = "auto",
    timeout: int = 600,
) -> dict[str, Any]:
    source = Path(spec_path).resolve()
    return build_model(read_json(source), output_path, backend=backend, timeout=timeout)
