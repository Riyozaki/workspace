from __future__ import annotations

import importlib.resources
import json
import posixpath
import re
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema
from lxml import etree

from .opc import CONTENT_TYPES_NS, REL_NS, resolve_relationship_target
from .pptx_edit import NS, R_NS, P, PptxEditError, PptxPackage, _slide_parts
from .security import secure_xml_from_bytes
from .util import read_json

SLIDE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
NOTES_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
SLIDE_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
ORPHAN_PREFIXES = (
    "ppt/charts/",
    "ppt/media/",
    "ppt/embeddings/",
    "ppt/notesSlides/",
    "ppt/diagrams/",
)


def validate_structure_plan(plan: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath(
        "schemas/pptx-structure.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(plan)


def _rels_name(part: str) -> str:
    pure = PurePosixPath(part)
    return str(pure.parent / "_rels" / f"{pure.name}.rels")


def _next_rid(relationships: etree._Element) -> str:
    used = {node.get("Id") for node in relationships}
    number = 1
    while f"rId{number}" in used:
        number += 1
    return f"rId{number}"


def _next_slide_part(package: PptxPackage) -> str:
    numbers = [
        int(match.group(1))
        for name in package.names
        if (match := re.match(r"ppt/slides/slide(\d+)\.xml$", name))
    ]
    return f"ppt/slides/slide{max(numbers, default=0) + 1}.xml"


def _add_content_type(package: PptxPackage, part: str) -> None:
    root = package.xml("[Content_Types].xml")
    part_name = "/" + part
    if not root.xpath(
        "./ct:Override[@PartName=$part]",
        namespaces={"ct": CONTENT_TYPES_NS},
        part=part_name,
    ):
        node = etree.SubElement(root, f"{{{CONTENT_TYPES_NS}}}Override")
        node.set("PartName", part_name)
        node.set("ContentType", SLIDE_CONTENT_TYPE)
        package.write_xml("[Content_Types].xml", root)


def _remove_content_types(package: PptxPackage, removed: set[str]) -> None:
    root = package.xml("[Content_Types].xml")
    changed = False
    for node in list(root.findall(f"{{{CONTENT_TYPES_NS}}}Override")):
        if (node.get("PartName") or "").lstrip("/") in removed:
            root.remove(node)
            changed = True
    if changed:
        package.write_xml("[Content_Types].xml", root)


def _duplicate_slide(package: PptxPackage, source_number: int, after: int) -> dict[str, Any]:
    parts = _slide_parts(package)
    if source_number > len(parts) or after > len(parts):
        raise PptxEditError(
            f"Duplicate slide selection exceeds current deck length {len(parts)}"
        )
    source_part = parts[source_number - 1]
    new_part = _next_slide_part(package)
    package.write_bytes(new_part, package.entries[source_part])
    source_rels = _rels_name(source_part)
    new_rels = _rels_name(new_part)
    if source_rels in package.names:
        rels = package.xml(source_rels)
        # Notes slides contain a back-reference to their owning slide and cannot be shared.
        for node in list(rels.findall(f"{{{REL_NS}}}Relationship")):
            if node.get("Type") == NOTES_REL:
                rels.remove(node)
        if len(rels):
            package.write_xml(new_rels, rels)
    _add_content_type(package, new_part)

    presentation = package.xml("ppt/presentation.xml")
    relationships = package.xml("ppt/_rels/presentation.xml.rels")
    rel_id = _next_rid(relationships)
    relation = etree.SubElement(relationships, f"{{{REL_NS}}}Relationship")
    relation.set("Id", rel_id)
    relation.set("Type", SLIDE_REL)
    relation.set("Target", posixpath.relpath(new_part, "ppt"))
    slide_ids = presentation.find("./p:sldIdLst", namespaces=NS)
    if slide_ids is None:
        raise PptxEditError("Presentation has no slide ID list")
    identifiers = [int(node.get("id", "255")) for node in slide_ids]
    new_id = max(identifiers, default=255) + 1
    node = etree.Element(P + "sldId")
    node.set("id", str(new_id))
    node.set(f"{{{R_NS}}}id", rel_id)
    slide_ids.insert(after, node)
    package.write_xml("ppt/presentation.xml", presentation)
    package.write_xml("ppt/_rels/presentation.xml.rels", relationships)
    return {
        "source_slide": source_number,
        "source_part": source_part,
        "new_slide": after + 1,
        "new_part": new_part,
        "shared_assets": True,
        "notes_copied": False,
    }


def _delete_slides(package: PptxPackage, numbers: list[int]) -> list[dict[str, Any]]:
    presentation = package.xml("ppt/presentation.xml")
    relationships = package.xml("ppt/_rels/presentation.xml.rels")
    slide_ids = presentation.find("./p:sldIdLst", namespaces=NS)
    if slide_ids is None:
        raise PptxEditError("Presentation has no slide ID list")
    if any(number > len(slide_ids) for number in numbers):
        raise PptxEditError(f"Delete selection exceeds current deck length {len(slide_ids)}")
    if len(set(numbers)) >= len(slide_ids):
        raise PptxEditError("Cannot delete every slide")
    rel_by_id = {node.get("Id"): node for node in relationships}
    removed = []
    for number in sorted(set(numbers), reverse=True):
        slide_id = slide_ids[number - 1]
        rel_id = slide_id.get(f"{{{R_NS}}}id")
        relation = rel_by_id.get(rel_id)
        if relation is None:
            raise PptxEditError(f"Slide {number} relationship {rel_id} is missing")
        part = resolve_relationship_target(
            "ppt/_rels/presentation.xml.rels", relation.get("Target") or ""
        )
        slide_ids.remove(slide_id)
        relationships.remove(relation)
        package.remove(part)
        package.remove(_rels_name(part))
        removed.append({"slide": number, "part": part})
    package.write_xml("ppt/presentation.xml", presentation)
    package.write_xml("ppt/_rels/presentation.xml.rels", relationships)
    _remove_content_types(package, {item["part"] for item in removed})
    return list(reversed(removed))


def _reorder_slides(package: PptxPackage, order: list[int]) -> list[int]:
    presentation = package.xml("ppt/presentation.xml")
    slide_ids = presentation.find("./p:sldIdLst", namespaces=NS)
    if slide_ids is None:
        raise PptxEditError("Presentation has no slide ID list")
    expected = list(range(1, len(slide_ids) + 1))
    if sorted(order) != expected:
        raise PptxEditError(f"Order must be a permutation of {expected}")
    nodes = list(slide_ids)
    for node in nodes:
        slide_ids.remove(node)
    for number in order:
        slide_ids.append(nodes[number - 1])
    package.write_xml("ppt/presentation.xml", presentation)
    return order


def _incoming_relationships(package: PptxPackage) -> dict[str, int]:
    incoming: dict[str, int] = {}
    for rels_name in [name for name in package.names if name.endswith(".rels")]:
        try:
            root = secure_xml_from_bytes(package.entries[rels_name], part=rels_name)
        except Exception:
            continue
        for relation in root.findall(f"{{{REL_NS}}}Relationship"):
            if (relation.get("TargetMode") or "").lower() == "external":
                continue
            try:
                target = resolve_relationship_target(rels_name, relation.get("Target") or "")
            except ValueError:
                continue
            incoming[target] = incoming.get(target, 0) + 1
    return incoming


def _clean_orphans(package: PptxPackage) -> list[str]:
    removed: list[str] = []
    while True:
        incoming = _incoming_relationships(package)
        candidates = [
            name
            for name in package.names
            if name.startswith(ORPHAN_PREFIXES)
            and "/_rels/" not in name
            and not name.endswith(".rels")
            and incoming.get(name, 0) == 0
        ]
        if not candidates:
            break
        for part in candidates:
            package.remove(part)
            package.remove(_rels_name(part))
            removed.append(part)
    _remove_content_types(package, set(removed))
    return sorted(removed)


def apply_pptx_structure_plan(
    input_path: str | Path,
    output_path: str | Path,
    plan: dict[str, Any],
) -> dict[str, Any]:
    validate_structure_plan(plan)
    package = PptxPackage(input_path)
    duplicated = []
    for operation in plan.get("duplicate", []):
        for _ in range(operation.get("copies", 1)):
            after = operation.get("after", operation["slide"])
            duplicated.append(_duplicate_slide(package, operation["slide"], after))
    deleted = _delete_slides(package, plan.get("delete", [])) if plan.get("delete") else []
    order = _reorder_slides(package, plan["order"]) if plan.get("order") else None
    orphaned = _clean_orphans(package) if plan.get("clean_orphans", True) else []
    package.save(output_path)
    return {
        "input": str(Path(input_path)),
        "output": str(Path(output_path)),
        "duplicated": duplicated,
        "deleted": deleted,
        "order": order,
        "orphaned_parts_removed": orphaned,
        "slide_count": len(_slide_parts(package)),
    }


def apply_pptx_structure_plan_file(
    input_path: str | Path,
    output_path: str | Path,
    plan_path: str | Path,
) -> dict[str, Any]:
    return apply_pptx_structure_plan(input_path, output_path, read_json(plan_path))
