from __future__ import annotations

import copy
import importlib.resources
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import jsonschema
from lxml import etree
from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries

from .errors import DocumentSystemError, UnsupportedDocumentError
from .opc import REL_NS, resolve_relationship_target
from .security import detect_format, inspect_zip, secure_xml_from_bytes
from .util import read_json

S_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
S = f"{{{S_NS}}}"
NS = {"s": S_NS, "r": R_NS}
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
CALC_CHAIN_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/calcChain"


class XlsxEditError(DocumentSystemError):
    pass


class XlsxPackage:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if detect_format(self.path) != "xlsx":
            raise UnsupportedDocumentError(f"Not an XLSX package: {self.path}")
        inspect_zip(self.path)
        self.entries: dict[str, bytes] = {}
        self.infos: dict[str, zipfile.ZipInfo] = {}
        self.order: list[str] = []
        with zipfile.ZipFile(self.path) as archive:
            for info in archive.infolist():
                if info.filename.endswith("/"):
                    continue
                self.order.append(info.filename)
                self.infos[info.filename] = copy.copy(info)
                self.entries[info.filename] = archive.read(info.filename)

    @property
    def names(self) -> set[str]:
        return set(self.entries)

    def read(self, name: str) -> bytes:
        return self.entries[name]

    def xml(self, name: str) -> etree._Element:
        return secure_xml_from_bytes(self.read(name), part=name)

    def write_xml(self, name: str, root: etree._Element) -> None:
        self.entries[name] = etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
        if name not in self.order:
            self.order.append(name)

    def remove(self, name: str) -> None:
        self.entries.pop(name, None)
        if name in self.order:
            self.order.remove(name)

    def save(self, output: str | Path) -> Path:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name in self.order:
                data = self.entries[name]
                info = copy.copy(self.infos.get(name, zipfile.ZipInfo(name)))
                if name not in self.infos:
                    info.date_time = (1980, 1, 1, 0, 0, 0)
                    info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
        destination.write_bytes(buffer.getvalue())
        return destination


def validate_xlsx_edit_plan(plan: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath("schemas/xlsx-edit-plan.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(plan)


def _sheet_parts(package: XlsxPackage) -> dict[str, str]:
    workbook = package.xml("xl/workbook.xml")
    rels_name = "xl/_rels/workbook.xml.rels"
    relationships = package.xml(rels_name)
    relationship_targets = {
        node.get("Id"): resolve_relationship_target(rels_name, node.get("Target") or "")
        for node in relationships.findall(f"{{{REL_NS}}}Relationship")
    }
    result: dict[str, str] = {}
    for sheet in workbook.xpath("./s:sheets/s:sheet", namespaces=NS):
        name = sheet.get("name")
        rel_id = sheet.get(f"{{{R_NS}}}id")
        if not name or rel_id not in relationship_targets:
            raise XlsxEditError(f"Worksheet relationship is missing for {name!r}")
        result[name] = relationship_targets[rel_id]
    return result


def _shared_strings(package: XlsxPackage) -> list[str]:
    if "xl/sharedStrings.xml" not in package.names:
        return []
    root = package.xml("xl/sharedStrings.xml")
    return ["".join(node.itertext()) for node in root.findall("./s:si", namespaces=NS)]


def _cell_value(cell: etree._Element | None, shared: list[str]) -> Any:
    if cell is None:
        return None
    formula = cell.find("./s:f", namespaces=NS)
    if formula is not None:
        return "=" + (formula.text or "")
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        inline = cell.find("./s:is", namespaces=NS)
        return "".join(inline.itertext()) if inline is not None else ""
    value = cell.findtext("./s:v", namespaces=NS)
    if value is None:
        return None
    if cell_type == "s":
        try:
            return shared[int(value)]
        except (ValueError, IndexError):
            raise XlsxEditError(f"Invalid shared string index: {value}") from None
    if cell_type == "b":
        return value == "1"
    if cell_type in {"str", "e"}:
        return value
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except ValueError:
        return value


def _find_or_create_row(sheet_data: etree._Element, row_number: int) -> etree._Element:
    for index, row in enumerate(sheet_data.findall("./s:row", namespaces=NS)):
        current = int(row.get("r", "0"))
        if current == row_number:
            return row
        if current > row_number:
            new_row = etree.Element(S + "row")
            new_row.set("r", str(row_number))
            sheet_data.insert(index, new_row)
            return new_row
    new_row = etree.SubElement(sheet_data, S + "row")
    new_row.set("r", str(row_number))
    return new_row


def _find_or_create_cell(row: etree._Element, coordinate: str) -> etree._Element:
    target_row, target_col = coordinate_to_tuple(coordinate)
    for index, cell in enumerate(row.findall("./s:c", namespaces=NS)):
        cell_row, cell_col = coordinate_to_tuple(cell.get("r") or "A1")
        if cell_row == target_row and cell_col == target_col:
            return cell
        if cell_col > target_col:
            new_cell = etree.Element(S + "c")
            new_cell.set("r", coordinate)
            row.insert(index, new_cell)
            return new_cell
    new_cell = etree.SubElement(row, S + "c")
    new_cell.set("r", coordinate)
    return new_cell


def _assert_not_non_anchor_merge(root: etree._Element, coordinate: str) -> None:
    target_row, target_col = coordinate_to_tuple(coordinate)
    for merged in root.xpath("./s:mergeCells/s:mergeCell", namespaces=NS):
        reference = merged.get("ref") or ""
        min_col, min_row, max_col, max_row = range_boundaries(reference)
        if min_row <= target_row <= max_row and min_col <= target_col <= max_col:
            if target_row != min_row or target_col != min_col:
                raise XlsxEditError(f"Cannot update non-anchor merged cell {coordinate} in {reference}")


def _write_scalar(cell: etree._Element, value: Any) -> None:
    for child in list(cell):
        if child.tag in {S + "f", S + "v", S + "is"}:
            cell.remove(child)
    if value is None:
        cell.attrib.pop("t", None)
        return
    if isinstance(value, bool):
        cell.set("t", "b")
        etree.SubElement(cell, S + "v").text = "1" if value else "0"
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        cell.attrib.pop("t", None)
        etree.SubElement(cell, S + "v").text = str(value)
    else:
        cell.set("t", "inlineStr")
        inline = etree.SubElement(cell, S + "is")
        text = etree.SubElement(inline, S + "t")
        string = str(value)
        if string.startswith(" ") or string.endswith(" ") or "  " in string:
            text.set(XML_SPACE, "preserve")
        text.text = string


def _write_formula(cell: etree._Element, formula: str, cached_value: Any = None) -> None:
    if not formula.startswith("="):
        raise XlsxEditError("Formula must start with '='")
    old_formula = cell.find("./s:f", namespaces=NS)
    if old_formula is not None and old_formula.get("t") not in {None, "normal"}:
        raise XlsxEditError(
            f"Cannot safely replace {old_formula.get('t')} formula in {cell.get('r')}; update the complete formula group"
        )
    for child in list(cell):
        if child.tag in {S + "f", S + "v", S + "is"}:
            cell.remove(child)
    cell.attrib.pop("t", None)
    etree.SubElement(cell, S + "f").text = formula[1:]
    if cached_value is not None:
        if isinstance(cached_value, str):
            cell.set("t", "str")
        etree.SubElement(cell, S + "v").text = str(cached_value)


def _remove_calc_chain(package: XlsxPackage) -> bool:
    if "xl/calcChain.xml" not in package.names:
        return False
    package.remove("xl/calcChain.xml")
    rels_name = "xl/_rels/workbook.xml.rels"
    rels = package.xml(rels_name)
    for node in list(rels.findall(f"{{{REL_NS}}}Relationship")):
        if node.get("Type") == CALC_CHAIN_REL:
            rels.remove(node)
    package.write_xml(rels_name, rels)
    content_types = package.xml("[Content_Types].xml")
    for node in list(content_types.findall(f"{{{CT_NS}}}Override")):
        if node.get("PartName") == "/xl/calcChain.xml":
            content_types.remove(node)
    package.write_xml("[Content_Types].xml", content_types)
    return True


def _force_recalculation(package: XlsxPackage) -> None:
    workbook = package.xml("xl/workbook.xml")
    calc = workbook.find("./s:calcPr", namespaces=NS)
    if calc is None:
        calc = etree.Element(S + "calcPr")
        later_tags = {
            S + "oleSize",
            S + "customWorkbookViews",
            S + "pivotCaches",
            S + "smartTagPr",
            S + "smartTagTypes",
            S + "webPublishing",
            S + "fileRecoveryPr",
            S + "webPublishObjects",
            S + "extLst",
        }
        insertion = next((index for index, child in enumerate(workbook) if child.tag in later_tags), len(workbook))
        workbook.insert(insertion, calc)
    calc.set("calcMode", "auto")
    calc.set("fullCalcOnLoad", "1")
    calc.set("forceFullCalc", "1")
    package.write_xml("xl/workbook.xml", workbook)


def _update_core_properties(package: XlsxPackage, values: dict[str, str]) -> None:
    name = "docProps/core.xml"
    if name not in package.names:
        return
    root = package.xml(name)
    mapping = {
        "title": f"{{{DC_NS}}}title",
        "subject": f"{{{DC_NS}}}subject",
        "creator": f"{{{DC_NS}}}creator",
        "keywords": f"{{{CP_NS}}}keywords",
        "category": f"{{{CP_NS}}}category",
        "description": f"{{{DC_NS}}}description",
    }
    for key, value in values.items():
        tag = mapping[key]
        node = root.find(tag)
        if node is None:
            node = etree.SubElement(root, tag)
        node.text = value
    package.write_xml(name, root)


def apply_xlsx_edit_plan(input_path: str | Path, output_path: str | Path, plan: dict[str, Any]) -> dict[str, Any]:
    validate_xlsx_edit_plan(plan)
    package = XlsxPackage(input_path)
    sheet_parts = _sheet_parts(package)
    shared = _shared_strings(package)
    roots: dict[str, etree._Element] = {}
    report_updates: list[dict[str, Any]] = []
    formula_changed = False

    for update in plan["updates"]:
        sheet = update["sheet"]
        coordinate = update["cell"].upper()
        if sheet not in sheet_parts:
            raise XlsxEditError(f"Worksheet not found: {sheet}")
        part = sheet_parts[sheet]
        root = roots.setdefault(part, package.xml(part))
        _assert_not_non_anchor_merge(root, coordinate)
        existing = root.xpath(f"./s:sheetData/s:row/s:c[@r='{coordinate}']", namespaces=NS)
        old_value = _cell_value(existing[0] if existing else None, shared)
        if "expected" in update and old_value != update["expected"]:
            raise XlsxEditError(
                f"{sheet}!{coordinate}: expected {update['expected']!r}, found {old_value!r}"
            )
        sheet_data = root.find("./s:sheetData", namespaces=NS)
        if sheet_data is None:
            sheet_data = etree.SubElement(root, S + "sheetData")
        row_number, _ = coordinate_to_tuple(coordinate)
        row = _find_or_create_row(sheet_data, row_number)
        cell = _find_or_create_cell(row, coordinate)
        if "formula" in update:
            _write_formula(cell, update["formula"], update.get("cached_value"))
            new_value = update["formula"]
            formula_changed = True
        else:
            _write_scalar(cell, update.get("value"))
            new_value = update.get("value")
        report_updates.append(
            {"sheet": sheet, "cell": coordinate, "old": old_value, "new": new_value}
        )

    for part, root in roots.items():
        package.write_xml(part, root)
    calc_chain_removed = False
    if formula_changed:
        calc_chain_removed = _remove_calc_chain(package)
        _force_recalculation(package)
    if plan.get("metadata"):
        _update_core_properties(package, plan["metadata"])
    package.save(output_path)
    return {
        "output": str(Path(output_path)),
        "updates": report_updates,
        "formula_changed": formula_changed,
        "calc_chain_removed": calc_chain_removed,
        "metadata_updated": bool(plan.get("metadata")),
    }


def apply_xlsx_edit_plan_file(input_path: str | Path, output_path: str | Path, plan_path: str | Path) -> dict[str, Any]:
    return apply_xlsx_edit_plan(input_path, output_path, read_json(plan_path))
