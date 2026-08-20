from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from .errors import DocumentSystemError
from .office_runtime import convert_with_office
from .security import detect_format
from .xlsx_extract import extract_xlsx


class RecalculationError(DocumentSystemError):
    pass


def recalculate_xlsx(
    input_path: str | Path,
    output_path: str | Path,
    *,
    timeout: int = 240,
    force_external_links: bool = False,
) -> dict[str, Any]:
    source = Path(input_path).resolve()
    destination = Path(output_path).resolve()
    if detect_format(source) != "xlsx":
        raise RecalculationError(f"Expected XLSX input: {source}")
    if source.suffix.lower() == ".xlsm":
        raise RecalculationError("Macro-enabled workbooks are not recalculated through LibreOffice because VBA fidelity is not guaranteed")
    before = extract_xlsx(source, include_cells=False)
    external_formula_refs = [
        item
        for sheet in before["sheets"]
        for item in sheet["formulas"]
        if "[" in str(item["formula"]) and "]" in str(item["formula"])
    ]
    if not force_external_links and (before["external_links"] or external_formula_refs):
        raise RecalculationError(
            "Workbook contains external links. Recalculation can destroy links/cached values; "
            "use force_external_links only after preserving their values."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="documentctl-recalc-") as tmp:
        result = convert_with_office(
            source,
            tmp,
            "xlsx",
            filter_name="Calc MS Excel 2007 XML",
            timeout=timeout,
        )
        produced = Path(result["output"])
        shutil.copy2(produced, destination)
    inspection = extract_xlsx(destination, include_cells=False)
    errors = inspection["formula_errors"]
    return {
        "input": str(source),
        "output": str(destination),
        "conversion": result,
        "formula_count": inspection["totals"].get("formulas", 0),
        "formula_errors": errors,
        "missing_cached_values": inspection["missing_cached_values"],
        "passed": not errors,
    }
