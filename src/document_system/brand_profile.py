from __future__ import annotations

import copy
import importlib.resources
import json
from pathlib import Path
from typing import Any

import jsonschema

from .docx_build import validate_spec as validate_docx_spec
from .pdf_build import validate_pdf_spec
from .pptx_build import validate_pptx_spec
from .util import read_json, write_json
from .xlsx_build import validate_xlsx_spec


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def validate_brand_profile(profile: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath(
        "schemas/brand-profile.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(profile)


def apply_brand_profile(
    profile: dict[str, Any],
    spec: dict[str, Any],
    *,
    format_name: str,
) -> dict[str, Any]:
    validate_brand_profile(profile)
    if format_name not in {"docx", "xlsx", "pptx", "pdf"}:
        raise ValueError(f"Unsupported profile format: {format_name}")
    defaults = profile.get("formats", {}).get(format_name, {})
    result = _merge(defaults, spec)
    if profile.get("theme"):
        allowed_theme_keys = {
            "docx": {"primary", "secondary", "accent", "text", "muted", "light", "font", "heading_font"},
            "xlsx": {"primary", "secondary", "accent", "positive", "negative", "text", "muted", "light", "font"},
            "pptx": {"primary", "secondary", "accent", "background", "light", "text", "muted", "positive", "negative", "font", "heading_font"},
            "pdf": {"primary", "secondary", "accent", "text", "muted", "light", "positive", "negative"},
        }[format_name]
        common_theme = {
            key: value
            for key, value in profile["theme"].items()
            if key in allowed_theme_keys
        }
        result["theme"] = _merge(common_theme, result.get("theme", {}))
    result.setdefault("metadata", {})
    result["metadata"].setdefault(
        "comments" if format_name in {"docx", "pptx"} else "description",
        f"Brand profile: {profile['name']}",
    )
    validators = {
        "docx": validate_docx_spec,
        "xlsx": validate_xlsx_spec,
        "pptx": validate_pptx_spec,
        "pdf": validate_pdf_spec,
    }
    validators[format_name](result)
    return result


def apply_brand_profile_files(
    profile_path: str | Path,
    spec_path: str | Path,
    output_spec: str | Path,
    *,
    format_name: str,
) -> dict[str, Any]:
    result = apply_brand_profile(
        read_json(profile_path),
        read_json(spec_path),
        format_name=format_name,
    )
    write_json(output_spec, result)
    return {
        "profile": str(Path(profile_path)),
        "input_spec": str(Path(spec_path)),
        "output_spec": str(Path(output_spec)),
        "format": format_name,
    }
