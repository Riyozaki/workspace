from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .batch import run_batch
from .brand_profile import apply_brand_profile_files
from .citations import build_citation_index, locate_text
from .compare import compare_documents
from .conversion import convert_document
from .diffing import diff_docx
from .doctor import doctor
from .docx_build import build_docx_from_file
from .docx_edit import apply_edit_plan_file
from .docx_extract import extract_docx
from .docx_revisions import apply_revision_view, verify_tracked_text
from .errors import DocumentSystemError
from .libreoffice import find_soffice, soffice_version
from .lineage import verify_lineage_file
from .microsoft_oracle import compare_libreoffice_to_microsoft
from .office_runtime import available_office_backends, preferred_office_backend
from .opc import inspect_ooxml
from .pdf_build import build_pdf_from_file
from .pdf_extract import extract_pdf
from .pdf_form_structure import infer_and_save_form_structure
from .pdf_forms import fill_pdf_form, overlay_pdf_file
from .pdf_ocr import ocr_pdf
from .pdf_qa import validate_pdf
from .pdf_redact import redact_pdf_file
from .pdf_transform import transform_pdf_file
from .pptx_build import build_pptx_from_file
from .pptx_edit import apply_pptx_edit_plan_file
from .pptx_extract import extract_pptx
from .pptx_qa import validate_pptx
from .pptx_structure import apply_pptx_structure_plan_file
from .qa import validate_docx
from .render import create_contact_sheets, render_document
from .security import detect_format
from .tabular import import_tabular_to_xlsx
from .util import read_json, write_json
from .wasm_office import wasm_office_version
from .workflow import run_workflow
from .xlsx_build import build_xlsx_from_file
from .xlsx_edit import apply_xlsx_edit_plan_file
from .xlsx_extract import extract_xlsx
from .xlsx_formula import build_formula_graph, lint_formulas, trace_formula
from .xlsx_qa import validate_xlsx
from .xlsx_recalc import recalculate_xlsx


def _print_json(value: Any) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _write_or_print(value: Any, path: str | None) -> None:
    if path:
        write_json(path, value)
        print(path)
    else:
        _print_json(value)


def command_env(args: argparse.Namespace) -> int:
    soffice = find_soffice()
    office_backends = available_office_backends()
    office_backend = preferred_office_backend()
    try:
        import pypandoc

        pandoc = pypandoc.get_pandoc_version()
    except Exception:
        pandoc = None
    value = {
        "documentctl": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "tools": {
            "soffice": str(soffice) if soffice else None,
            "soffice_version": soffice_version(soffice),
            "libreoffice_wasm": wasm_office_version(),
            "office_backends": office_backends,
            "preferred_office_backend": office_backend,
            "pandoc_version": str(pandoc) if pandoc else None,
        },
        "environment": {
            "DOCUMENT_SYSTEM_SOFFICE": os.environ.get("DOCUMENT_SYSTEM_SOFFICE"),
        },
    }
    _print_json(value)
    return 0 if office_backend else 1


def command_inspect(args: argparse.Namespace) -> int:
    fmt = detect_format(args.input)
    if fmt in {"docx", "xlsx", "pptx"}:
        report = inspect_ooxml(args.input)
        if fmt == "docx" and args.semantic:
            semantic = extract_docx(args.input, revisions=args.revisions)
            report["semantic"] = {
                "inventory": semantic["inventory"],
                "styles": semantic["styles"],
                "fields": semantic["fields"],
                "comments": semantic["comments"],
                "settings": semantic["settings"],
                "text": semantic["text"] if args.include_text else None,
            }
        elif fmt == "xlsx" and args.semantic:
            report["semantic"] = extract_xlsx(
                args.input,
                include_cells=args.include_text,
            )
        elif fmt == "pptx" and args.semantic:
            report["semantic"] = extract_pptx(args.input)
    elif fmt == "pdf":
        report = extract_pdf(args.input, extract_tables=args.include_text)
        if not args.include_text:
            report["text"] = None
            for page in report.get("pages", []):
                page["text"] = None
    else:
        report = {"path": args.input, "format": fmt}
    _write_or_print(report, args.output)
    return 2 if report.get("summary", {}).get("errors") else 0


def command_extract(args: argparse.Namespace) -> int:
    result = extract_docx(args.input, revisions=args.revisions)
    if args.format == "text":
        Path(args.output).write_text(result["text"] + "\n", encoding="utf-8") if args.output else print(result["text"])
    else:
        _write_or_print(result, args.output)
    return 0


def command_docx_revisions(args: argparse.Namespace) -> int:
    result = apply_revision_view(args.input, args.output, mode=args.mode)
    if args.validate:
        result["validation"] = validate_docx(args.output)
    _print_json(result)
    return 0 if not result.get("validation") or result["validation"]["passed"] else 2


def command_docx_tracked_check(args: argparse.Namespace) -> int:
    result = verify_tracked_text(args.original, args.modified)
    _write_or_print(result, args.output)
    return 0 if result["passed"] else 2


def command_create(args: argparse.Namespace) -> int:
    output = build_docx_from_file(args.spec, args.output)
    result: dict[str, Any] = {"output": str(output)}
    if args.validate:
        result["validation"] = validate_docx(
            output,
            render=args.render,
            render_dir=args.render_dir,
            require_header=args.require_header,
            require_footer=args.require_footer,
            require_page_numbers=args.require_page_numbers,
            require_toc=args.require_toc,
            require_images=args.require_images,
        )
    _print_json(result)
    if result.get("validation") and not result["validation"]["passed"]:
        return 2
    return 0


def command_edit(args: argparse.Namespace) -> int:
    result = apply_edit_plan_file(args.input, args.output, args.plan)
    if args.validate:
        result["validation"] = validate_docx(
            args.output,
            render=args.render,
            render_dir=args.render_dir,
            allow_placeholders=args.allow_placeholders,
        )
    _print_json(result)
    if result.get("validation") and not result["validation"]["passed"]:
        return 2
    return 0


def command_xlsx_create(args: argparse.Namespace) -> int:
    output = build_xlsx_from_file(args.spec, args.output)
    result: dict[str, Any] = {"output": str(output)}
    if args.validate:
        result["validation"] = validate_xlsx(
            output,
            render=args.render,
            render_dir=args.render_dir,
            require_sheets=args.require_sheet,
            require_cells=args.require_cell,
            require_formulas=args.require_formulas,
            require_recalculated=args.require_recalculated,
            libreoffice_compatible=args.libreoffice_compatible,
        )
    _print_json(result)
    return 0 if not result.get("validation") or result["validation"]["passed"] else 2


def command_xlsx_edit(args: argparse.Namespace) -> int:
    result = apply_xlsx_edit_plan_file(args.input, args.output, args.plan)
    if args.validate:
        result["validation"] = validate_xlsx(
            args.output,
            require_formulas=args.require_formulas,
            require_recalculated=args.require_recalculated,
            libreoffice_compatible=args.libreoffice_compatible,
            allow_placeholders=args.allow_placeholders,
        )
    _print_json(result)
    return 0 if not result.get("validation") or result["validation"]["passed"] else 2


def command_xlsx_import(args: argparse.Namespace) -> int:
    delimiter = "\t" if args.delimiter == "\\t" else args.delimiter
    result = import_tabular_to_xlsx(
        args.input,
        args.output,
        delimiter=delimiter,
        sheet_name=args.sheet,
        encoding=args.encoding,
    )
    if args.validate:
        result["validation"] = validate_xlsx(args.output)
    _print_json(result)
    return 0 if not result.get("validation") or result["validation"]["passed"] else 2


def command_xlsx_formulas(args: argparse.Namespace) -> int:
    result = lint_formulas(args.input, libreoffice_compatible=args.libreoffice_compatible)
    if not args.lint_only:
        result["graph"] = build_formula_graph(args.input)
    _write_or_print(result, args.output)
    errors = sum(item["severity"] == "error" for item in result["issues"])
    return 0 if errors == 0 else 2


def command_xlsx_trace(args: argparse.Namespace) -> int:
    result = trace_formula(
        args.input,
        args.reference,
        direction=args.direction,
        max_depth=args.max_depth,
    )
    _write_or_print(result, args.output)
    return 0


def command_xlsx_recalc(args: argparse.Namespace) -> int:
    result = recalculate_xlsx(
        args.input,
        args.output,
        timeout=args.timeout,
        force_external_links=args.force_external_links,
    )
    _print_json(result)
    return 0 if result["passed"] else 2


def command_xlsx_validate(args: argparse.Namespace) -> int:
    result = validate_xlsx(
        args.input,
        output_report=args.output,
        render=args.render,
        render_dir=args.render_dir,
        strict=args.strict,
        require_sheets=args.require_sheet,
        require_cells=args.require_cell,
        require_formulas=args.require_formulas,
        require_recalculated=args.require_recalculated,
        libreoffice_compatible=args.libreoffice_compatible,
        allow_placeholders=args.allow_placeholders,
        openxml_sdk=not args.no_openxml_sdk,
        require_openxml_sdk=args.require_openxml_sdk,
        timeout=args.timeout,
    )
    if args.output:
        print(args.output)
    else:
        _print_json(result)
    return 0 if result["passed"] else 2


def command_pptx_create(args: argparse.Namespace) -> int:
    output = build_pptx_from_file(args.spec, args.output)
    result: dict[str, Any] = {"output": str(output)}
    if args.validate:
        result["validation"] = validate_pptx(
            output,
            render=args.render,
            render_dir=args.render_dir,
            expected_slides=args.expected_slides,
            require_titles=not args.allow_missing_titles,
            require_notes=args.require_notes,
        )
    _print_json(result)
    return 0 if not result.get("validation") or result["validation"]["passed"] else 2


def command_pptx_edit(args: argparse.Namespace) -> int:
    result = apply_pptx_edit_plan_file(args.input, args.output, args.plan)
    if args.validate:
        result["validation"] = validate_pptx(
            args.output,
            render=args.render,
            render_dir=args.render_dir,
            allow_placeholders=args.allow_placeholders,
        )
    _print_json(result)
    return 0 if not result.get("validation") or result["validation"]["passed"] else 2


def command_pptx_structure(args: argparse.Namespace) -> int:
    result = apply_pptx_structure_plan_file(args.input, args.output, args.plan)
    if args.validate:
        result["validation"] = validate_pptx(
            args.output,
            original=args.input,
            require_titles=not args.allow_missing_titles,
        )
    _print_json(result)
    return 0 if not result.get("validation") or result["validation"]["passed"] else 2


def command_pptx_validate(args: argparse.Namespace) -> int:
    result = validate_pptx(
        args.input,
        output_report=args.output,
        render=args.render,
        render_dir=args.render_dir,
        strict=args.strict,
        expected_slides=args.expected_slides,
        require_titles=not args.allow_missing_titles,
        require_notes=args.require_notes,
        require_text=args.require_text,
        allow_placeholders=args.allow_placeholders,
        original=args.original,
        openxml_sdk=not args.no_openxml_sdk,
        require_openxml_sdk=args.require_openxml_sdk,
        timeout=args.timeout,
    )
    if args.output:
        print(args.output)
    else:
        _print_json(result)
    return 0 if result["passed"] else 2


def command_pdf_create(args: argparse.Namespace) -> int:
    output = build_pdf_from_file(args.spec, args.output)
    result: dict[str, Any] = {"output": str(output)}
    if args.validate:
        result["validation"] = validate_pdf(
            output,
            render=args.render,
            render_dir=args.render_dir,
            expected_pages=args.expected_pages,
        )
    _print_json(result)
    return 0 if not result.get("validation") or result["validation"]["passed"] else 2


def command_pdf_extract(args: argparse.Namespace) -> int:
    result = extract_pdf(args.input, password=args.password, extract_tables=args.tables)
    if args.output:
        write_json(args.output, result)
        print(args.output)
    else:
        _print_json(result)
    return 0


def command_pdf_transform(args: argparse.Namespace) -> int:
    _print_json(transform_pdf_file(args.plan, args.output))
    return 0


def command_pdf_overlay(args: argparse.Namespace) -> int:
    _print_json(overlay_pdf_file(args.input, args.output, args.plan))
    return 0


def command_pdf_form_structure(args: argparse.Namespace) -> int:
    result = infer_and_save_form_structure(
        args.input,
        args.output,
        image_dir=args.image_dir,
        dpi=args.dpi,
    )
    _print_json(
        {
            "output": args.output,
            "pages": result["page_count"],
            "fields": result["field_count"],
            "validation_images": result.get("validation_images", []),
        }
    )
    return 0


def command_pdf_redact(args: argparse.Namespace) -> int:
    result = redact_pdf_file(args.input, args.output, args.plan)
    _print_json(result)
    return 0


def command_pdf_fill(args: argparse.Namespace) -> int:
    values = read_json(args.values)
    if not isinstance(values, dict):
        raise ValueError("PDF form values file must contain a JSON object")
    _print_json(fill_pdf_form(args.input, args.output, values, password=args.password))
    return 0


def command_pdf_ocr(args: argparse.Namespace) -> int:
    _print_json(
        ocr_pdf(
            args.input,
            args.output,
            language=args.language,
            dpi=args.dpi,
            timeout_per_page=args.timeout_per_page,
        )
    )
    return 0


def command_pdf_validate(args: argparse.Namespace) -> int:
    result = validate_pdf(
        args.input,
        output_report=args.output,
        password=args.password,
        render=args.render,
        render_dir=args.render_dir,
        strict=args.strict,
        expected_pages=args.expected_pages,
        require_text=args.require_text,
        require_forms=args.require_forms,
        allow_placeholders=args.allow_placeholders,
        allow_risk_features=args.allow_risk_features,
    )
    if args.output:
        print(args.output)
    else:
        _print_json(result)
    return 0 if result["passed"] else 2


def command_render(args: argparse.Namespace) -> int:
    result = render_document(
        args.input,
        args.output_dir,
        dpi=args.dpi,
        contact_sheet=not args.no_contact_sheet,
        timeout=args.timeout,
    )
    _print_json(result)
    return 0


def command_validate(args: argparse.Namespace) -> int:
    result = validate_docx(
        args.input,
        output_report=args.output,
        render=args.render,
        render_dir=args.render_dir,
        strict=args.strict,
        expect_text=args.expect_text,
        forbid_text=args.forbid_text,
        require_header=args.require_header,
        require_footer=args.require_footer,
        require_page_numbers=args.require_page_numbers,
        require_images=args.require_images,
        require_toc=args.require_toc,
        allow_placeholders=args.allow_placeholders,
        tracked_against=args.tracked_against,
        openxml_sdk=not args.no_openxml_sdk,
        require_openxml_sdk=args.require_openxml_sdk,
        timeout=args.timeout,
    )
    if not args.output:
        _print_json(result)
    else:
        print(args.output)
    return 0 if result["passed"] else 2


def command_diff(args: argparse.Namespace) -> int:
    result = diff_docx(
        args.original,
        args.modified,
        output_report=args.output,
        visual=args.visual,
        visual_dir=args.visual_dir,
        timeout=args.timeout,
    )
    if not args.output:
        _print_json(result)
    else:
        print(args.output)
    return 0


def command_profile(args: argparse.Namespace) -> int:
    result = apply_brand_profile_files(
        args.profile,
        args.spec,
        args.output,
        format_name=args.format,
    )
    _print_json(result)
    return 0


def command_lineage(args: argparse.Namespace) -> int:
    result = verify_lineage_file(args.plan, output_report=args.output)
    if args.output:
        print(args.output)
    else:
        _print_json(result)
    return 0 if result["passed"] else 2


def command_citations(args: argparse.Namespace) -> int:
    result = build_citation_index(args.input, max_entries=args.max_entries)
    _write_or_print(result, args.output)
    return 0


def command_locate(args: argparse.Namespace) -> int:
    result = locate_text(
        args.input,
        args.query,
        case_sensitive=args.case_sensitive,
        max_hits=args.max_hits,
    )
    _write_or_print(result, args.output)
    return 0 if result["hit_count"] else 1


def command_batch(args: argparse.Namespace) -> int:
    result = run_batch(
        args.inputs,
        args.output_dir,
        action=args.action,
        workers=args.workers,
        recursive=args.recursive,
        render=args.render,
        timeout=args.timeout,
    )
    _print_json(result)
    return 0 if result["status"] == "passed" else 2


def command_microsoft_oracle(args: argparse.Namespace) -> int:
    result = compare_libreoffice_to_microsoft(
        args.input,
        args.output_dir,
        timeout=args.timeout,
    )
    write_json(Path(args.output_dir) / "oracle-report.json", result)
    _print_json(
        {
            "input": result["input"],
            "provider": result["microsoft"]["provider"],
            "comparison": str(Path(args.output_dir) / "oracle-report.json"),
            "visual_pages": len(result["comparison"]["visual"]["pages"]),
        }
    )
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    result = doctor(self_test=args.self_test)
    _write_or_print(result, args.output)
    return 0 if result["core_ready"] and (not args.self_test or result["self_test"]["passed"]) else 2


def command_compare(args: argparse.Namespace) -> int:
    result = compare_documents(
        args.original,
        args.modified,
        output_report=args.output,
        visual=args.visual,
        visual_dir=args.visual_dir,
        timeout=args.timeout,
    )
    if args.output:
        print(args.output)
    else:
        _print_json(result)
    return 0


def command_convert(args: argparse.Namespace) -> int:
    result = convert_document(
        args.input,
        args.output,
        target=args.to,
        timeout=args.timeout,
        dpi=args.dpi,
    )
    _print_json(result)
    return 0


def command_workflow(args: argparse.Namespace) -> int:
    result = run_workflow(args.workflow, work_dir=args.work_dir)
    _print_json(
        {
            "job_id": result["job_id"],
            "status": result["status"],
            "manifest": result["manifest"],
            "steps": [
                {"id": step["id"], "action": step["action"], "status": step["status"]}
                for step in result["steps"]
            ],
        }
    )
    return 0 if result["status"] == "passed" else 2


def command_contact_sheet(args: argparse.Namespace) -> int:
    images: list[Path] = []
    for value in args.images:
        path = Path(value)
        if path.is_dir():
            images.extend(sorted(path.glob("*.png")))
            images.extend(sorted(path.glob("*.jpg")))
            images.extend(sorted(path.glob("*.jpeg")))
        else:
            images.append(path)
    results = create_contact_sheets(
        images,
        args.output,
        columns=args.columns,
        max_pages_per_sheet=args.max_pages,
    )
    _print_json({"outputs": [str(path) for path in results]})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="documentctl",
        description="Create, edit, inspect, render, compare, and validate documents.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    env = subparsers.add_parser("env", help="Show document toolchain readiness")
    env.set_defaults(func=command_env)

    inspect = subparsers.add_parser("inspect", help="Inspect package integrity and document inventory")
    inspect.add_argument("input")
    inspect.add_argument("--output", "-o")
    inspect.add_argument("--semantic", action=argparse.BooleanOptionalAction, default=True)
    inspect.add_argument("--include-text", action="store_true")
    inspect.add_argument("--revisions", choices=("accept", "reject", "all"), default="accept")
    inspect.set_defaults(func=command_inspect)

    extract = subparsers.add_parser("extract", help="Extract DOCX text and semantic structure")
    extract.add_argument("input")
    extract.add_argument("--output", "-o")
    extract.add_argument("--format", choices=("text", "json"), default="text")
    extract.add_argument("--revisions", choices=("accept", "reject", "all"), default="accept")
    extract.set_defaults(func=command_extract)

    create = subparsers.add_parser("create", help="Create a DOCX from a declarative JSON specification")
    create.add_argument("spec")
    create.add_argument("output")
    create.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
    create.add_argument("--render", action="store_true")
    create.add_argument("--render-dir")
    create.add_argument("--require-header", action="store_true")
    create.add_argument("--require-footer", action="store_true")
    create.add_argument("--require-page-numbers", action="store_true")
    create.add_argument("--require-toc", action="store_true")
    create.add_argument("--require-images", type=int, default=0)
    create.set_defaults(func=command_create)

    edit = subparsers.add_parser("edit", help="Apply replacements, tracked changes, and comments to DOCX")
    edit.add_argument("input")
    edit.add_argument("output")
    edit.add_argument("--plan", required=True)
    edit.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
    edit.add_argument("--render", action="store_true")
    edit.add_argument("--render-dir")
    edit.add_argument("--allow-placeholders", action="store_true")
    edit.set_defaults(func=command_edit)

    docx_revisions = subparsers.add_parser("docx-revisions", help="Accept or reject tracked revisions into a clean DOCX")
    docx_revisions.add_argument("input")
    docx_revisions.add_argument("output")
    docx_revisions.add_argument("--mode", choices=("accept", "reject"), required=True)
    docx_revisions.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
    docx_revisions.set_defaults(func=command_docx_revisions)

    docx_tracked = subparsers.add_parser("docx-tracked-check", help="Prove that rejecting revisions reproduces original visible text")
    docx_tracked.add_argument("original")
    docx_tracked.add_argument("modified")
    docx_tracked.add_argument("--output", "-o")
    docx_tracked.set_defaults(func=command_docx_tracked_check)

    xlsx_create = subparsers.add_parser("xlsx-create", help="Create an XLSX from a declarative JSON specification")
    xlsx_create.add_argument("spec")
    xlsx_create.add_argument("output")
    xlsx_create.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
    xlsx_create.add_argument("--render", action="store_true")
    xlsx_create.add_argument("--render-dir")
    xlsx_create.add_argument("--require-sheet", action="append", default=[])
    xlsx_create.add_argument("--require-cell", action="append", default=[])
    xlsx_create.add_argument("--require-formulas", action="store_true")
    xlsx_create.add_argument("--require-recalculated", action="store_true")
    xlsx_create.add_argument("--libreoffice-compatible", action="store_true")
    xlsx_create.set_defaults(func=command_xlsx_create)

    xlsx_edit = subparsers.add_parser("xlsx-edit", help="Apply atomic cell/formula updates to an XLSX")
    xlsx_edit.add_argument("input")
    xlsx_edit.add_argument("output")
    xlsx_edit.add_argument("--plan", required=True)
    xlsx_edit.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
    xlsx_edit.add_argument("--require-formulas", action="store_true")
    xlsx_edit.add_argument("--require-recalculated", action="store_true")
    xlsx_edit.add_argument("--libreoffice-compatible", action="store_true")
    xlsx_edit.add_argument("--allow-placeholders", action="store_true")
    xlsx_edit.set_defaults(func=command_xlsx_edit)

    xlsx_import = subparsers.add_parser("xlsx-import", help="Normalize CSV/TSV into a styled native Excel table")
    xlsx_import.add_argument("input")
    xlsx_import.add_argument("output")
    xlsx_import.add_argument("--delimiter", help="single character or \\t; auto-detected by default")
    xlsx_import.add_argument("--sheet", default="Data")
    xlsx_import.add_argument("--encoding", default="utf-8-sig")
    xlsx_import.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
    xlsx_import.set_defaults(func=command_xlsx_import)

    xlsx_formulas = subparsers.add_parser("xlsx-formulas", help="Build a formula dependency graph and compatibility lint")
    xlsx_formulas.add_argument("input")
    xlsx_formulas.add_argument("--output", "-o")
    xlsx_formulas.add_argument("--lint-only", action="store_true")
    xlsx_formulas.add_argument("--libreoffice-compatible", action="store_true")
    xlsx_formulas.set_defaults(func=command_xlsx_formulas)

    xlsx_trace = subparsers.add_parser("xlsx-trace", help="Trace formula precedents or dependents with cell citations")
    xlsx_trace.add_argument("input")
    xlsx_trace.add_argument("reference", help="Sheet!A1")
    xlsx_trace.add_argument("--direction", choices=("precedents", "dependents"), default="precedents")
    xlsx_trace.add_argument("--max-depth", type=int, default=20)
    xlsx_trace.add_argument("--output", "-o")
    xlsx_trace.set_defaults(func=command_xlsx_trace)

    xlsx_recalc = subparsers.add_parser("xlsx-recalc", help="Recalculate formulas through isolated LibreOffice")
    xlsx_recalc.add_argument("input")
    xlsx_recalc.add_argument("output")
    xlsx_recalc.add_argument("--timeout", type=int, default=240)
    xlsx_recalc.add_argument("--force-external-links", action="store_true")
    xlsx_recalc.set_defaults(func=command_xlsx_recalc)

    xlsx_validate = subparsers.add_parser("xlsx-validate", help="Run package, formula, semantic, and visual XLSX QA")
    xlsx_validate.add_argument("input")
    xlsx_validate.add_argument("--output", "-o")
    xlsx_validate.add_argument("--render", action="store_true")
    xlsx_validate.add_argument("--render-dir")
    xlsx_validate.add_argument("--strict", action="store_true")
    xlsx_validate.add_argument("--require-sheet", action="append", default=[])
    xlsx_validate.add_argument("--require-cell", action="append", default=[])
    xlsx_validate.add_argument("--require-formulas", action="store_true")
    xlsx_validate.add_argument("--require-recalculated", action="store_true")
    xlsx_validate.add_argument("--libreoffice-compatible", action="store_true")
    xlsx_validate.add_argument("--allow-placeholders", action="store_true")
    xlsx_validate.add_argument("--no-openxml-sdk", action="store_true")
    xlsx_validate.add_argument("--require-openxml-sdk", action="store_true")
    xlsx_validate.add_argument("--timeout", type=int, default=240)
    xlsx_validate.set_defaults(func=command_xlsx_validate)

    pptx_create = subparsers.add_parser("pptx-create", help="Create a PPTX from a declarative JSON specification")
    pptx_create.add_argument("spec")
    pptx_create.add_argument("output")
    pptx_create.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
    pptx_create.add_argument("--render", action="store_true")
    pptx_create.add_argument("--render-dir")
    pptx_create.add_argument("--expected-slides", type=int)
    pptx_create.add_argument("--allow-missing-titles", action="store_true")
    pptx_create.add_argument("--require-notes", action="store_true")
    pptx_create.set_defaults(func=command_pptx_create)

    pptx_edit = subparsers.add_parser("pptx-edit", help="Apply preservation-safe text/media edits to PPTX")
    pptx_edit.add_argument("input")
    pptx_edit.add_argument("output")
    pptx_edit.add_argument("--plan", required=True)
    pptx_edit.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
    pptx_edit.add_argument("--render", action="store_true")
    pptx_edit.add_argument("--render-dir")
    pptx_edit.add_argument("--allow-placeholders", action="store_true")
    pptx_edit.set_defaults(func=command_pptx_edit)

    pptx_structure = subparsers.add_parser("pptx-structure", help="Duplicate, delete, reorder, and clean slides safely")
    pptx_structure.add_argument("input")
    pptx_structure.add_argument("output")
    pptx_structure.add_argument("--plan", required=True)
    pptx_structure.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
    pptx_structure.add_argument("--allow-missing-titles", action="store_true")
    pptx_structure.set_defaults(func=command_pptx_structure)

    pptx_validate = subparsers.add_parser("pptx-validate", help="Run package, content, geometry, and visual PPTX QA")
    pptx_validate.add_argument("input")
    pptx_validate.add_argument("--output", "-o")
    pptx_validate.add_argument("--render", action="store_true")
    pptx_validate.add_argument("--render-dir")
    pptx_validate.add_argument("--strict", action="store_true")
    pptx_validate.add_argument("--expected-slides", type=int)
    pptx_validate.add_argument("--allow-missing-titles", action="store_true")
    pptx_validate.add_argument("--require-notes", action="store_true")
    pptx_validate.add_argument("--require-text", action="append", default=[])
    pptx_validate.add_argument("--allow-placeholders", action="store_true")
    pptx_validate.add_argument("--original", help="baseline template whose inherited package issues are ignored")
    pptx_validate.add_argument("--no-openxml-sdk", action="store_true")
    pptx_validate.add_argument("--require-openxml-sdk", action="store_true")
    pptx_validate.add_argument("--timeout", type=int, default=240)
    pptx_validate.set_defaults(func=command_pptx_validate)

    pdf_create = subparsers.add_parser("pdf-create", help="Create a PDF from a declarative JSON specification")
    pdf_create.add_argument("spec")
    pdf_create.add_argument("output")
    pdf_create.add_argument("--validate", action=argparse.BooleanOptionalAction, default=True)
    pdf_create.add_argument("--render", action="store_true")
    pdf_create.add_argument("--render-dir")
    pdf_create.add_argument("--expected-pages", type=int)
    pdf_create.set_defaults(func=command_pdf_create)

    pdf_extract = subparsers.add_parser("pdf-extract", help="Extract PDF text, forms, metadata, and optional tables")
    pdf_extract.add_argument("input")
    pdf_extract.add_argument("--output", "-o")
    pdf_extract.add_argument("--password")
    pdf_extract.add_argument("--tables", action="store_true")
    pdf_extract.set_defaults(func=command_pdf_extract)

    pdf_transform = subparsers.add_parser("pdf-transform", help="Merge, select, rotate, watermark, or encrypt PDFs")
    pdf_transform.add_argument("plan")
    pdf_transform.add_argument("output")
    pdf_transform.set_defaults(func=command_pdf_transform)

    pdf_overlay = subparsers.add_parser("pdf-overlay", help="Place text, checks, boxes, or images using top-left coordinates")
    pdf_overlay.add_argument("input")
    pdf_overlay.add_argument("output")
    pdf_overlay.add_argument("--plan", required=True)
    pdf_overlay.set_defaults(func=command_pdf_overlay)

    pdf_form_structure = subparsers.add_parser("pdf-form-structure", help="Infer fields in non-fillable forms and create validation images")
    pdf_form_structure.add_argument("input")
    pdf_form_structure.add_argument("--output", "-o", required=True)
    pdf_form_structure.add_argument("--image-dir")
    pdf_form_structure.add_argument("--dpi", type=int, default=144)
    pdf_form_structure.set_defaults(func=command_pdf_form_structure)

    pdf_redact = subparsers.add_parser("pdf-redact", help="Securely redact by raster reconstruction and remove original streams")
    pdf_redact.add_argument("input")
    pdf_redact.add_argument("output")
    pdf_redact.add_argument("--plan", required=True)
    pdf_redact.set_defaults(func=command_pdf_redact)

    pdf_fill = subparsers.add_parser("pdf-fill", help="Fill existing AcroForm fields")
    pdf_fill.add_argument("input")
    pdf_fill.add_argument("output")
    pdf_fill.add_argument("--values", required=True)
    pdf_fill.add_argument("--password")
    pdf_fill.set_defaults(func=command_pdf_fill)

    pdf_ocr = subparsers.add_parser("pdf-ocr", help="Create a searchable raster PDF through Tesseract")
    pdf_ocr.add_argument("input")
    pdf_ocr.add_argument("output")
    pdf_ocr.add_argument("--language", default="eng")
    pdf_ocr.add_argument("--dpi", type=int, default=300)
    pdf_ocr.add_argument("--timeout-per-page", type=int, default=120)
    pdf_ocr.set_defaults(func=command_pdf_ocr)

    pdf_validate = subparsers.add_parser("pdf-validate", help="Run parse, content, safety, font, and visual PDF QA")
    pdf_validate.add_argument("input")
    pdf_validate.add_argument("--output", "-o")
    pdf_validate.add_argument("--password")
    pdf_validate.add_argument("--render", action="store_true")
    pdf_validate.add_argument("--render-dir")
    pdf_validate.add_argument("--strict", action="store_true")
    pdf_validate.add_argument("--expected-pages", type=int)
    pdf_validate.add_argument("--require-text", action="append", default=[])
    pdf_validate.add_argument("--require-forms", action="store_true")
    pdf_validate.add_argument("--allow-placeholders", action="store_true")
    pdf_validate.add_argument("--allow-risk-features", action="store_true")
    pdf_validate.set_defaults(func=command_pdf_validate)

    render = subparsers.add_parser("render", help="Render an Office/PDF file to PDF, page images, and contact sheet")
    render.add_argument("input")
    render.add_argument("--output-dir", "-o", required=True)
    render.add_argument("--dpi", type=int, default=144)
    render.add_argument("--timeout", type=int, default=180)
    render.add_argument("--no-contact-sheet", action="store_true")
    render.set_defaults(func=command_render)

    validate = subparsers.add_parser("validate", help="Run package, semantic, business, and optional visual QA")
    validate.add_argument("input")
    validate.add_argument("--output", "-o")
    validate.add_argument("--render", action="store_true")
    validate.add_argument("--render-dir")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--expect-text", action="append", default=[])
    validate.add_argument("--forbid-text", action="append", default=[])
    validate.add_argument("--require-header", action="store_true")
    validate.add_argument("--require-footer", action="store_true")
    validate.add_argument("--require-page-numbers", action="store_true")
    validate.add_argument("--require-images", type=int, default=0)
    validate.add_argument("--require-toc", action="store_true")
    validate.add_argument("--allow-placeholders", action="store_true")
    validate.add_argument("--tracked-against", help="original DOCX used to verify all visible text edits are tracked")
    validate.add_argument("--no-openxml-sdk", action="store_true", help="skip optional Microsoft Open XML SDK validation")
    validate.add_argument("--require-openxml-sdk", action="store_true", help="fail if the optional .NET validator is unavailable")
    validate.add_argument("--timeout", type=int, default=180)
    validate.set_defaults(func=command_validate)

    diff = subparsers.add_parser("diff", help="Compare DOCX package parts, text, and optional rendering")
    diff.add_argument("original")
    diff.add_argument("modified")
    diff.add_argument("--output", "-o")
    diff.add_argument("--visual", action="store_true")
    diff.add_argument("--visual-dir")
    diff.add_argument("--timeout", type=int, default=180)
    diff.set_defaults(func=command_diff)

    compare = subparsers.add_parser("compare", help="Compare DOCX, XLSX, PPTX, or PDF semantically and visually")
    compare.add_argument("original")
    compare.add_argument("modified")
    compare.add_argument("--output", "-o")
    compare.add_argument("--visual", action="store_true")
    compare.add_argument("--visual-dir")
    compare.add_argument("--timeout", type=int, default=240)
    compare.set_defaults(func=command_compare)

    convert = subparsers.add_parser("convert", help="Perform a supported, explicit document conversion")
    convert.add_argument("input")
    convert.add_argument("output")
    convert.add_argument("--to", required=True, choices=("pdf", "docx", "xlsx", "pptx", "images"))
    convert.add_argument("--timeout", type=int, default=240)
    convert.add_argument("--dpi", type=int, default=144)
    convert.set_defaults(func=command_convert)

    profile = subparsers.add_parser("profile", help="Apply a reusable brand profile to a document specification")
    profile.add_argument("profile")
    profile.add_argument("spec")
    profile.add_argument("output")
    profile.add_argument("--format", choices=("docx", "xlsx", "pptx", "pdf"), required=True)
    profile.set_defaults(func=command_profile)

    lineage = subparsers.add_parser("lineage", help="Verify claims across source and target documents with native citations")
    lineage.add_argument("plan")
    lineage.add_argument("--output", "-o")
    lineage.set_defaults(func=command_lineage)

    citations = subparsers.add_parser("citations", help="Build stable paragraph/cell/shape/page citation locators")
    citations.add_argument("input")
    citations.add_argument("--output", "-o")
    citations.add_argument("--max-entries", type=int, default=200000)
    citations.set_defaults(func=command_citations)

    locate = subparsers.add_parser("locate", help="Find text and return format-native citations")
    locate.add_argument("input")
    locate.add_argument("query")
    locate.add_argument("--case-sensitive", action="store_true")
    locate.add_argument("--max-hits", type=int, default=100)
    locate.add_argument("--output", "-o")
    locate.set_defaults(func=command_locate)

    batch = subparsers.add_parser("batch", help="Inspect, validate, or render documents concurrently")
    batch.add_argument("inputs", nargs="+")
    batch.add_argument("--output-dir", "-o", required=True)
    batch.add_argument("--action", choices=("inspect", "validate", "render"), default="inspect")
    batch.add_argument("--workers", type=int)
    batch.add_argument("--recursive", action="store_true")
    batch.add_argument("--render", action="store_true", help="render during batch validation")
    batch.add_argument("--timeout", type=int, default=240)
    batch.set_defaults(func=command_batch)

    microsoft_oracle = subparsers.add_parser("microsoft-oracle", help="Compare LibreOffice rendering with Microsoft Graph Office rendering")
    microsoft_oracle.add_argument("input")
    microsoft_oracle.add_argument("--output-dir", "-o", required=True)
    microsoft_oracle.add_argument("--timeout", type=int, default=180)
    microsoft_oracle.set_defaults(func=command_microsoft_oracle)

    doctor_parser = subparsers.add_parser("doctor", help="Report toolchain readiness and optionally run smoke tests")
    doctor_parser.add_argument("--self-test", action="store_true")
    doctor_parser.add_argument("--output", "-o")
    doctor_parser.set_defaults(func=command_doctor)

    workflow_parser = subparsers.add_parser("workflow", help="Run a deterministic cross-format workflow and write a manifest")
    workflow_parser.add_argument("workflow")
    workflow_parser.add_argument("--work-dir")
    workflow_parser.set_defaults(func=command_workflow)

    contact = subparsers.add_parser("contact-sheet", help="Create labeled contact sheets from page images")
    contact.add_argument("images", nargs="+")
    contact.add_argument("--output", "-o", required=True)
    contact.add_argument("--columns", type=int, default=4)
    contact.add_argument("--max-pages", type=int, default=20)
    contact.set_defaults(func=command_contact_sheet)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (DocumentSystemError, FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"documentctl: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
