from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_system.batch import run_batch
from document_system.compare import compare_documents
from document_system.conversion import convert_document
from document_system.doctor import doctor
from document_system.errors import UnsupportedDocumentError
from document_system.pdf_build import build_pdf
from document_system.workflow import run_workflow
from document_system.xlsx_build import build_xlsx
from document_system.xlsx_edit import apply_xlsx_edit_plan


def test_compare_pdf_semantic_and_visual(tmp_path):
    first = build_pdf(
        {"content": [{"type": "heading", "level": 1, "text": "Original"}]},
        tmp_path / "first.pdf",
    )
    second = build_pdf(
        {"content": [{"type": "heading", "level": 1, "text": "Modified"}]},
        tmp_path / "second.pdf",
    )
    report = compare_documents(
        first,
        second,
        visual=True,
        visual_dir=tmp_path / "difference",
    )
    assert report["format"] == "pdf"
    assert report["semantic"]["changed"] is True
    assert report["visual"]["original_pages"] == 1
    assert report["visual"]["pages"][0]["changed_pixel_ratio"] > 0


def test_compare_xlsx_reports_changed_package_parts(tmp_path):
    source = build_xlsx(
        {"sheets": [{"name": "Data", "cells": [{"cell": "A1", "value": 1}]}]},
        tmp_path / "source.xlsx",
    )
    modified = tmp_path / "modified.xlsx"
    apply_xlsx_edit_plan(
        source,
        modified,
        {"updates": [{"sheet": "Data", "cell": "A1", "expected": 1, "value": 2}]},
    )
    report = compare_documents(source, modified)
    assert report["semantic"]["changed"] is True
    assert report["package"]["changed_parts"] == ["xl/worksheets/sheet1.xml"]


def test_pdf_to_images_conversion(tmp_path):
    source = build_pdf(
        {"content": [{"type": "heading", "level": 1, "text": "Images"}]},
        tmp_path / "source.pdf",
    )
    result = convert_document(source, tmp_path / "images", target="images", dpi=100)
    assert result["pages"] == 1
    assert Path(result["files"][0]).is_file()
    assert result["contact_sheets"]


def test_rejects_false_fidelity_conversion(tmp_path):
    source = build_pdf(
        {"content": [{"type": "heading", "level": 1, "text": "PDF"}]},
        tmp_path / "source.pdf",
    )
    with pytest.raises(UnsupportedDocumentError, match="does not claim"):
        convert_document(source, tmp_path / "reconstructed.docx", target="docx")


def test_doctor_self_test(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    report = doctor(self_test=True)
    assert report["core_ready"] is True
    assert report["self_test"]["passed"] is True
    assert all(report["self_test"][name] for name in ("docx", "xlsx", "pptx", "pdf"))


def test_concurrent_cross_format_batch(tmp_path):
    documents = tmp_path / "documents"
    documents.mkdir()
    build_pdf(
        {"content": [{"type": "heading", "level": 1, "text": "PDF"}]},
        documents / "sample.pdf",
    )
    build_xlsx(
        {"sheets": [{"name": "Data", "cells": [{"cell": "A1", "value": "XLSX"}]}]},
        documents / "sample.xlsx",
    )
    from document_system.docx_build import build_docx
    from document_system.pptx_build import build_pptx

    build_docx(
        {"content": [{"type": "heading", "level": 1, "text": "DOCX"}]},
        documents / "sample.docx",
    )
    build_pptx(
        {"slides": [{"layout": "title", "title": "PPTX"}]},
        documents / "sample.pptx",
    )
    result = run_batch(
        [documents],
        tmp_path / "batch",
        action="inspect",
        workers=3,
    )
    assert result["status"] == "passed"
    assert result["files"] == 4
    assert result["failed"] == 0
    assert {item["format"] for item in result["items"]} == {"docx", "xlsx", "pptx", "pdf"}


def test_workflow_human_approval_hash_gate(tmp_path):
    artifact = build_pdf(
        {"content": [{"type": "heading", "level": 1, "text": "Approved"}]},
        tmp_path / "approved.pdf",
    )
    from document_system.util import sha256_file

    approval = tmp_path / "approval.json"
    approval.write_text(
        json.dumps(
            {
                "approved": True,
                "approved_by": "reviewer@example.com",
                "artifacts": [
                    {"path": str(artifact), "sha256": sha256_file(artifact)}
                ],
            }
        ),
        encoding="utf-8",
    )
    workflow = tmp_path / "approval-workflow.json"
    workflow.write_text(
        json.dumps(
            {
                "steps": [
                    {"id": "human-gate", "action": "approval", "plan": approval.name}
                ]
            }
        ),
        encoding="utf-8",
    )
    manifest = run_workflow(workflow, work_dir=tmp_path / "approval-work")
    assert manifest["status"] == "passed"

    value = json.loads(approval.read_text())
    value["artifacts"][0]["sha256"] = "0" * 64
    approval.write_text(json.dumps(value), encoding="utf-8")
    failed = run_workflow(workflow, work_dir=tmp_path / "approval-work-failed")
    assert failed["status"] == "failed"


def test_workflow_stops_when_validation_returns_false(tmp_path):
    spec = tmp_path / "pdf.json"
    spec.write_text(
        json.dumps({"content": [{"type": "heading", "level": 1, "text": "Actual"}]}),
        encoding="utf-8",
    )
    workflow = tmp_path / "failed-workflow.json"
    workflow.write_text(
        json.dumps(
            {
                "job_id": "failed-validation",
                "steps": [
                    {"id": "make", "action": "create", "format": "pdf", "spec": spec.name, "output": "actual.pdf"},
                    {
                        "id": "gate",
                        "action": "validate",
                        "input": "${make.output}",
                        "options": {"require_text": ["Missing requirement"]},
                    },
                    {"id": "never", "action": "inspect", "input": "${make.output}"},
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = run_workflow(workflow, work_dir=tmp_path / "failed-work")
    assert manifest["status"] == "failed"
    assert [step["id"] for step in manifest["steps"]] == ["make", "gate"]
    assert manifest["steps"][1]["status"] == "failed"


def test_wasm_batch_render_is_serialized(tmp_path, monkeypatch):
    first = build_pdf(
        {"content": [{"type": "paragraph", "text": "One"}]},
        tmp_path / "one.pdf",
    )
    second = build_pdf(
        {"content": [{"type": "paragraph", "text": "Two"}]},
        tmp_path / "two.pdf",
    )
    monkeypatch.setattr("document_system.batch.preferred_office_backend", lambda: "wasm")
    result = run_batch(
        [first, second],
        tmp_path / "render-batch",
        action="render",
        workers=4,
    )
    assert result["workers"] == 1
    assert result["status"] == "passed"


def test_cross_format_workflow_manifest(tmp_path):
    pdf_spec = tmp_path / "pdf.json"
    pdf_spec.write_text(
        json.dumps(
            {
                "metadata": {"title": "Workflow report"},
                "content": [
                    {"type": "heading", "level": 1, "text": "Workflow report"},
                    {"type": "paragraph", "text": "Deterministic orchestration"},
                ],
            }
        ),
        encoding="utf-8",
    )
    workflow = tmp_path / "workflow.json"
    workflow.write_text(
        json.dumps(
            {
                "job_id": "test-workflow",
                "steps": [
                    {
                        "id": "create",
                        "action": "create",
                        "format": "pdf",
                        "spec": pdf_spec.name,
                        "output": "result.pdf",
                    },
                    {
                        "id": "validate",
                        "action": "validate",
                        "input": "${create.output}",
                        "options": {"expected_pages": 1, "require_text": ["Workflow report"]},
                    },
                    {
                        "id": "render",
                        "action": "render",
                        "input": "${create.output}",
                        "output": "render",
                        "options": {"dpi": 100},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    work = tmp_path / "work"
    manifest = run_workflow(workflow, work_dir=work)
    assert manifest["status"] == "passed"
    assert [step["status"] for step in manifest["steps"]] == ["passed", "passed", "passed"]
    assert (work / "manifest.json").is_file()
    assert (tmp_path / "result.pdf").is_file()
    assert manifest["steps"][0]["output_sha256"]
