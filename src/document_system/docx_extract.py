from __future__ import annotations

import re
import zipfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from lxml import etree

from .errors import UnsupportedDocumentError
from .security import detect_format, inspect_zip, secure_xml_from_bytes

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
NS = {"w": W_NS, "r": R_NS, "w14": W14_NS}
W = f"{{{W_NS}}}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _is_within(node: etree._Element, tag: str) -> bool:
    parent = node.getparent()
    while parent is not None:
        if parent.tag == W + tag:
            return True
        parent = parent.getparent()
    return False


def text_of(element: etree._Element, revisions: str = "accept") -> str:
    if revisions not in {"accept", "reject", "all"}:
        raise ValueError("revisions must be accept, reject, or all")
    fragments: list[str] = []
    for node in element.iter():
        in_deleted = _is_within(node, "del")
        in_inserted = _is_within(node, "ins")
        if revisions == "accept" and in_deleted:
            continue
        if revisions == "reject" and in_inserted:
            continue
        if node.tag in {W + "t", W + "delText"}:
            fragments.append(node.text or "")
        elif node.tag == W + "tab":
            fragments.append("\t")
        elif node.tag in {W + "br", W + "cr"}:
            fragments.append("\n")
        elif revisions == "all" and node.tag == W + "ins":
            fragments.append("⟦+")
        elif revisions == "all" and node.tag == W + "del":
            fragments.append("⟦−")
        if revisions == "all" and node.tag in {W + "ins", W + "del"}:
            # The closing marker is appended by the recursive serializer below instead.
            pass
    if revisions != "all":
        return "".join(fragments)
    return _text_with_revision_markers(element)


def _text_with_revision_markers(element: etree._Element) -> str:
    out: list[str] = []

    def visit(node: etree._Element) -> None:
        marker = None
        if node.tag == W + "ins":
            marker = "+"
        elif node.tag == W + "del":
            marker = "−"
        if marker:
            out.append(f"⟦{marker}")
        if node.tag in {W + "t", W + "delText"}:
            out.append(node.text or "")
        elif node.tag == W + "tab":
            out.append("\t")
        elif node.tag in {W + "br", W + "cr"}:
            out.append("\n")
        for child in node:
            visit(child)
        if marker:
            out.append("⟧")

    visit(element)
    return "".join(out)


def _paragraph_info(paragraph: etree._Element, revisions: str) -> dict[str, Any]:
    style = paragraph.find("./w:pPr/w:pStyle", namespaces=NS)
    num_id = paragraph.find("./w:pPr/w:numPr/w:numId", namespaces=NS)
    ilvl = paragraph.find("./w:pPr/w:numPr/w:ilvl", namespaces=NS)
    return {
        "text": text_of(paragraph, revisions),
        "style": style.get(W + "val") if style is not None else None,
        "numbering": (
            {
                "num_id": num_id.get(W + "val") if num_id is not None else None,
                "level": ilvl.get(W + "val") if ilvl is not None else None,
            }
            if num_id is not None
            else None
        ),
        "page_breaks": len(paragraph.xpath(".//w:br[@w:type='page']", namespaces=NS)),
    }


def _table_info(table: etree._Element, revisions: str) -> dict[str, Any]:
    rows: list[list[str]] = []
    for row in table.findall("./w:tr", namespaces=NS):
        cells: list[str] = []
        for cell in row.findall("./w:tc", namespaces=NS):
            paragraphs = [text_of(p, revisions) for p in cell.findall("./w:p", namespaces=NS)]
            cells.append("\n".join(paragraphs))
        rows.append(cells)
    return {"rows": rows, "row_count": len(rows), "column_count": max((len(r) for r in rows), default=0)}


def _story_parts(names: Iterable[str]) -> list[str]:
    patterns = (
        re.compile(r"^word/header\d+\.xml$"),
        re.compile(r"^word/footer\d+\.xml$"),
    )
    ordered = ["word/document.xml", "word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"]
    present = [name for name in ordered if name in names]
    present.extend(sorted(name for name in names if any(pattern.match(name) for pattern in patterns)))
    return present


def extract_docx(path: str | Path, revisions: str = "accept") -> dict[str, Any]:
    source = Path(path)
    if detect_format(source) != "docx":
        raise UnsupportedDocumentError(f"Not a DOCX package: {source}")
    inspect_zip(source)

    parts: dict[str, Any] = {}
    all_text: list[str] = []
    style_counts: Counter[str] = Counter()
    inventory: Counter[str] = Counter()
    comments: list[dict[str, Any]] = []

    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        for name in _story_parts(names):
            root = secure_xml_from_bytes(archive.read(name), part=name)
            paragraphs = [_paragraph_info(node, revisions) for node in root.xpath(".//w:p", namespaces=NS)]
            tables = [_table_info(node, revisions) for node in root.xpath(".//w:tbl", namespaces=NS)]
            text = "\n".join(item["text"] for item in paragraphs if item["text"])
            parts[name] = {"paragraphs": paragraphs, "tables": tables, "text": text}
            if text:
                all_text.append(text)
            for item in paragraphs:
                if item["style"]:
                    style_counts[item["style"]] += 1
            inventory["paragraphs"] += len(paragraphs)
            inventory["tables"] += len(tables)
            inventory["table_rows"] += sum(table["row_count"] for table in tables)

            if name == "word/comments.xml":
                for node in root.findall("./w:comment", namespaces=NS):
                    comments.append(
                        {
                            "id": node.get(W + "id"),
                            "author": node.get(W + "author"),
                            "date": node.get(W + "date"),
                            "initials": node.get(W + "initials"),
                            "text": text_of(node, revisions="accept"),
                        }
                    )

        main = secure_xml_from_bytes(archive.read("word/document.xml"), part="word/document.xml")
        body = main.find("./w:body", namespaces=NS)
        blocks: list[dict[str, Any]] = []
        if body is not None:
            for child in body:
                if child.tag == W + "p":
                    blocks.append({"type": "paragraph", **_paragraph_info(child, revisions)})
                elif child.tag == W + "tbl":
                    blocks.append({"type": "table", **_table_info(child, revisions)})

        inventory.update(
            {
                "sections": len(main.xpath(".//w:sectPr", namespaces=NS)),
                "insertions": len(main.xpath(".//w:ins", namespaces=NS)),
                "deletions": len(main.xpath(".//w:del", namespaces=NS)),
                "comment_anchors": len(main.xpath(".//w:commentRangeStart", namespaces=NS)),
                "hyperlinks": len(main.xpath(".//w:hyperlink", namespaces=NS)),
                "drawings": len(main.xpath(".//w:drawing", namespaces=NS)),
                "fields": len(main.xpath(".//w:instrText", namespaces=NS)),
                "bookmarks": len(main.xpath(".//w:bookmarkStart", namespaces=NS)),
                "manual_page_breaks": len(main.xpath(".//w:br[@w:type='page']", namespaces=NS)),
                "headers": len([name for name in names if re.match(r"^word/header\d+\.xml$", name)]),
                "footers": len([name for name in names if re.match(r"^word/footer\d+\.xml$", name)]),
                "footnotes": max(0, len(parts.get("word/footnotes.xml", {}).get("paragraphs", [])) - 2),
                "endnotes": max(0, len(parts.get("word/endnotes.xml", {}).get("paragraphs", [])) - 2),
                "comments": len(comments),
                "media_parts": len([name for name in names if name.startswith("word/media/") and not name.endswith("/")]),
            }
        )

        settings: dict[str, Any] = {}
        if "word/settings.xml" in names:
            root = secure_xml_from_bytes(archive.read("word/settings.xml"), part="word/settings.xml")
            settings = {
                "track_revisions": root.find("./w:trackRevisions", namespaces=NS) is not None,
                "update_fields": (
                    root.find("./w:updateFields", namespaces=NS).get(W + "val", "true")
                    if root.find("./w:updateFields", namespaces=NS) is not None
                    else None
                ),
            }

        fields = ["".join(node.itertext()).strip() for node in main.xpath(".//w:instrText", namespaces=NS)]

    return {
        "path": str(source),
        "revisions_view": revisions,
        "text": "\n\n".join(all_text),
        "blocks": blocks,
        "parts": parts,
        "inventory": dict(inventory),
        "styles": dict(style_counts.most_common()),
        "fields": fields,
        "comments": comments,
        "settings": settings,
    }
