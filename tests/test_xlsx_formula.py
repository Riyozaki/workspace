from __future__ import annotations

from document_system.xlsx_build import build_xlsx
from document_system.xlsx_formula import build_formula_graph, lint_formulas, trace_formula


def test_dependency_graph_trace_and_cycles(tmp_path):
    workbook = build_xlsx(
        {
            "sheets": [
                {
                    "name": "Model",
                    "cells": [
                        {"cell": "A1", "value": 10, "style": "input"},
                        {"cell": "B1", "formula": "=A1*2", "style": "formula"},
                        {"cell": "C1", "formula": "=B1+1", "style": "formula"},
                        {"cell": "D1", "formula": "=E1+1", "style": "formula"},
                        {"cell": "E1", "formula": "=D1+1", "style": "formula"},
                    ],
                }
            ]
        },
        tmp_path / "model.xlsx",
    )
    graph = build_formula_graph(workbook)
    assert graph["dependencies"]["Model!C1"] == ["Model!B1"]
    assert graph["cycles"]
    trace = trace_formula(workbook, "Model!C1")
    assert [node["cell"] for node in trace["nodes"]] == ["Model!C1", "Model!B1", "Model!A1"]
    assert trace["nodes"][1]["citation"] == "[Model!B1]"


def test_libreoffice_formula_compatibility_lint(tmp_path):
    workbook = build_xlsx(
        {
            "sheets": [
                {
                    "name": "Model",
                    "cells": [
                        {"cell": "A1", "value": "a"},
                        {"cell": "B1", "value": 1},
                        {"cell": "C1", "formula": '=XLOOKUP(A1,A:A,B:B,"missing")'},
                        {"cell": "D1", "formula": '=TEXTJOIN(",",TRUE,A1:A2)'},
                        {"cell": "E1", "formula": "=OFFSET(B1,0,0)"},
                    ],
                }
            ]
        },
        tmp_path / "compatibility.xlsx",
    )
    report = lint_formulas(workbook, libreoffice_compatible=True)
    by_code = {item["code"]: item for item in report["issues"]}
    assert by_code["unsupported-linear-runtime-function"]["severity"] == "error"
    assert by_code["xlfn-prefix-required"]["severity"] == "error"
    assert by_code["volatile-function"]["severity"] == "warning"
