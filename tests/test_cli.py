from __future__ import annotations

import json
from pathlib import Path

from document_system.cli import main


def test_cli_create_inspect_extract_validate(tmp_path, rich_spec, capsys):
    spec = tmp_path / "spec.json"
    output = tmp_path / "report.docx"
    spec.write_text(json.dumps(rich_spec, ensure_ascii=False), encoding="utf-8")

    assert main(["create", str(spec), str(output), "--require-footer", "--require-page-numbers"]) == 0
    capsys.readouterr()
    inspection = tmp_path / "inspection.json"
    assert main(["inspect", str(output), "-o", str(inspection)]) == 0
    capsys.readouterr()
    assert json.loads(inspection.read_text())["summary"]["errors"] == 0

    text = tmp_path / "content.txt"
    assert main(["extract", str(output), "-o", str(text)]) == 0
    capsys.readouterr()
    assert "Операционный обзор" in text.read_text(encoding="utf-8")

    qa = tmp_path / "qa.json"
    assert main(["validate", str(output), "-o", str(qa), "--require-images", "1"]) == 0
    capsys.readouterr()
    assert json.loads(qa.read_text())["passed"] is True


def test_cli_xlsx_create_edit_validate(tmp_path, capsys):
    root = Path(__file__).resolve().parents[1]
    spec = root / "examples/xlsx/operational-dashboard.json"
    plan = root / "examples/xlsx/scenario-update.json"
    source = tmp_path / "dashboard.xlsx"
    edited = tmp_path / "scenario.xlsx"
    qa = tmp_path / "qa.json"

    assert main(["xlsx-create", str(spec), str(source), "--require-formulas"]) == 0
    capsys.readouterr()
    assert main(["xlsx-edit", str(source), str(edited), "--plan", str(plan)]) == 0
    capsys.readouterr()
    assert main(["xlsx-validate", str(edited), "-o", str(qa), "--require-sheet", "Панель"]) == 0
    capsys.readouterr()
    report = json.loads(qa.read_text())
    assert report["passed"] is True
    assert report["workbook"]["totals"]["formulas"] == 4


def test_cli_pptx_create_edit_validate(tmp_path, capsys):
    root = Path(__file__).resolve().parents[1]
    spec = root / "examples/pptx/operational-review.json"
    plan = root / "examples/pptx/review-plan.json"
    source = tmp_path / "review.pptx"
    edited = tmp_path / "updated.pptx"
    qa = tmp_path / "qa-pptx.json"

    assert main(["pptx-create", str(spec), str(source), "--expected-slides", "9", "--require-notes"]) == 0
    capsys.readouterr()
    assert main(["pptx-edit", str(source), str(edited), "--plan", str(plan)]) == 0
    capsys.readouterr()
    assert main(["pptx-validate", str(edited), "-o", str(qa), "--expected-slides", "9"]) == 0
    capsys.readouterr()
    report = json.loads(qa.read_text())
    assert report["passed"] is True
    assert report["presentation"]["totals"]["slides"] == 9


def test_cli_pdf_create_extract_validate(tmp_path, capsys):
    root = Path(__file__).resolve().parents[1]
    spec = root / "examples/pdf/operational-report.json"
    output = tmp_path / "report.pdf"
    extracted = tmp_path / "pdf.json"
    qa = tmp_path / "qa-pdf.json"

    assert main(["pdf-create", str(spec), str(output), "--render", "--render-dir", str(tmp_path / "render")]) == 0
    capsys.readouterr()
    assert main(["pdf-extract", str(output), "-o", str(extracted), "--tables"]) == 0
    capsys.readouterr()
    assert main(["pdf-validate", str(output), "-o", str(qa), "--expected-pages", "4", "--require-text", "7 ноября"]) == 0
    capsys.readouterr()
    assert json.loads(extracted.read_text())["tables"]
    assert json.loads(qa.read_text())["passed"] is True


def test_cli_render_fails_cleanly_without_renderer(tmp_path, rich_spec, capsys):
    from document_system.docx_build import build_docx
    from document_system.office_runtime import preferred_office_backend

    if preferred_office_backend() is not None:
        return
    source = build_docx(rich_spec, tmp_path / "report.docx")
    assert main(["render", str(source), "-o", str(tmp_path / "render")]) == 2
    error = capsys.readouterr().err
    assert "LibreOffice/soffice not found" in error
