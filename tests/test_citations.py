from __future__ import annotations

from document_system.citations import build_citation_index, locate_text
from document_system.docx_build import build_docx
from document_system.lineage import verify_lineage
from document_system.pdf_build import build_pdf
from document_system.pptx_build import build_pptx
from document_system.xlsx_build import build_xlsx


def test_format_native_citations(tmp_path):
    docx = build_docx(
        {
            "content": [
                {"type": "heading", "level": 1, "text": "Revenue"},
                {"type": "paragraph", "text": "Revenue increased to 42."},
            ]
        },
        tmp_path / "memo.docx",
    )
    xlsx = build_xlsx(
        {"sheets": [{"name": "Summary", "cells": [{"cell": "B5", "value": "Revenue 42"}]}]},
        tmp_path / "model.xlsx",
    )
    pptx = build_pptx(
        {"slides": [{"layout": "bullets", "title": "Revenue", "bullets": ["Revenue 42"]}]},
        tmp_path / "deck.pptx",
    )
    pdf = build_pdf(
        {"content": [{"type": "paragraph", "text": "Revenue 42"}]},
        tmp_path / "report.pdf",
    )

    assert locate_text(docx, "increased")["hits"][0]["citation"].startswith("[DOCX:p")
    assert locate_text(xlsx, "Revenue")["hits"][0]["citation"] == "[XLSX:Summary!B5]"
    assert locate_text(pptx, "Revenue 42")["hits"][0]["citation"].startswith("[PPTX:s1:shape")
    assert locate_text(pdf, "Revenue 42")["hits"][0]["citation"].startswith("[PDF:p1:l")

    index = build_citation_index(docx)
    paragraph = next(entry for entry in index["entries"] if "increased" in entry["text"])
    assert paragraph["location"]["section"] == "Revenue"

    lineage = verify_lineage(
        {
            "claims": [
                {
                    "id": "revenue",
                    "value": 42,
                    "sources": [{"path": str(xlsx), "query": "Revenue 42"}],
                    "targets": [
                        {"path": str(docx), "query": "Revenue increased to 42"},
                        {"path": str(pptx), "query": "Revenue 42"},
                        {"path": str(pdf), "query": "Revenue 42"},
                    ],
                }
            ]
        }
    )
    assert lineage["passed"] is True
    assert all(
        item["citations"]
        for item in lineage["claims"][0]["sources"] + lineage["claims"][0]["targets"]
    )
