from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from document_system.docx_build import build_docx
from document_system.office_runtime import preferred_office_backend
from document_system.pptx_build import build_pptx
from document_system.render import analyze_page_image, create_contact_sheets, render_document
from document_system.xlsx_build import build_xlsx
from document_system.xlsx_recalc import recalculate_xlsx


def test_contact_sheet_and_page_analysis(tmp_path):
    pages = []
    for index in range(5):
        path = tmp_path / f"page-{index + 1:03d}.png"
        image = Image.new("RGB", (600, 850), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((60, 70, 540, 780), outline="black", width=2)
        draw.text((80, 90), f"Page {index + 1}", fill="black")
        image.save(path)
        pages.append(path)
    outputs = create_contact_sheets(pages, tmp_path / "contact.png", columns=3)
    assert len(outputs) == 1
    assert outputs[0].exists()
    analysis = analyze_page_image(pages[0])
    assert analysis["likely_blank"] is False
    assert analysis["possible_edge_clipping"] is False


@pytest.mark.integration
def test_libreoffice_render_pipeline(tmp_path, rich_spec):
    if preferred_office_backend() is None:
        pytest.skip("LibreOffice is not available in this runtime")
    source = build_docx(rich_spec, tmp_path / "report.docx")
    report = render_document(source, tmp_path / "render")
    assert report["page_count"] >= 3
    assert report["contact_sheets"]
    assert all(not item["likely_blank"] for item in report["analysis"])


@pytest.mark.integration
def test_libreoffice_recalculates_xlsx(tmp_path):
    if preferred_office_backend() is None:
        pytest.skip("LibreOffice is not available in this runtime")
    spec = {
        "sheets": [
            {
                "name": "Model",
                "cells": [
                    {"cell": "A1", "value": 10, "style": "input"},
                    {"cell": "A2", "value": 20, "style": "input"},
                    {"cell": "A3", "formula": "=SUM(A1:A2)", "style": "formula"},
                ],
            }
        ]
    }
    source = build_xlsx(spec, tmp_path / "model.xlsx")
    output = tmp_path / "model-recalculated.xlsx"
    result = recalculate_xlsx(source, output)
    assert result["passed"] is True
    assert result["formula_count"] == 1
    assert result["missing_cached_values"] == []


@pytest.mark.integration
def test_libreoffice_renders_pptx(tmp_path):
    if preferred_office_backend() is None:
        pytest.skip("LibreOffice is not available in this runtime")
    spec = {
        "slides": [
            {"layout": "title", "title": "Render test", "subtitle": "Title slide"},
            {"layout": "bullets", "title": "Content", "bullets": ["One", "Two"]},
        ]
    }
    source = build_pptx(spec, tmp_path / "deck.pptx")
    report = render_document(source, tmp_path / "render")
    assert report["page_count"] == 2
    assert report["contact_sheets"]
