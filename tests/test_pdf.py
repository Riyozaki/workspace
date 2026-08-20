from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from document_system.pdf_build import build_pdf
from document_system.pdf_extract import extract_pdf
from document_system.pdf_form_structure import (
    create_form_structure_images,
    infer_pdf_form_structure,
)
from document_system.pdf_forms import fill_pdf_form, overlay_pdf
from document_system.pdf_ocr import ocr_pdf
from document_system.pdf_qa import validate_pdf
from document_system.pdf_redact import redact_pdf
from document_system.pdf_transform import PdfTransformError, parse_page_range, transform_pdf


@pytest.fixture
def pdf_spec():
    path = Path(__file__).resolve().parents[1] / "examples/pdf/operational-report.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_builds_and_visually_validates_rich_pdf(tmp_path, pdf_spec):
    output = build_pdf(pdf_spec, tmp_path / "report.pdf")
    extracted = extract_pdf(output, extract_tables=True)
    assert extracted["page_count"] == 4
    assert "Операционная эффективность" in " ".join(extracted["text"].split())
    assert "План действий" in extracted["text"]
    toc_text = extracted["pages"][1]["text"]
    assert "Резюме" in toc_text
    assert "Ключевые показатели" in toc_text
    assert "■" not in extracted["text"]
    assert extracted["unembedded_fonts"] == []
    assert extracted["risk_features"] == []
    assert extracted["tables"]
    report = validate_pdf(
        output,
        render=True,
        render_dir=tmp_path / "render",
        expected_pages=4,
        require_text=["цикл обработки сократился", "7 ноября"],
    )
    assert report["passed"] is True, report["issues"]
    assert report["summary"] == {"errors": 0, "warnings": 0, "info": 0}
    assert report["render"]["page_count"] == 4
    assert report["render"]["contact_sheets"]


def test_transform_merge_select_rotate_and_watermark(tmp_path, pdf_spec):
    first = build_pdf({"metadata": {"title": "First"}, "content": [{"type": "heading", "level": 1, "text": "First"}]}, tmp_path / "first.pdf")
    second = build_pdf({"metadata": {"title": "Second"}, "content": [{"type": "heading", "level": 1, "text": "Second"}]}, tmp_path / "second.pdf")
    output = tmp_path / "combined.pdf"
    result = transform_pdf(
        {
            "inputs": [
                {"path": first.name, "pages": "1"},
                {"path": second.name, "pages": "1"},
            ],
            "rotate": [{"pages": "2", "degrees": 90}],
            "watermark": {"text": "DRAFT", "opacity": 0.12, "angle": 35},
            "metadata": {"title": "Combined"},
        },
        output,
        base_dir=tmp_path,
    )
    assert result["pages"] == 2
    reader = PdfReader(output)
    assert len(reader.pages) == 2
    assert reader.pages[1].rotation == 90
    assert reader.metadata.title == "Combined"
    assert "DRAFT" in (reader.pages[0].extract_text() or "")


def test_overlay_uses_top_left_coordinates(tmp_path, pdf_spec):
    source = build_pdf({"metadata": {"title": "Overlay"}, "content": [{"type": "heading", "level": 1, "text": "Overlay form"}]}, tmp_path / "source.pdf")
    output = tmp_path / "overlay.pdf"
    result = overlay_pdf(
        source,
        output,
        {
            "items": [
                {"page": 1, "type": "text", "x": 80, "y": 120, "width": 240, "height": 24, "text": "APPROVED", "font_size": 12},
                {"page": 1, "type": "check", "x": 80, "y": 165, "width": 18, "height": 18, "color": "26734D"},
                {"page": 1, "type": "rectangle", "x": 70, "y": 105, "width": 280, "height": 95, "color": "C7863B"},
            ]
        },
    )
    assert result["items"] == 3
    assert "APPROVED" in extract_pdf(output)["text"]
    assert validate_pdf(output, render=True, render_dir=tmp_path / "overlay-render")["passed"] is True


def test_overlay_rejects_out_of_bounds_item(tmp_path):
    source = build_pdf(
        {"content": [{"type": "heading", "level": 1, "text": "Bounds"}]},
        tmp_path / "source.pdf",
    )
    from document_system.pdf_forms import PdfFormError

    with pytest.raises(PdfFormError, match="exceeds page bounds"):
        overlay_pdf(
            source,
            tmp_path / "bad.pdf",
            {
                "items": [
                    {
                        "page": 1,
                        "type": "text",
                        "x": 550,
                        "y": 800,
                        "width": 100,
                        "height": 100,
                        "text": "outside",
                    }
                ]
            },
        )


def test_infers_nonfillable_form_structure(tmp_path):
    source = tmp_path / "flat-form.pdf"
    pdf = canvas.Canvas(str(source), pagesize=(400, 300))
    pdf.drawString(40, 245, "Legal name")
    pdf.rect(120, 230, 220, 24, stroke=1, fill=0)
    pdf.drawString(40, 195, "Approved")
    pdf.rect(120, 187, 14, 14, stroke=1, fill=0)
    pdf.drawString(40, 150, "Comments")
    pdf.line(120, 145, 340, 145)
    pdf.save()
    structure = infer_pdf_form_structure(source)
    assert structure["field_count"] >= 3
    assert any(field["label"] == "Legal name" for field in structure["pages"][0]["fields"])
    assert any(field["type"] == "checkbox" for field in structure["pages"][0]["fields"])
    images = create_form_structure_images(source, structure, tmp_path / "structure-images")
    assert len(images) == 1 and images[0].is_file()


def test_secure_raster_redaction_removes_original_streams(tmp_path):
    source = tmp_path / "secret.pdf"
    pdf = canvas.Canvas(str(source), pagesize=(400, 300))
    pdf.setFont("Helvetica", 16)
    pdf.drawString(100, 150, "SECRET CODE 1234")
    pdf.save()
    output = tmp_path / "redacted.pdf"
    result = redact_pdf(
        source,
        output,
        {
            "dpi": 200,
            "rectangles": [
                {"page": 1, "x": 92, "y": 130, "width": 170, "height": 30}
            ],
            "verify_absent": ["SECRET", "1234"],
        },
    )
    assert result["mode"] == "secure-raster-reconstruction"
    assert result["text_objects_remaining"] == 0
    assert "SECRET" not in output.read_bytes().decode("latin1", errors="ignore")
    qa = validate_pdf(output, render=True, render_dir=tmp_path / "redacted-render")
    assert qa["passed"] is True


def test_fill_acroform(tmp_path):
    source = tmp_path / "form.pdf"
    pdf = canvas.Canvas(str(source), pagesize=(400, 300))
    pdf.drawString(50, 250, "Name")
    pdf.acroForm.textfield(name="name", x=100, y=235, width=200, height=24, borderStyle="underlined")
    pdf.acroForm.checkbox(name="approved", x=100, y=190, size=16)
    pdf.save()
    output = tmp_path / "filled.pdf"
    result = fill_pdf_form(source, output, {"name": "Alice", "approved": "/Yes"})
    assert result["field_count"] == 2
    fields = PdfReader(output).get_fields()
    assert fields["name"]["/V"] == "Alice"
    assert str(fields["approved"]["/V"]) == "/Yes"


def test_active_javascript_fails_safety_gate(tmp_path):
    output = tmp_path / "javascript.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.add_js("app.alert('hello')")
    with output.open("wb") as handle:
        writer.write(handle)
    report = validate_pdf(output)
    assert report["passed"] is False
    assert any(item["code"] == "active-or-embedded-content" for item in report["issues"])


def test_missing_glyph_sequence_fails_visual_safety_gate(tmp_path):
    output = build_pdf(
        {"content": [{"type": "paragraph", "text": "■■■■ garbled text"}]},
        tmp_path / "missing-glyphs.pdf",
    )
    report = validate_pdf(output)
    assert report["passed"] is False
    assert any(item["code"] == "missing-glyph-markers" for item in report["issues"])


def test_page_range_validation():
    assert parse_page_range("1,3-4", 5) == [0, 2, 3]
    with pytest.raises(PdfTransformError):
        parse_page_range("4-2", 5)
    with pytest.raises(PdfTransformError):
        parse_page_range("6", 5)


@pytest.mark.integration
def test_tesseract_ocr_route(tmp_path):
    from document_system.wasm_ocr import find_wasm_ocr

    if shutil.which("tesseract") is None and find_wasm_ocr() is None:
        pytest.skip("Tesseract is not available")
    source = tmp_path / "scan.pdf"
    pdf = canvas.Canvas(str(source), pagesize=(400, 300))
    pdf.setFont("Helvetica", 20)
    pdf.drawString(40, 150, "SEARCHABLE OCR TEST")
    pdf.save()
    output = tmp_path / "ocr.pdf"
    result = ocr_pdf(source, output, language="eng", dpi=200)
    assert result["pages"] == 1
    assert "OCR" in extract_pdf(output)["text"]
