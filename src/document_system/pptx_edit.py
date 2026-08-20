from __future__ import annotations

import copy
import hashlib
import importlib.resources
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
from lxml import etree
from PIL import Image

from .errors import DocumentSystemError, UnsupportedDocumentError
from .opc import REL_NS, resolve_relationship_target
from .security import detect_format, inspect_zip, secure_xml_from_bytes
from .util import read_json

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
P = f"{{{P_NS}}}"
A = f"{{{A_NS}}}"
NS = {"p": P_NS, "a": A_NS, "r": R_NS}
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
NOTES_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"


class PptxEditError(DocumentSystemError):
    pass


class PptxPackage:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if detect_format(self.path) != "pptx":
            raise UnsupportedDocumentError(f"Not a PPTX package: {self.path}")
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

    def xml(self, name: str) -> etree._Element:
        return secure_xml_from_bytes(self.entries[name], part=name)

    def write_bytes(self, name: str, value: bytes) -> None:
        if name not in self.entries:
            self.order.append(name)
        self.entries[name] = value

    def write_xml(self, name: str, root: etree._Element) -> None:
        self.write_bytes(
            name,
            etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True),
        )

    def remove(self, name: str) -> None:
        self.entries.pop(name, None)
        self.infos.pop(name, None)
        if name in self.order:
            self.order.remove(name)

    def save(self, output: str | Path) -> Path:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name in self.order:
                info = copy.copy(self.infos.get(name, zipfile.ZipInfo(name)))
                if name not in self.infos:
                    info.date_time = (1980, 1, 1, 0, 0, 0)
                    info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, self.entries[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
        destination.write_bytes(buffer.getvalue())
        return destination


def validate_pptx_edit_plan(plan: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath("schemas/pptx-edit-plan.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(plan)


def _slide_parts(package: PptxPackage) -> list[str]:
    presentation = package.xml("ppt/presentation.xml")
    rels_name = "ppt/_rels/presentation.xml.rels"
    relationships = package.xml(rels_name)
    targets = {
        node.get("Id"): resolve_relationship_target(rels_name, node.get("Target") or "")
        for node in relationships.findall(f"{{{REL_NS}}}Relationship")
    }
    result: list[str] = []
    for slide_id in presentation.xpath("./p:sldIdLst/p:sldId", namespaces=NS):
        rel_id = slide_id.get(f"{{{R_NS}}}id")
        if rel_id not in targets:
            raise PptxEditError(f"Presentation slide relationship is missing: {rel_id}")
        result.append(targets[rel_id])
    return result


def _notes_part(package: PptxPackage, slide_part: str) -> str | None:
    pure = Path(slide_part)
    rels_name = str(pure.parent / "_rels" / f"{pure.name}.rels")
    if rels_name not in package.names:
        return None
    relationships = package.xml(rels_name)
    for node in relationships.findall(f"{{{REL_NS}}}Relationship"):
        if node.get("Type") == NOTES_REL:
            return resolve_relationship_target(rels_name, node.get("Target") or "")
    return None


@dataclass
class TextSpan:
    run: etree._Element
    start: int
    end: int
    text: str


def _paragraph_runs(paragraph: etree._Element) -> tuple[str, list[TextSpan]]:
    spans: list[TextSpan] = []
    values: list[str] = []
    cursor = 0
    for run in paragraph.findall("./a:r", namespaces=NS):
        text_node = run.find("./a:t", namespaces=NS)
        value = text_node.text if text_node is not None and text_node.text is not None else ""
        spans.append(TextSpan(run, cursor, cursor + len(value), value))
        values.append(value)
        cursor += len(value)
    return "".join(values), spans


def _clone_run(run: etree._Element, text: str) -> etree._Element:
    clone = etree.Element(A + "r", nsmap=run.nsmap)
    properties = run.find("./a:rPr", namespaces=NS)
    if properties is not None:
        clone.append(copy.deepcopy(properties))
    node = etree.SubElement(clone, A + "t")
    if text.startswith(" ") or text.endswith(" ") or "  " in text:
        node.set(XML_SPACE, "preserve")
    node.text = text
    return clone


def _replace_range(paragraph: etree._Element, start: int, end: int, replacement: str) -> None:
    _text, spans = _paragraph_runs(paragraph)
    selected = [span for span in spans if span.end > start and span.start < end]
    if not selected:
        raise PptxEditError("Text range did not map to DrawingML runs")
    first, last = selected[0], selected[-1]
    prefix = first.text[: start - first.start]
    suffix = last.text[end - last.start :]
    parent = first.run.getparent()
    if parent is None or any(span.run.getparent() is not parent for span in selected):
        raise PptxEditError("Replacement crosses incompatible DrawingML containers")
    index = parent.index(first.run)
    for span in selected:
        parent.remove(span.run)
    nodes = []
    if prefix:
        nodes.append(_clone_run(first.run, prefix))
    if replacement:
        nodes.append(_clone_run(first.run, replacement))
    if suffix:
        nodes.append(_clone_run(last.run, suffix))
    for offset, node in enumerate(nodes):
        parent.insert(index + offset, node)


def _replace_in_part(root: etree._Element, find: str, replacement: str, replace_all: bool) -> int:
    count = 0
    for paragraph in root.xpath(".//a:p", namespaces=NS):
        text, _spans = _paragraph_runs(paragraph)
        positions: list[int] = []
        cursor = 0
        while True:
            position = text.find(find, cursor)
            if position < 0:
                break
            positions.append(position)
            cursor = position + len(find)
            if not replace_all:
                break
        for position in reversed(positions):
            _replace_range(paragraph, position, position + len(find), replacement)
            count += 1
        if positions and not replace_all:
            break
    return count


def _replace_media(package: PptxPackage, part: str, path: Path, expected_sha256: str | None) -> dict[str, Any]:
    if part not in package.names:
        raise PptxEditError(f"Media part not found: {part}")
    old = package.entries[part]
    old_hash = hashlib.sha256(old).hexdigest()
    if expected_sha256 and old_hash.lower() != expected_sha256.lower():
        raise PptxEditError(f"{part}: expected SHA-256 {expected_sha256}, found {old_hash}")
    if not path.is_file():
        raise FileNotFoundError(path)
    expected_formats = {
        ".png": {"PNG"},
        ".jpg": {"JPEG"},
        ".jpeg": {"JPEG"},
        ".gif": {"GIF"},
        ".bmp": {"BMP"},
        ".tif": {"TIFF"},
        ".tiff": {"TIFF"},
    }
    suffix = Path(part).suffix.lower()
    with Image.open(path) as image:
        actual_format = image.format
        dimensions = list(image.size)
    if suffix in expected_formats and actual_format not in expected_formats[suffix]:
        raise PptxEditError(f"Replacement for {part} must remain {suffix}; got {actual_format}")
    value = path.read_bytes()
    package.entries[part] = value
    return {
        "part": part,
        "old_sha256": old_hash,
        "new_sha256": hashlib.sha256(value).hexdigest(),
        "format": actual_format,
        "dimensions": dimensions,
    }


def _update_core_properties(package: PptxPackage, values: dict[str, str]) -> None:
    name = "docProps/core.xml"
    if name not in package.names:
        return
    root = package.xml(name)
    mapping = {
        "title": f"{{{DC_NS}}}title",
        "subject": f"{{{DC_NS}}}subject",
        "author": f"{{{DC_NS}}}creator",
        "keywords": f"{{{CP_NS}}}keywords",
        "category": f"{{{CP_NS}}}category",
        "comments": f"{{{DC_NS}}}description",
    }
    for key, value in values.items():
        tag = mapping[key]
        node = root.find(tag)
        if node is None:
            node = etree.SubElement(root, tag)
        node.text = value
    package.write_xml(name, root)


def apply_pptx_edit_plan(input_path: str | Path, output_path: str | Path, plan: dict[str, Any], *, base_dir: str | Path | None = None) -> dict[str, Any]:
    validate_pptx_edit_plan(plan)
    package = PptxPackage(input_path)
    slide_parts = _slide_parts(package)
    base = Path(base_dir or ".").resolve()
    replacements: list[dict[str, Any]] = []

    for operation in plan.get("replacements", []):
        selected_numbers = operation.get("slides") or list(range(1, len(slide_parts) + 1))
        if any(number > len(slide_parts) for number in selected_numbers):
            raise PptxEditError(f"Slide selection exceeds deck length {len(slide_parts)}")
        count = 0
        changed_roots: dict[str, etree._Element] = {}
        parts = [slide_parts[number - 1] for number in selected_numbers]
        if operation.get("include_notes"):
            parts.extend(
                notes
                for slide_part in [slide_parts[number - 1] for number in selected_numbers]
                if (notes := _notes_part(package, slide_part)) is not None
            )
        for part in parts:
            root = package.xml(part)
            part_count = _replace_in_part(root, operation["find"], operation["replace"], operation.get("all", True))
            if part_count:
                changed_roots[part] = root
                count += part_count
            if part_count and not operation.get("all", True):
                break
        expected = operation.get("expected")
        if expected is not None and count != expected:
            raise PptxEditError(f"Replacement {operation['find']!r}: expected {expected}, found {count}")
        if expected is None and count == 0:
            raise PptxEditError(f"Required replacement not found: {operation['find']!r}")
        for part, root in changed_roots.items():
            package.write_xml(part, root)
        replacements.append({"find": operation["find"], "replace": operation["replace"], "count": count})

    media = [
        _replace_media(package, item["part"], (base / item["path"]).resolve(), item.get("expected_sha256"))
        for item in plan.get("media_replacements", [])
    ]
    if plan.get("metadata"):
        _update_core_properties(package, plan["metadata"])
    package.save(output_path)
    return {
        "output": str(Path(output_path)),
        "replacements": replacements,
        "media_replacements": media,
        "metadata_updated": bool(plan.get("metadata")),
    }


def apply_pptx_edit_plan_file(input_path: str | Path, output_path: str | Path, plan_path: str | Path) -> dict[str, Any]:
    source = Path(plan_path).resolve()
    return apply_pptx_edit_plan(input_path, output_path, read_json(source), base_dir=source.parent)
