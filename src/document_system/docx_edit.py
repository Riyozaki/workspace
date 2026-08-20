from __future__ import annotations

import copy
import datetime as dt
import importlib.resources
import io
import json
import re
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
from lxml import etree

from .errors import DocumentSystemError, UnsupportedDocumentError
from .security import detect_format, inspect_zip, secure_xml_from_bytes
from .util import read_json

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
NS = {"w": W_NS, "r": R_NS}
W = f"{{{W_NS}}}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
COMMENTS_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
COMMENTS_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"


class EditError(DocumentSystemError):
    pass


class Package:
    """OOXML package editor that preserves untouched ZIP members byte-for-byte."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if detect_format(self.path) != "docx":
            raise UnsupportedDocumentError(f"Not a DOCX package: {self.path}")
        inspect_zip(self.path)
        self._entries: dict[str, bytes] = {}
        self._infos: dict[str, zipfile.ZipInfo] = {}
        self._order: list[str] = []
        with zipfile.ZipFile(self.path) as archive:
            for info in archive.infolist():
                if info.filename.endswith("/"):
                    continue
                self._order.append(info.filename)
                self._infos[info.filename] = copy.copy(info)
                self._entries[info.filename] = archive.read(info.filename)

    @property
    def names(self) -> set[str]:
        return set(self._entries)

    def read(self, name: str) -> bytes:
        return self._entries[name]

    def write(self, name: str, value: bytes) -> None:
        if name not in self._entries:
            self._order.append(name)
        self._entries[name] = value

    def xml(self, name: str) -> etree._Element:
        return secure_xml_from_bytes(self.read(name), part=name)

    def write_xml(self, name: str, root: etree._Element) -> None:
        self.write(
            name,
            etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True),
        )

    def save(self, output: str | Path) -> Path:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name in self._order:
                data = self._entries[name]
                if name in self._infos:
                    info = copy.copy(self._infos[name])
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
                else:
                    info = zipfile.ZipInfo(name)
                    info.date_time = (1980, 1, 1, 0, 0, 0)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
        destination.write_bytes(buffer.getvalue())
        return destination


@dataclass
class RunSpan:
    run: etree._Element
    start: int
    end: int
    text: str


def _run_plain_text(run: etree._Element) -> str | None:
    values: list[str] = []
    for child in run:
        if child.tag == W + "rPr":
            continue
        if child.tag == W + "t":
            values.append(child.text or "")
        elif child.tag == W + "tab":
            values.append("\t")
        elif child.tag in {W + "br", W + "cr"}:
            values.append("\n")
        elif child.tag in {W + "lastRenderedPageBreak", W + "proofErr"}:
            continue
        else:
            # Drawing, field, note reference, or another complex run cannot be split safely.
            return None
    return "".join(values)


def _inside_revision(run: etree._Element) -> bool:
    parent = run.getparent()
    while parent is not None:
        if parent.tag in {W + "ins", W + "del", W + "moveFrom", W + "moveTo"}:
            return True
        parent = parent.getparent()
    return False


def _paragraph_runs(paragraph: etree._Element) -> tuple[str, list[RunSpan]]:
    spans: list[RunSpan] = []
    text_parts: list[str] = []
    cursor = 0
    for run in paragraph.xpath(".//w:r", namespaces=NS):
        if _inside_revision(run):
            continue
        value = _run_plain_text(run)
        if value is None:
            # A replacement may still happen elsewhere in the paragraph; complex runs form a hard boundary.
            value = "\uFFF9"
        start = cursor
        cursor += len(value)
        spans.append(RunSpan(run=run, start=start, end=cursor, text=value))
        text_parts.append(value)
    return "".join(text_parts), spans


def _clone_run(run: etree._Element, text: str, *, deleted: bool = False) -> etree._Element:
    cloned = etree.Element(W + "r", nsmap=run.nsmap)
    properties = run.find("./w:rPr", namespaces=NS)
    if properties is not None:
        cloned.append(copy.deepcopy(properties))
    node = etree.SubElement(cloned, W + ("delText" if deleted else "t"))
    if text.startswith(" ") or text.endswith(" ") or "  " in text:
        node.set(XML_SPACE, "preserve")
    node.text = text
    return cloned


def _selected_spans(spans: list[RunSpan], start: int, end: int) -> list[RunSpan]:
    return [span for span in spans if span.end > start and span.start < end]


def _replace_range(
    paragraph: etree._Element,
    start: int,
    end: int,
    replacement: str,
    *,
    tracked: bool,
    author: str,
    date: str,
    revision_id: int,
) -> None:
    _text, spans = _paragraph_runs(paragraph)
    selected = _selected_spans(spans, start, end)
    if not selected:
        raise EditError("Replacement range did not map to editable Word runs")
    if any("\uFFF9" in span.text for span in selected):
        raise EditError("Replacement crosses a drawing, field, or other complex run")
    parent = selected[0].run.getparent()
    if parent is None or any(span.run.getparent() is not parent for span in selected):
        raise EditError("Replacement crosses hyperlink or nested container boundaries")

    first, last = selected[0], selected[-1]
    first_offset = start - first.start
    last_offset = end - last.start
    prefix = first.text[:first_offset]
    suffix = last.text[last_offset:]
    deleted_chunks: list[tuple[etree._Element, str]] = []
    for span in selected:
        local_start = max(start, span.start) - span.start
        local_end = min(end, span.end) - span.start
        chunk = span.text[local_start:local_end]
        if chunk:
            deleted_chunks.append((span.run, chunk))

    insertion_index = parent.index(first.run)
    for span in selected:
        parent.remove(span.run)

    nodes: list[etree._Element] = []
    if prefix:
        nodes.append(_clone_run(first.run, prefix))
    if tracked:
        deletion = etree.Element(W + "del")
        deletion.set(W + "id", str(revision_id))
        deletion.set(W + "author", author)
        deletion.set(W + "date", date)
        for source_run, chunk in deleted_chunks:
            deletion.append(_clone_run(source_run, chunk, deleted=True))
        insertion = etree.Element(W + "ins")
        insertion.set(W + "id", str(revision_id + 1))
        insertion.set(W + "author", author)
        insertion.set(W + "date", date)
        if replacement:
            insertion.append(_clone_run(first.run, replacement))
        nodes.append(deletion)
        if replacement:
            nodes.append(insertion)
    elif replacement:
        nodes.append(_clone_run(first.run, replacement))
    if suffix:
        nodes.append(_clone_run(last.run, suffix))
    for offset, node in enumerate(nodes):
        parent.insert(insertion_index + offset, node)


def _story_parts(package: Package, scopes: Iterable[str] | None = None) -> list[str]:
    scopes = set(scopes or ("document", "headers", "footers"))
    names: list[str] = []
    if "document" in scopes:
        names.append("word/document.xml")
    if "headers" in scopes:
        names.extend(sorted(name for name in package.names if re.match(r"word/header\d+\.xml$", name)))
    if "footers" in scopes:
        names.extend(sorted(name for name in package.names if re.match(r"word/footer\d+\.xml$", name)))
    return names


def _max_revision_id(package: Package) -> int:
    maximum = -1
    for name in _story_parts(package):
        root = package.xml(name)
        for node in root.xpath(".//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo", namespaces=NS):
            value = node.get(W + "id")
            if value and value.isdigit():
                maximum = max(maximum, int(value))
    return maximum


def replace_text(
    package: Package,
    find: str,
    replacement: str,
    *,
    tracked: bool = False,
    author: str = "Document Agent",
    date: str | None = None,
    scopes: Iterable[str] | None = None,
    replace_all: bool = True,
) -> int:
    if not find:
        raise ValueError("find text must not be empty")
    date = date or dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    revision_id = _max_revision_id(package) + 1
    count = 0
    for part in _story_parts(package, scopes):
        root = package.xml(part)
        changed = False
        for paragraph in root.xpath(".//w:p", namespaces=NS):
            text, _spans = _paragraph_runs(paragraph)
            positions: list[int] = []
            cursor = 0
            while True:
                index = text.find(find, cursor)
                if index < 0:
                    break
                positions.append(index)
                cursor = index + max(1, len(find))
                if not replace_all:
                    break
            for start in reversed(positions):
                _replace_range(
                    paragraph,
                    start,
                    start + len(find),
                    replacement,
                    tracked=tracked,
                    author=author,
                    date=date,
                    revision_id=revision_id,
                )
                revision_id += 2 if tracked else 0
                count += 1
                changed = True
            if positions and not replace_all:
                break
        if changed:
            package.write_xml(part, root)
        if count and not replace_all:
            break
    return count


def _ensure_comments_part(package: Package) -> etree._Element:
    if "word/comments.xml" in package.names:
        return package.xml("word/comments.xml")
    root = etree.Element(W + "comments", nsmap={"w": W_NS})

    content_types = package.xml("[Content_Types].xml")
    exists = content_types.xpath(
        "./ct:Override[@PartName='/word/comments.xml']",
        namespaces={"ct": CT_NS},
    )
    if not exists:
        override = etree.SubElement(content_types, f"{{{CT_NS}}}Override")
        override.set("PartName", "/word/comments.xml")
        override.set("ContentType", COMMENTS_CONTENT_TYPE)
        package.write_xml("[Content_Types].xml", content_types)

    rels_name = "word/_rels/document.xml.rels"
    relationships = package.xml(rels_name)
    if not relationships.xpath(
        "./rel:Relationship[@Type=$type]",
        namespaces={"rel": REL_NS},
        type=COMMENTS_REL_TYPE,
    ):
        used = {node.get("Id") for node in relationships}
        number = 1
        while f"rId{number}" in used:
            number += 1
        relationship = etree.SubElement(relationships, f"{{{REL_NS}}}Relationship")
        relationship.set("Id", f"rId{number}")
        relationship.set("Type", COMMENTS_REL_TYPE)
        relationship.set("Target", "comments.xml")
        package.write_xml(rels_name, relationships)
    return root


def _anchor_comment(paragraph: etree._Element, start: int, end: int, comment_id: int) -> None:
    _text, spans = _paragraph_runs(paragraph)
    selected = _selected_spans(spans, start, end)
    if not selected:
        raise EditError("Comment range did not map to editable runs")
    if any("\uFFF9" in span.text for span in selected):
        raise EditError("Comment range crosses a drawing, field, or complex run")
    parent = selected[0].run.getparent()
    if parent is None or any(span.run.getparent() is not parent for span in selected):
        raise EditError("Comment range crosses nested container boundaries")

    first, last = selected[0], selected[-1]
    prefix = first.text[: start - first.start]
    suffix = last.text[end - last.start :]
    target_runs: list[etree._Element] = []
    for span in selected:
        local_start = max(start, span.start) - span.start
        local_end = min(end, span.end) - span.start
        chunk = span.text[local_start:local_end]
        if chunk:
            target_runs.append(_clone_run(span.run, chunk))

    insertion_index = parent.index(first.run)
    for span in selected:
        parent.remove(span.run)
    nodes: list[etree._Element] = []
    if prefix:
        nodes.append(_clone_run(first.run, prefix))
    start_node = etree.Element(W + "commentRangeStart")
    start_node.set(W + "id", str(comment_id))
    end_node = etree.Element(W + "commentRangeEnd")
    end_node.set(W + "id", str(comment_id))
    reference_run = etree.Element(W + "r")
    reference_properties = etree.SubElement(reference_run, W + "rPr")
    style = etree.SubElement(reference_properties, W + "rStyle")
    style.set(W + "val", "CommentReference")
    reference = etree.SubElement(reference_run, W + "commentReference")
    reference.set(W + "id", str(comment_id))
    nodes.extend([start_node, *target_runs, end_node, reference_run])
    if suffix:
        nodes.append(_clone_run(last.run, suffix))
    for offset, node in enumerate(nodes):
        parent.insert(insertion_index + offset, node)


def add_comment(
    package: Package,
    target: str,
    comment_text: str,
    *,
    author: str = "Document Agent",
    initials: str = "DA",
    date: str | None = None,
    occurrence: int = 1,
) -> int:
    if occurrence < 1:
        raise ValueError("occurrence is 1-based")
    date = date or dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    document = package.xml("word/document.xml")
    found = 0
    target_paragraph: etree._Element | None = None
    start = -1
    for paragraph in document.xpath(".//w:p", namespaces=NS):
        text, _spans = _paragraph_runs(paragraph)
        cursor = 0
        while True:
            index = text.find(target, cursor)
            if index < 0:
                break
            found += 1
            if found == occurrence:
                target_paragraph = paragraph
                start = index
                break
            cursor = index + len(target)
        if target_paragraph is not None:
            break
    if target_paragraph is None:
        raise EditError(f"Comment target occurrence {occurrence} not found: {target!r}")

    comments = _ensure_comments_part(package)
    ids = [node.get(W + "id") for node in comments.findall("./w:comment", namespaces=NS)]
    numeric_ids = [int(value) for value in ids if value and value.isdigit()]
    comment_id = max(numeric_ids, default=-1) + 1
    _anchor_comment(target_paragraph, start, start + len(target), comment_id)
    package.write_xml("word/document.xml", document)

    comment = etree.SubElement(comments, W + "comment")
    comment.set(W + "id", str(comment_id))
    comment.set(W + "author", author)
    comment.set(W + "date", date)
    comment.set(W + "initials", initials)
    paragraph = etree.SubElement(comment, W + "p")
    run = etree.SubElement(paragraph, W + "r")
    text = etree.SubElement(run, W + "t")
    text.text = comment_text
    package.write_xml("word/comments.xml", comments)
    return comment_id


def _enable_track_revisions(package: Package) -> None:
    if "word/settings.xml" not in package.names:
        return
    settings = package.xml("word/settings.xml")
    if settings.find("./w:trackRevisions", namespaces=NS) is None:
        node = etree.Element(W + "trackRevisions")
        later = {
            "doNotTrackMoves", "doNotTrackFormatting", "documentProtection",
            "autoFormatOverride", "styleLockTheme", "styleLockQFSet",
            "defaultTabStop", "autoHyphenation", "consecutiveHyphenLimit",
            "hyphenationZone", "doNotHyphenateCaps", "showEnvelope",
            "summaryLength", "clickAndTypeStyle", "defaultTableStyle",
            "evenAndOddHeaders", "bookFoldRevPrinting", "bookFoldPrinting",
            "bookFoldPrintingSheets", "drawingGridHorizontalSpacing",
            "drawingGridVerticalSpacing", "displayHorizontalDrawingGridEvery",
            "displayVerticalDrawingGridEvery", "doNotUseMarginsForDrawingGridOrigin",
            "drawingGridHorizontalOrigin", "drawingGridVerticalOrigin",
            "doNotShadeFormData", "noPunctuationKerning", "characterSpacingControl",
            "printTwoOnOne", "strictFirstAndLastChars", "noLineBreaksAfter",
            "noLineBreaksBefore", "savePreviewPicture", "doNotValidateAgainstSchema",
            "saveInvalidXml", "ignoreMixedContent", "alwaysShowPlaceholderText",
            "doNotDemarcateInvalidXml", "saveXmlDataOnly", "useXSLTWhenSaving",
            "saveThroughXslt", "showXMLTags", "alwaysMergeEmptyNamespace",
            "updateFields", "hdrShapeDefaults", "footnotePr", "endnotePr",
            "compat", "docVars", "rsids", "mathPr", "themeFontLang",
            "clrSchemeMapping",
        }
        insertion = next(
            (
                index
                for index, child in enumerate(settings)
                if child.tag.rsplit("}", 1)[-1] in later
            ),
            len(settings),
        )
        settings.insert(insertion, node)
        package.write_xml("word/settings.xml", settings)


def _update_core_properties(package: Package, values: dict[str, str]) -> None:
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
        tag = mapping.get(key)
        if tag is None:
            continue
        node = root.find(tag)
        if node is None:
            node = etree.SubElement(root, tag)
        node.text = value
    modified = root.find(f"{{{DCTERMS_NS}}}modified")
    if modified is None:
        modified = etree.SubElement(root, f"{{{DCTERMS_NS}}}modified")
        modified.set(f"{{{XSI_NS}}}type", "dcterms:W3CDTF")
    modified.text = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    package.write_xml(name, root)


def validate_edit_plan(plan: dict[str, Any]) -> None:
    schema_path = importlib.resources.files("document_system").joinpath("schemas/docx-edit-plan.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(plan)


def apply_edit_plan(input_path: str | Path, output_path: str | Path, plan: dict[str, Any]) -> dict[str, Any]:
    validate_edit_plan(plan)
    package = Package(input_path)
    default_author = plan.get("author", "Document Agent")
    default_track = bool(plan.get("track_changes", False))
    report: dict[str, Any] = {"replacements": [], "comments": [], "metadata_updated": False}

    def apply_comments(phase: str) -> None:
        for item in plan.get("comments", []):
            if item.get("phase", "after") != phase:
                continue
            comment_id = add_comment(
                package,
                item["target"],
                item["text"],
                author=item.get("author", default_author),
                initials=item.get("initials", "DA"),
                date=item.get("date"),
                occurrence=item.get("occurrence", 1),
            )
            report["comments"].append(
                {"id": comment_id, "target": item["target"], "text": item["text"], "phase": phase}
            )

    # A before-phase comment is useful when its range will itself be redlined.
    apply_comments("before")

    for item in plan.get("replacements", []):
        tracked = bool(item.get("track_changes", default_track))
        count = replace_text(
            package,
            item["find"],
            item.get("replace", ""),
            tracked=tracked,
            author=item.get("author", default_author),
            date=item.get("date"),
            scopes=item.get("scopes"),
            replace_all=item.get("all", True),
        )
        expected = item.get("expected")
        if expected is not None and count != expected:
            raise EditError(
                f"Replacement {item['find']!r}: expected {expected} occurrence(s), found {count}"
            )
        if count == 0 and item.get("required", True):
            raise EditError(f"Required replacement text not found: {item['find']!r}")
        report["replacements"].append(
            {"find": item["find"], "replace": item.get("replace", ""), "count": count, "tracked": tracked}
        )

    if any(item["tracked"] for item in report["replacements"]):
        _enable_track_revisions(package)

    apply_comments("after")

    if plan.get("metadata"):
        _update_core_properties(package, plan["metadata"])
        report["metadata_updated"] = True

    package.save(output_path)
    report["output"] = str(Path(output_path))
    return report


def apply_edit_plan_file(input_path: str | Path, output_path: str | Path, plan_path: str | Path) -> dict[str, Any]:
    return apply_edit_plan(input_path, output_path, read_json(plan_path))
