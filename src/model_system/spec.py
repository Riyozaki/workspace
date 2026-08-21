from __future__ import annotations

import importlib.resources
import json
import math
from typing import Any

import jsonschema

UNIT_SCALE = {"m": 1.0, "cm": 0.01, "mm": 0.001}


def validate_model_spec(spec: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("model_system").joinpath("schemas/model-spec.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(spec)

    material_ids = [item["id"] for item in spec.get("materials", [])]
    object_ids = [item["id"] for item in spec["objects"]]
    if len(material_ids) != len(set(material_ids)):
        raise ValueError("Material IDs must be unique")
    if len(object_ids) != len(set(object_ids)):
        raise ValueError("Object IDs must be unique")
    known_materials = set(material_ids)
    for obj in spec["objects"]:
        material_id = obj.get("material")
        if material_id and material_id not in known_materials:
            raise ValueError(f"Object {obj['id']!r} references unknown material {material_id!r}")
        values = [
            *(obj.get("location") or (0, 0, 0)),
            *(obj.get("rotation_deg") or (0, 0, 0)),
            *(obj.get("scale") or (1, 1, 1)),
        ]
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError(f"Object {obj['id']!r} contains a non-finite transform")
        if obj["type"] == "torus" and obj["minor_radius"] >= obj["major_radius"]:
            raise ValueError(f"Object {obj['id']!r}: torus minor_radius must be less than major_radius")
        bevel = obj.get("bevel")
        if bevel and obj.get("size") and bevel["width"] * 2 >= min(obj["size"]):
            raise ValueError(f"Object {obj['id']!r}: bevel width is too large for its size")


def unit_scale(spec: dict[str, Any]) -> float:
    return UNIT_SCALE[spec.get("units", "m")]
