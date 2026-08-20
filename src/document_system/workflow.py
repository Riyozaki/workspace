from __future__ import annotations

import importlib.resources
import json
import re
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

from .compare import compare_documents
from .conversion import convert_document
from .doctor import doctor
from .docx_build import build_docx_from_file
from .docx_edit import apply_edit_plan_file
from .docx_extract import extract_docx
from .docx_revisions import apply_revision_view
from .errors import DocumentSystemError
from .lineage import verify_lineage_file
from .opc import inspect_ooxml
from .pdf_build import build_pdf_from_file
from .pdf_extract import extract_pdf
from .pdf_forms import overlay_pdf_file
from .pdf_qa import validate_pdf
from .pdf_redact import redact_pdf_file
from .pdf_transform import transform_pdf_file
from .pptx_build import build_pptx_from_file
from .pptx_edit import apply_pptx_edit_plan_file
from .pptx_extract import extract_pptx
from .pptx_qa import validate_pptx
from .pptx_structure import apply_pptx_structure_plan_file
from .qa import validate_docx
from .render import render_document
from .security import detect_format
from .util import read_json, sha256_file, write_json
from .xlsx_build import build_xlsx_from_file
from .xlsx_edit import apply_xlsx_edit_plan_file
from .xlsx_extract import extract_xlsx
from .xlsx_qa import validate_xlsx
from .xlsx_recalc import recalculate_xlsx

REFERENCE = re.compile(r"\$\{([A-Za-z0-9_.-]+)\.output\}")


def validate_workflow(value: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath("schemas/workflow.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(value)
    ids = [step["id"] for step in value["steps"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Workflow step IDs must be unique")


def _resolve_string(value: str, context: dict[str, dict[str, Any]], base: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        step = match.group(1)
        if step not in context or not context[step].get("output"):
            raise ValueError(f"Unresolved workflow reference: {match.group(0)}")
        return context[step]["output"]

    resolved = REFERENCE.sub(replace, value)
    path = Path(resolved)
    return str(path if path.is_absolute() else (base / path).resolve())


def _resolve_option_references(value: Any, context: dict[str, dict[str, Any]]) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            step = match.group(1)
            if step not in context or not context[step].get("output"):
                raise ValueError(f"Unresolved workflow reference: {match.group(0)}")
            return context[step]["output"]

        return REFERENCE.sub(replace, value)
    if isinstance(value, list):
        return [_resolve_option_references(item, context) for item in value]
    if isinstance(value, dict):
        return {
            key: _resolve_option_references(item, context)
            for key, item in value.items()
        }
    return value


def _resolve_step(step: dict[str, Any], context: dict[str, dict[str, Any]], base: Path) -> dict[str, Any]:
    result = dict(step)
    for key in ("input", "original", "modified", "output", "spec", "plan"):
        if result.get(key):
            result[key] = _resolve_string(result[key], context, base)
    if result.get("options"):
        result["options"] = _resolve_option_references(result["options"], context)
    return result


def _inspect(path: str) -> dict[str, Any]:
    fmt = detect_format(path)
    if fmt in {"docx", "xlsx", "pptx"}:
        result = inspect_ooxml(path)
        result["semantic"] = {
            "docx": lambda: extract_docx(path),
            "xlsx": lambda: extract_xlsx(path, include_cells=False),
            "pptx": lambda: extract_pptx(path),
        }[fmt]()
        return result
    if fmt == "pdf":
        return extract_pdf(path)
    raise DocumentSystemError(f"Cannot inspect unsupported format: {fmt}")


def _validate(path: str, options: dict[str, Any]) -> dict[str, Any]:
    fmt = detect_format(path)
    functions = {
        "docx": validate_docx,
        "xlsx": validate_xlsx,
        "pptx": validate_pptx,
        "pdf": validate_pdf,
    }
    if fmt not in functions:
        raise DocumentSystemError(f"Cannot validate unsupported format: {fmt}")
    return functions[fmt](path, **options)


def _execute(step: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    action = step["action"]
    options = step.get("options", {})
    output = step.get("output")
    if action == "create":
        fmt = step.get("format")
        if not output or not step.get("spec") or fmt not in {"docx", "xlsx", "pptx", "pdf"}:
            raise ValueError("create requires format, spec, and output")
        builders = {
            "docx": build_docx_from_file,
            "xlsx": build_xlsx_from_file,
            "pptx": build_pptx_from_file,
            "pdf": build_pdf_from_file,
        }
        builders[fmt](step["spec"], output)
        return {"output": output, "format": fmt}, output
    if action == "edit":
        fmt = step.get("format")
        if not output or not step.get("input") or not step.get("plan") or fmt not in {"docx", "xlsx", "pptx"}:
            raise ValueError("edit requires format, input, plan, and output")
        editors = {
            "docx": apply_edit_plan_file,
            "xlsx": apply_xlsx_edit_plan_file,
            "pptx": apply_pptx_edit_plan_file,
        }
        result = editors[fmt](step["input"], output, step["plan"])
        return result, output
    if action == "inspect":
        if not step.get("input"):
            raise ValueError("inspect requires input")
        return _inspect(step["input"]), None
    if action == "validate":
        if not step.get("input"):
            raise ValueError("validate requires input")
        return _validate(step["input"], options), None
    if action == "render":
        if not step.get("input") or not output:
            raise ValueError("render requires input and output directory")
        return render_document(step["input"], output, **options), output
    if action == "compare":
        if not step.get("original") or not step.get("modified"):
            raise ValueError("compare requires original and modified")
        return compare_documents(step["original"], step["modified"], **options), None
    if action == "convert":
        if not step.get("input") or not output or not step.get("target"):
            raise ValueError("convert requires input, output, and target")
        return convert_document(step["input"], output, target=step["target"], **options), output
    if action == "docx-revisions":
        if not step.get("input") or not output or options.get("mode") not in {"accept", "reject"}:
            raise ValueError("docx-revisions requires input, output, and options.mode")
        return apply_revision_view(step["input"], output, mode=options["mode"]), output
    if action == "xlsx-recalc":
        if not step.get("input") or not output:
            raise ValueError("xlsx-recalc requires input and output")
        return recalculate_xlsx(step["input"], output, **options), output
    if action == "pptx-structure":
        if not step.get("input") or not step.get("plan") or not output:
            raise ValueError("pptx-structure requires input, plan, and output")
        return apply_pptx_structure_plan_file(step["input"], output, step["plan"]), output
    if action == "pdf-transform":
        if not step.get("plan") or not output:
            raise ValueError("pdf-transform requires plan and output")
        return transform_pdf_file(step["plan"], output), output
    if action == "pdf-overlay":
        if not step.get("input") or not step.get("plan") or not output:
            raise ValueError("pdf-overlay requires input, plan, and output")
        return overlay_pdf_file(step["input"], output, step["plan"]), output
    if action == "pdf-redact":
        if not step.get("input") or not step.get("plan") or not output:
            raise ValueError("pdf-redact requires input, plan, and output")
        return redact_pdf_file(step["input"], output, step["plan"]), output
    if action == "lineage":
        if not step.get("plan"):
            raise ValueError("lineage requires plan")
        return verify_lineage_file(step["plan"]), None
    if action == "approval":
        if not step.get("plan"):
            raise ValueError("approval requires a signed approval JSON in plan")
        approval = read_json(step["plan"])
        if approval.get("approved") is not True or not approval.get("approved_by"):
            raise DocumentSystemError("Approval is missing approved=true or approved_by")
        verified = []
        for artifact in approval.get("artifacts", []):
            path = Path(artifact["path"]).resolve()
            actual = sha256_file(path)
            if actual.lower() != artifact["sha256"].lower():
                raise DocumentSystemError(
                    f"Approval hash mismatch for {path}: expected {artifact['sha256']}, found {actual}"
                )
            verified.append({"path": str(path), "sha256": actual})
        return {
            "approved": True,
            "approved_by": approval["approved_by"],
            "approved_at": approval.get("approved_at"),
            "artifacts": verified,
            "note": approval.get("note"),
        }, None
    raise ValueError(f"Unsupported workflow action: {action}")


def run_workflow(
    workflow_path: str | Path,
    *,
    work_dir: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(workflow_path).resolve()
    workflow = read_json(source)
    validate_workflow(workflow)
    job_id = workflow.get("job_id") or f"job-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    work = Path(work_dir).resolve() if work_dir else (Path.cwd() / ".document-work/jobs" / job_id).resolve()
    work.mkdir(parents=True, exist_ok=True)
    manifest_path = work / "manifest.json"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "job_id": job_id,
        "workflow": str(source),
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "status": "running",
        "environment": doctor(self_test=False),
        "steps": [],
    }
    write_json(manifest_path, manifest)
    context: dict[str, dict[str, Any]] = {}
    failed = False
    for raw_step in workflow["steps"]:
        step = _resolve_step(raw_step, context, source.parent)
        started = datetime.now(UTC)
        record: dict[str, Any] = {
            "id": step["id"],
            "action": step["action"],
            "started_at": started.isoformat(),
            "status": "running",
            "resolved": step,
        }
        manifest["steps"].append(record)
        try:
            result, output = _execute(step)
            report_path = work / f"{step['id']}.json"
            write_json(report_path, result)
            record.update(
                {
                    "status": "passed",
                    "completed_at": datetime.now(UTC).isoformat(),
                    "duration_seconds": round((datetime.now(UTC) - started).total_seconds(), 3),
                    "report": str(report_path),
                    "output": output,
                    "output_sha256": sha256_file(output) if output and Path(output).is_file() else None,
                }
            )
            context[step["id"]] = {"output": output, "report": str(report_path)}
            if isinstance(result, dict) and result.get("passed") is False:
                raise DocumentSystemError(f"Step {step['id']} returned passed=false")
        except Exception as exc:
            failed = True
            record.update(
                {
                    "status": "failed",
                    "completed_at": datetime.now(UTC).isoformat(),
                    "duration_seconds": round((datetime.now(UTC) - started).total_seconds(), 3),
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                    "traceback": traceback.format_exc(limit=12),
                }
            )
            write_json(manifest_path, manifest)
            if not workflow.get("continue_on_error", False):
                break
        write_json(manifest_path, manifest)
    manifest["completed_at"] = datetime.now(UTC).isoformat()
    manifest["status"] = "failed" if failed else "passed"
    manifest["manifest"] = str(manifest_path)
    write_json(manifest_path, manifest)
    return manifest
