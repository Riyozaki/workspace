#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Restricted Blender worker.

This process is intentionally file/JSON driven. It never executes source from a
model, prompt, or uploaded .blend file. Because it imports GPL Blender Python,
this worker is distributed under GPL-3.0-or-later; the main model_system package
communicates with it only through subprocess files and JSON.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector

UNIT_SCALE = {"m": 1.0, "cm": 0.01, "mm": 0.001}


def _hex(value: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    raw = value.lstrip("#")
    values = [int(raw[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    if len(raw) == 8:
        alpha *= int(raw[6:8], 16) / 255
    return values[0], values[1], values[2], alpha


def _reset() -> None:
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    bpy.app.driver_namespace.clear()


def _material(config: dict[str, Any]) -> Any:
    material = bpy.data.materials.new(config.get("name") or config["id"])
    rgba = _hex(config["base_color"], float(config.get("alpha", 1.0)))
    material.diffuse_color = rgba
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = float(config.get("metallic", 0.0))
    bsdf.inputs["Roughness"].default_value = float(config.get("roughness", 0.5))
    bsdf.inputs["Alpha"].default_value = rgba[3]
    if rgba[3] < 1:
        material.surface_render_method = "DITHERED"
    emission_strength = float(config.get("emission_strength", 0.0))
    if emission_strength and config.get("emission_color"):
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = _hex(config["emission_color"])
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    return material


def _apply_bevel(obj: Any, config: dict[str, Any], unit: float) -> None:
    bevel = config.get("bevel")
    if not bevel or float(bevel["width"]) <= 0:
        return
    modifier = obj.modifiers.new("ModelSpec bevel", "BEVEL")
    modifier.width = float(bevel["width"]) * unit
    modifier.segments = int(bevel.get("segments", 3))
    modifier.limit_method = "ANGLE"
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def _create_object(config: dict[str, Any], unit: float, materials: dict[str, Any]) -> Any:
    kind = config["type"]
    segments = int(config.get("segments", 48))
    if kind in {"box", "rounded_box"}:
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        obj.dimensions = tuple(float(value) * unit for value in config["size"])
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    elif kind == "plane":
        bpy.ops.mesh.primitive_plane_add(size=1)
        obj = bpy.context.object
        obj.scale = (float(config["size"][0]) * unit, float(config["size"][1]) * unit, 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    elif kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=segments,
            ring_count=max(8, segments // 2),
            radius=float(config["radius"]) * unit,
        )
        obj = bpy.context.object
    elif kind == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=segments,
            radius=float(config["radius"]) * unit,
            depth=float(config["depth"]) * unit,
        )
        obj = bpy.context.object
    elif kind == "cone":
        bpy.ops.mesh.primitive_cone_add(
            vertices=segments,
            radius1=float(config["radius"]) * unit,
            radius2=float(config.get("top_radius", 0.0)) * unit,
            depth=float(config["depth"]) * unit,
        )
        obj = bpy.context.object
    elif kind == "torus":
        bpy.ops.mesh.primitive_torus_add(
            major_segments=segments,
            minor_segments=max(8, segments // 3),
            major_radius=float(config["major_radius"]) * unit,
            minor_radius=float(config["minor_radius"]) * unit,
        )
        obj = bpy.context.object
    else:
        raise ValueError(f"Unsupported object type: {kind}")

    obj.name = config.get("name") or config["id"]
    obj["model_spec_id"] = config["id"]
    _apply_bevel(obj, config, unit)
    obj.location = tuple(float(value) * unit for value in config.get("location", (0, 0, 0)))
    obj.rotation_euler = tuple(math.radians(float(value)) for value in config.get("rotation_deg", (0, 0, 0)))
    obj.scale = tuple(float(value) for value in config.get("scale", (1, 1, 1)))
    material_id = config.get("material")
    if material_id:
        obj.data.materials.append(materials[material_id])
    if config.get("smooth"):
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    return obj


def build(spec_path: Path, output_path: Path) -> dict[str, Any]:
    _reset()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    unit = UNIT_SCALE[spec.get("units", "m")]
    materials = {item["id"]: _material(item) for item in spec.get("materials", [])}
    objects = [_create_object(config, unit, materials) for config in spec["objects"]]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_extras=True,
        export_cameras=False,
        export_lights=False,
        export_animations=False,
    )
    return {
        "operation": "build",
        "output": str(output_path),
        "bytes": output_path.stat().st_size,
        "objects": len(objects),
        "materials": len(materials),
        "blender": bpy.app.version_string,
        "engine": "bpy",
    }


def _look_at(obj: Any, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _scene_bounds(objects: list[Any]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    minimum = Vector(tuple(min(point[index] for point in points) for index in range(3)))
    maximum = Vector(tuple(max(point[index] for point in points) for index in range(3)))
    return minimum, maximum


def _studio_material(name: str, color: tuple[float, float, float, float], roughness: float) -> Any:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    return material


def _add_area(name: str, location: tuple[float, float, float], target: Vector, energy: float, size: float, color: tuple[float, float, float]) -> None:
    bpy.ops.object.light_add(type="AREA", location=location)
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    light.data.shape = "DISK"
    light.data.size = size
    light.data.color = color
    _look_at(light, target)


def render(model_path: Path, output_dir: Path, options_path: Path | None) -> dict[str, Any]:
    _reset()
    options = json.loads(options_path.read_text(encoding="utf-8")) if options_path else {}
    bpy.ops.import_scene.gltf(filepath=str(model_path))
    model_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not model_objects:
        raise ValueError("Imported GLB contains no mesh objects")
    minimum, maximum = _scene_bounds(model_objects)
    center = (minimum + maximum) * 0.5
    extent = maximum - minimum
    # Use the bounding-sphere radius rather than half the largest axis. This
    # keeps diagonal perspective views inside the frame instead of clipping.
    radius = max(extent.length * 0.5, 0.05)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = int(options.get("samples", 24))
    scene.cycles.use_denoising = True
    resolution = int(options.get("resolution", 512))
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = bool(options.get("transparent", False))
    scene.view_settings.look = "AgX - Medium High Contrast"

    scene.world = bpy.data.worlds.new("Model studio world")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = _hex(options.get("background", "#162333"))
    background.inputs["Strength"].default_value = 0.28

    floor_size = radius * 12
    bpy.ops.mesh.primitive_plane_add(size=floor_size, location=(center.x, center.y, minimum.z - radius * 0.015))
    floor = bpy.context.object
    floor.name = "QA studio floor"
    floor.data.materials.append(_studio_material("QA floor", (0.055, 0.065, 0.085, 1), 0.72))

    distance = radius * 3.4
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "QA camera"
    camera.data.lens = 58
    scene.camera = camera

    _add_area("Key", (center.x - distance, center.y - distance, center.z + distance * 1.25), center, 900 * max(radius, 0.4), radius * 3.0, (1.0, 0.78, 0.58))
    _add_area("Fill", (center.x + distance, center.y - distance * 0.4, center.z + distance * 0.6), center, 600 * max(radius, 0.4), radius * 2.5, (0.45, 0.65, 1.0))
    _add_area("Rim", (center.x, center.y + distance, center.z + distance), center, 1000 * max(radius, 0.4), radius * 2.0, (1.0, 0.42, 0.18))

    directions = {
        "perspective": Vector((1.25, -1.45, 0.95)),
        "front": Vector((0.0, -1.0, 0.25)),
        "right": Vector((1.0, 0.0, 0.25)),
        "back": Vector((0.0, 1.0, 0.25)),
        "left": Vector((-1.0, 0.0, 0.25)),
        "top": Vector((0.01, -0.01, 1.0)),
    }
    views = options.get("views") or ["perspective", "front", "right", "back"]
    output_dir.mkdir(parents=True, exist_ok=True)
    images: list[str] = []
    for view in views:
        direction = directions[view].normalized()
        camera.location = center + direction * distance
        _look_at(camera, center)
        destination = output_dir / f"{view}.png"
        scene.render.filepath = str(destination)
        bpy.ops.render.render(write_still=True)
        images.append(str(destination))
    return {
        "operation": "render",
        "input": str(model_path),
        "output_dir": str(output_dir),
        "images": images,
        "views": views,
        "resolution": resolution,
        "samples": scene.cycles.samples,
        "bounds": {"min": list(minimum), "max": list(maximum), "extent": list(extent)},
        "blender": bpy.app.version_string,
        "engine": "Cycles CPU",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("spec", type=Path)
    build_parser.add_argument("output", type=Path)
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("model", type=Path)
    render_parser.add_argument("output_dir", type=Path)
    render_parser.add_argument("--options", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        result = build(args.spec.resolve(), args.output.resolve())
    else:
        result = render(args.model.resolve(), args.output_dir.resolve(), args.options.resolve() if args.options else None)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
