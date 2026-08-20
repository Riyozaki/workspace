from __future__ import annotations

import posixpath
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import UnsupportedDocumentError
from .security import ArchivePolicy, detect_format, inspect_zip, secure_xml_from_bytes
from .util import sha256_file

CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_DOCUMENT_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
STRICT_OFFICE_DOCUMENT_REL = "http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument"


def issue(severity: str, code: str, message: str, part: str | None = None) -> dict[str, str]:
    value = {"severity": severity, "code": code, "message": message}
    if part:
        value["part"] = part
    return value


def relationship_owner(rels_part: str) -> str:
    pure = PurePosixPath(rels_part)
    if rels_part == "_rels/.rels":
        return ""
    if pure.parent.name != "_rels" or not pure.name.endswith(".rels"):
        raise ValueError(f"Not a relationship part: {rels_part}")
    owner_name = pure.name[: -len(".rels")]
    return str(pure.parent.parent / owner_name)


def resolve_relationship_target(rels_part: str, target: str) -> str:
    if target.startswith("/"):
        resolved = posixpath.normpath(target.lstrip("/"))
    else:
        owner = relationship_owner(rels_part)
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(owner), target))
    if resolved == ".." or resolved.startswith("../") or resolved.startswith("/"):
        raise ValueError(f"Relationship target escapes package: {target}")
    return resolved


def _content_type_for(
    part: str, defaults: dict[str, str], overrides: dict[str, str]
) -> str | None:
    key = "/" + part
    if key in overrides:
        return overrides[key]
    extension = PurePosixPath(part).suffix.lower().lstrip(".")
    return defaults.get(extension)


def inspect_ooxml(path: str | Path, policy: ArchivePolicy | None = None) -> dict[str, Any]:
    source = Path(path)
    fmt = detect_format(source)
    if fmt not in {"docx", "xlsx", "pptx"}:
        raise UnsupportedDocumentError(f"Expected OOXML package, detected {fmt}: {source}")

    archive_report = inspect_zip(source, policy=policy)
    issues: list[dict[str, str]] = []
    xml_parts = 0
    rel_count = 0
    external_relationships: list[dict[str, str]] = []
    macros: list[str] = []
    embedded_objects: list[str] = []
    media: list[str] = []
    main_part: str | None = None

    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        required = {"[Content_Types].xml", "_rels/.rels"}
        required.add({"docx": "word/document.xml", "xlsx": "xl/workbook.xml", "pptx": "ppt/presentation.xml"}[fmt])
        for name in sorted(required - names):
            issues.append(issue("error", "missing-required-part", f"Required package part is missing: {name}", name))

        defaults: dict[str, str] = {}
        overrides: dict[str, str] = {}
        if "[Content_Types].xml" in names:
            root = secure_xml_from_bytes(archive.read("[Content_Types].xml"), part="[Content_Types].xml")
            for node in root.findall(f"{{{CONTENT_TYPES_NS}}}Default"):
                ext = (node.get("Extension") or "").lower()
                content_type = node.get("ContentType") or ""
                if ext in defaults:
                    issues.append(issue("error", "duplicate-content-default", f"Duplicate Default for .{ext}", "[Content_Types].xml"))
                defaults[ext] = content_type
            for node in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
                part_name = node.get("PartName") or ""
                content_type = node.get("ContentType") or ""
                if part_name in overrides:
                    issues.append(issue("error", "duplicate-content-override", f"Duplicate Override for {part_name}", "[Content_Types].xml"))
                overrides[part_name] = content_type
                normalized = part_name.lstrip("/")
                if normalized not in names:
                    issues.append(issue("error", "missing-overridden-part", f"Content type override points to missing part: {part_name}", "[Content_Types].xml"))

        for name in sorted(names):
            lower = name.lower()
            if lower.endswith("vbaproject.bin") or lower.endswith("vbaProject.bin".lower()):
                macros.append(name)
            if "/embeddings/" in lower or lower.endswith(".ole"):
                embedded_objects.append(name)
            if any(segment in lower for segment in ("/media/", "word/media/", "ppt/media/", "xl/media/")) and not name.endswith("/"):
                media.append(name)
            if name.endswith("/") or name in {"[Content_Types].xml"}:
                continue
            if _content_type_for(name, defaults, overrides) is None and not name.endswith(".rels"):
                issues.append(issue("warning", "missing-content-type", f"No content type resolves for part: {name}", name))

            if name.endswith((".xml", ".rels")):
                xml_parts += 1
                try:
                    root = secure_xml_from_bytes(archive.read(name), part=name)
                except Exception as exc:
                    issues.append(issue("error", "malformed-xml", str(exc), name))
                    continue

                if name.endswith(".rels"):
                    seen_ids: set[str] = set()
                    for rel in root.findall(f"{{{REL_NS}}}Relationship"):
                        rel_count += 1
                        rel_id = rel.get("Id") or ""
                        target = rel.get("Target") or ""
                        rel_type = rel.get("Type") or ""
                        mode = rel.get("TargetMode", "Internal")
                        if not rel_id or rel_id in seen_ids:
                            issues.append(issue("error", "duplicate-or-empty-rel-id", f"Duplicate or empty relationship Id: {rel_id!r}", name))
                        seen_ids.add(rel_id)
                        if mode.lower() == "external":
                            external_relationships.append(
                                {"part": name, "id": rel_id, "type": rel_type, "target": target}
                            )
                            continue
                        try:
                            resolved = resolve_relationship_target(name, target)
                        except ValueError as exc:
                            issues.append(issue("error", "unsafe-relationship-target", str(exc), name))
                            continue
                        if resolved not in names:
                            issues.append(issue("error", "broken-relationship", f"{rel_id} points to missing part {resolved}", name))
                        if name == "_rels/.rels" and rel_type in {OFFICE_DOCUMENT_REL, STRICT_OFFICE_DOCUMENT_REL}:
                            main_part = resolved

        # XML parts reference relationships by r:id/r:embed/r:link. Verify those IDs exist
        # in the relationship part belonging to the same owner.
        for xml_name in sorted(
            name for name in names if name.endswith(".xml") and name != "[Content_Types].xml"
        ):
            try:
                root = secure_xml_from_bytes(archive.read(xml_name), part=xml_name)
            except Exception:
                continue
            relationship_attribute_namespaces = {
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                "http://purl.oclc.org/ooxml/officeDocument/relationships",
            }
            referenced_ids = {
                value
                for node in root.iter()
                for attribute, value in node.attrib.items()
                if attribute.startswith("{")
                and attribute[1:].split("}", 1)[0] in relationship_attribute_namespaces
                and value
            }
            if not referenced_ids:
                continue
            pure = PurePosixPath(xml_name)
            rels_name = str(pure.parent / "_rels" / f"{pure.name}.rels")
            if rels_name not in names:
                issues.append(
                    issue(
                        "error",
                        "missing-relationship-part",
                        f"{xml_name} references relationship IDs but {rels_name} is missing",
                        xml_name,
                    )
                )
                continue
            rels_root = secure_xml_from_bytes(archive.read(rels_name), part=rels_name)
            declared_ids = {
                node.get("Id")
                for node in rels_root.findall(f"{{{REL_NS}}}Relationship")
                if node.get("Id")
            }
            for missing_id in sorted(referenced_ids - declared_ids):
                issues.append(
                    issue(
                        "error",
                        "undeclared-relationship-id",
                        f"{xml_name} references missing relationship {missing_id}",
                        xml_name,
                    )
                )

        for name in macros:
            issues.append(issue("warning", "macro-present", f"Package contains executable macro content: {name}", name))
        for name in embedded_objects:
            # Native PowerPoint charts store their editable datasheet as an embedded XLSX.
            # This is expected, non-executable chart data rather than an arbitrary OLE payload.
            if fmt == "pptx" and name.lower().endswith(".xlsx"):
                continue
            issues.append(issue("warning", "embedded-object-present", f"Package contains an embedded object: {name}", name))
        for relationship in external_relationships:
            relationship_type = relationship["type"].rsplit("/", 1)[-1]
            if relationship_type != "hyperlink":
                issues.append(
                    issue(
                        "warning",
                        "external-resource-relationship",
                        f"External {relationship_type} relationship targets {relationship['target']}",
                        relationship["part"],
                    )
                )

        expected_main = {"docx": "word/document.xml", "xlsx": "xl/workbook.xml", "pptx": "ppt/presentation.xml"}[fmt]
        if main_part is None:
            issues.append(issue("error", "missing-office-document-rel", "Root relationships do not identify an officeDocument part", "_rels/.rels"))
        elif main_part != expected_main:
            issues.append(issue("warning", "unusual-main-part", f"Root relationship identifies {main_part}; expected {expected_main}", "_rels/.rels"))

        # IDs for Word drawing objects must not collide inside one XML part.
        if fmt == "docx":
            ns = {"wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"}
            for name in sorted(n for n in names if n.startswith("word/") and n.endswith(".xml")):
                try:
                    root = secure_xml_from_bytes(archive.read(name), part=name)
                except Exception:
                    continue
                ids = [node.get("id") for node in root.xpath(".//wp:docPr", namespaces=ns) if node.get("id")]
                duplicates = [value for value, count in Counter(ids).items() if count > 1]
                for value in duplicates:
                    issues.append(issue("error", "duplicate-drawing-id", f"Drawing object id {value} is duplicated", name))

    counts = Counter(item["severity"] for item in issues)
    return {
        "path": str(source),
        "sha256": sha256_file(source),
        "format": fmt,
        "archive": archive_report,
        "package": {
            "xml_parts": xml_parts,
            "relationships": rel_count,
            "main_part": main_part,
            "media_parts": len(media),
            "macro_parts": macros,
            "embedded_objects": embedded_objects,
            "external_relationships": external_relationships,
        },
        "issues": issues,
        "summary": {
            "errors": counts["error"],
            "warnings": counts["warning"],
            "info": counts["info"],
        },
    }
