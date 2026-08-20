from __future__ import annotations

import zipfile

from document_system.docx_build import build_docx
from document_system.docx_extract import extract_docx
from document_system.opc import inspect_ooxml
from document_system.qa import validate_docx


def test_builds_rich_valid_document(tmp_path, rich_spec):
    output = build_docx(rich_spec, tmp_path / "report.docx", base_dir=tmp_path)
    assert output.exists()
    package = inspect_ooxml(output)
    assert package["format"] == "docx"
    assert package["summary"]["errors"] == 0, package["issues"]

    extracted = extract_docx(output)
    assert "Операционный обзор" in extracted["text"]
    assert "цикл обработки сократился на 18%" in extracted["text"]
    assert extracted["inventory"]["tables"] >= 3  # cover, callout, content table
    assert extracted["inventory"]["media_parts"] == 1
    assert any("TOC" in value for value in extracted["fields"])

    report = validate_docx(
        output,
        require_header=True,
        require_footer=True,
        require_page_numbers=True,
        require_images=1,
        require_toc=True,
    )
    assert report["passed"], report["issues"]


def test_generated_docx_marks_fields_for_update(tmp_path, rich_spec):
    output = build_docx(rich_spec, tmp_path / "report.docx")
    with zipfile.ZipFile(output) as archive:
        settings = archive.read("word/settings.xml")
        assert b"updateFields" in settings
        footer = b"".join(
            archive.read(name)
            for name in archive.namelist()
            if name.startswith("word/footer") and name.endswith(".xml")
        )
        assert b"PAGE" in footer


def test_placeholder_is_a_validation_error(tmp_path, rich_spec):
    rich_spec["content"].append({"type": "paragraph", "text": "Client: {{CLIENT_NAME}}"})
    output = build_docx(rich_spec, tmp_path / "placeholder.docx")
    report = validate_docx(output)
    assert report["passed"] is False
    assert any(item["code"] == "placeholder-present" for item in report["issues"])
