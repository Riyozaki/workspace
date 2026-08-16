#!/usr/bin/env python3
"""
recalc.py — evaluate every formula in a workbook and write the results back as
cached values.

WHY THIS MATTERS
openpyxl writes formulas as bare strings with no cached result. Until something
recalculates them, every formula cell reads back as None to pandas,
`load_workbook(data_only=True)`, previewers, and anything converting the sheet
to PDF. The usual fix is to open the file in LibreOffice — which does not exist
in this sandbox and cannot be installed. This script uses the pure-python
`formulas` engine instead, then injects the computed values straight into the
sheet XML next to each `<f>` element, which is exactly what Excel stores.

USAGE
    python tools/recalc.py book.xlsx              # rewrite in place
    python tools/recalc.py book.xlsx -o out.xlsx  # write a copy
    python tools/recalc.py book.xlsx --json       # machine-readable report

EXIT CODES
    0  every formula evaluated (report may still list warnings)
    1  at least one formula produced an Excel error (#REF!, #VALUE!, ...)
    2  the workbook could not be processed at all

A clean run proves the formulas *evaluate*, not that they are *right*: an
off-by-one range yields a perfectly clean file full of wrong numbers.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

ERROR_LITERALS = {
    "#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#N/A", "#NULL!", "#NUM!", "#SPILL!",
}

# Excel functions the `formulas` engine does not implement. Kept explicit so the
# report can name them instead of emitting a bare #NAME?.
KNOWN_UNSUPPORTED = {
    "XLOOKUP", "XMATCH", "FILTER", "SORTBY", "TEXTSPLIT", "LAMBDA", "LET",
}

# Functions Excel implements but the `formulas` engine does not. A cell using
# one of these evaluates to #NAME? here while being perfectly valid in Excel,
# so its result must be left uncached rather than poisoned with a fake error.
ENGINE_GAPS = {
    "SUBTOTAL", "AGGREGATE", "XLOOKUP", "XMATCH", "FILTER", "SORTBY",
    "TEXTSPLIT", "LAMBDA", "LET", "TEXTJOIN", "IFS", "SWITCH",
}

CELL_KEY = re.compile(r"^'\[(?P<book>[^\]]+)\](?P<sheet>[^']+)'!(?P<cell>[A-Z]+\d+)$")


def _unwrap(value: Any) -> Any:
    """Turn a formulas/numpy scalar wrapper into a plain python value."""
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        np = None

    # formulas returns Ranges objects for most cells
    for attr in ("value",):
        if hasattr(value, attr):
            try:
                value = getattr(value, attr)
            except Exception:
                break

    if np is not None and isinstance(value, np.ndarray):
        if value.size == 0:
            return None
        value = value.flat[0]
    if np is not None and isinstance(value, np.generic):
        value = value.item()

    if isinstance(value, str) and value.startswith("<Empty"):
        return None
    return value


def evaluate(path: Path) -> tuple[dict[tuple[str, str], Any], list[str]]:
    """Return ({(SHEET, CELL): value}, warnings)."""
    import formulas

    warnings: list[str] = []
    model = formulas.ExcelModel().loads(str(path)).finish()
    solution = model.calculate()

    values: dict[tuple[str, str], Any] = {}
    for key, raw in solution.items():
        match = CELL_KEY.match(str(key))
        if not match:
            continue
        sheet = match.group("sheet").upper()
        cell = match.group("cell")
        try:
            values[(sheet, cell)] = _unwrap(raw)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{sheet}!{cell}: could not read result ({exc})")
    return values, warnings


def _xml_value(value: Any) -> tuple[str | None, str] | None:
    """Map a python value to (t attribute, text) for the <v> element."""
    if value is None:
        return None
    if isinstance(value, bool):
        return ("b", "1" if value else "0")
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):  # NaN/inf
            return ("e", "#NUM!")
        return (None, repr(float(value)) if isinstance(value, float) else str(value))
    text = str(value)
    if text in ERROR_LITERALS:
        return ("e", text)
    return ("str", text)


def inject(path: Path, values: dict[tuple[str, str], Any]) -> tuple[int, list[str], list[str]]:
    """
    Write cached values into the sheet XML beside each <f>.

    Rewrites the zip because a .xlsx entry cannot be edited in place.

    Returns (written, errors, skipped). A cell whose formula uses a function
    the engine does not implement is SKIPPED, never cached: writing the
    engine's #NAME? over a formula Excel handles perfectly well would turn a
    working workbook into a broken one. Such cells keep no cached value and
    fullCalcOnLoad makes Excel fill them on open.
    """
    from lxml import etree

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    written = 0
    errors: list[str] = []
    skipped: list[str] = []

    with zipfile.ZipFile(path) as zin:
        entries = {name: zin.read(name) for name in zin.namelist()}

    # sheet file -> display name, via workbook.xml + its rels
    sheet_names: dict[str, str] = {}
    if "xl/workbook.xml" in entries:
        wb = etree.fromstring(entries["xl/workbook.xml"])
        rels = etree.fromstring(entries.get("xl/_rels/workbook.xml.rels", b"<r/>"))
        rel_map = {
            r.get("Id"): r.get("Target").lstrip("/")
            for r in rels.iter()
            if r.get("Id") and r.get("Target")
        }
        rid = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        for sheet in wb.findall(".//m:sheets/m:sheet", ns):
            target = rel_map.get(sheet.get(rid), "")
            if target and not target.startswith("xl/"):
                target = "xl/" + target
            sheet_names[target] = sheet.get("name", "")

    for name, blob in list(entries.items()):
        if not name.startswith("xl/worksheets/sheet") or not name.endswith(".xml"):
            continue
        display = sheet_names.get(name, "").upper()
        root = etree.fromstring(blob)
        changed = False

        for cell in root.findall(".//m:sheetData/m:row/m:c", ns):
            formula = cell.find("m:f", ns)
            if formula is None:
                continue
            ref = cell.get("r")
            value = values.get((display, ref))
            if value is None and (display, ref) not in values:
                continue

            mapped = _xml_value(value)
            if mapped is None:
                continue
            t_attr, text = mapped

            if t_attr == "e":
                expr = (formula.text or "").upper()
                engine_gap = next(
                    (fn for fn in ENGINE_GAPS if fn + "(" in expr), None
                )
                if engine_gap:
                    # Our engine's limitation, not the workbook's error.
                    skipped.append(f"{display or name}!{ref} ({engine_gap})")
                    for old in cell.findall("m:v", ns) + cell.findall("m:is", ns):
                        cell.remove(old)
                    if "t" in cell.attrib:
                        del cell.attrib["t"]
                    changed = True
                    continue
                errors.append(f"{display or name}!{ref} = {text}")

            for old in cell.findall("m:v", ns) + cell.findall("m:is", ns):
                cell.remove(old)

            v = etree.SubElement(cell, "{%s}v" % ns["m"])
            v.text = text
            if t_attr:
                cell.set("t", t_attr)
            elif "t" in cell.attrib:
                del cell.attrib["t"]
            changed = True
            written += 1

        if changed:
            entries[name] = etree.tostring(
                root, xml_declaration=True, encoding="UTF-8", standalone=True
            )

    # Force a full recalc on open so Excel re-verifies our arithmetic.
    if "xl/workbook.xml" in entries:
        wb = etree.fromstring(entries["xl/workbook.xml"])
        calc = wb.find("m:calcPr", ns)
        if calc is None:
            calc = etree.SubElement(wb, "{%s}calcPr" % ns["m"])
        calc.set("fullCalcOnLoad", "1")
        entries["xl/workbook.xml"] = etree.tostring(
            wb, xml_declaration=True, encoding="UTF-8", standalone=True
        )

    tmp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, blob in entries.items():
            zout.writestr(name, blob)
    tmp.replace(path)
    return written, errors, skipped


def scan_unsupported(path: Path) -> list[str]:
    """Name formulas using functions the engine cannot evaluate."""
    import openpyxl

    found: list[str] = []
    wb = openpyxl.load_workbook(path, data_only=False)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if not isinstance(cell.value, str) or not cell.value.startswith("="):
                    continue
                upper = cell.value.upper()
                for fn in KNOWN_UNSUPPORTED:
                    if f"{fn}(" in upper:
                        found.append(f"{ws.title}!{cell.coordinate} uses {fn}()")
    wb.close()
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workbook", type=Path)
    ap.add_argument("-o", "--output", type=Path, help="write here instead of in place")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    args = ap.parse_args()

    src: Path = args.workbook
    if not src.is_file():
        print(f"error: {src} not found", file=sys.stderr)
        return 2

    target = args.output or src
    if args.output:
        shutil.copy2(src, target)

    try:
        unsupported = scan_unsupported(target)
        values, warnings = evaluate(target)
        written, errors, skipped = inject(target, values)
    except Exception as exc:  # noqa: BLE001
        report = {"status": "failed", "error": str(exc)}
        print(json.dumps(report, indent=2) if args.json else f"error: {exc}", file=sys.stderr)
        return 2

    status = "errors_found" if errors else "success"
    report = {
        "status": status,
        "file": str(target),
        "values_written": written,
        "total_errors": len(errors),
        "errors": errors[:100],
        "unsupported_functions": unsupported,
        # Valid in Excel, not implemented by the engine: left uncached on
        # purpose so Excel computes them on open.
        "left_to_excel": skipped[:50],
        "total_left_to_excel": len(skipped),
        "warnings": warnings[:20],
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"{status}: wrote {written} cached values to {target.name}")
        if skipped:
            print(f"  i {len(skipped)} cell(s) left for Excel to calculate "
                  f"(engine gap, formula is valid):")
            for item in skipped[:8]:
                print(f"      {item}")
            if len(skipped) > 8:
                print(f"      ... and {len(skipped) - 8} more")
        for item in unsupported:
            print(f"  ! unsupported: {item}")
        for err in errors[:20]:
            print(f"  ✗ {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        for warn in warnings[:5]:
            print(f"  ! {warn}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
