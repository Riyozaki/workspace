from __future__ import annotations

import importlib.resources
import json
from pathlib import Path
from typing import Any

import jsonschema

from .citations import locate_text
from .util import read_json, sha256_file, write_json


def validate_lineage_plan(plan: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath(
        "schemas/lineage.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(plan)
    identifiers = [claim["id"] for claim in plan["claims"]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Lineage claim IDs must be unique")


def _check_location(
    location: dict[str, Any],
    value: Any,
    base: Path,
) -> dict[str, Any]:
    path = Path(location["path"])
    path = path if path.is_absolute() else (base / path).resolve()
    query = location.get("query", str(value))
    result = locate_text(
        path,
        query,
        case_sensitive=location.get("case_sensitive", False),
        max_hits=25,
    )
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "query": query,
        "passed": result["hit_count"] > 0,
        "citations": [hit["citation"] for hit in result["hits"]],
        "evidence": [hit["text"] for hit in result["hits"]],
    }


def verify_lineage(
    plan: dict[str, Any],
    *,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    validate_lineage_plan(plan)
    base = Path(base_dir or ".").resolve()
    claims = []
    for claim in plan["claims"]:
        sources = [
            _check_location(location, claim["value"], base)
            for location in claim["sources"]
        ]
        targets = [
            _check_location(location, claim["value"], base)
            for location in claim["targets"]
        ]
        claims.append(
            {
                "id": claim["id"],
                "value": claim["value"],
                "passed": all(item["passed"] for item in sources + targets),
                "sources": sources,
                "targets": targets,
            }
        )
    return {
        "passed": all(claim["passed"] for claim in claims),
        "claim_count": len(claims),
        "claims": claims,
    }


def verify_lineage_file(
    plan_path: str | Path,
    *,
    output_report: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(plan_path).resolve()
    report = verify_lineage(read_json(source), base_dir=source.parent)
    report["plan"] = str(source)
    if output_report:
        write_json(output_report, report)
    return report
