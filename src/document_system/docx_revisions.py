from __future__ import annotations

from pathlib import Path
from typing import Any

from lxml import etree

from .docx_edit import NS, Package, W
from .docx_extract import extract_docx

REVISION_TAGS = {W + "ins", W + "del", W + "moveFrom", W + "moveTo"}


def _unwrap(node: etree._Element, *, restore_deleted_text: bool = False) -> None:
    parent = node.getparent()
    if parent is None:
        return
    index = parent.index(node)
    children = list(node)
    for child in children:
        node.remove(child)
        if restore_deleted_text:
            for text in child.iter(W + "delText"):
                text.tag = W + "t"
        parent.insert(index, child)
        index += 1
    parent.remove(node)


def _accept_deleted_paragraph_marks(root: etree._Element) -> int:
    joined = 0
    paragraphs = list(root.xpath(".//w:p[w:pPr/w:rPr/w:del]", namespaces=NS))
    for paragraph in paragraphs:
        marker = paragraph.find("./w:pPr/w:rPr/w:del", namespaces=NS)
        if marker is None:
            continue
        marker.getparent().remove(marker)
        sibling = paragraph.getnext()
        while sibling is not None and sibling.tag != W + "p":
            sibling = sibling.getnext()
        if sibling is None:
            continue
        for child in list(sibling):
            if child.tag != W + "pPr":
                sibling.remove(child)
                paragraph.append(child)
        sibling.getparent().remove(sibling)
        joined += 1
    return joined


def _reject_deleted_paragraph_marks(root: etree._Element) -> int:
    markers = list(root.xpath(".//w:pPr/w:rPr/w:del", namespaces=NS))
    for marker in markers:
        marker.getparent().remove(marker)
    return len(markers)


def _process_root(root: etree._Element, mode: str) -> dict[str, int]:
    counts = {
        "insertions": len(root.xpath(".//w:ins", namespaces=NS)),
        "deletions": len(root.xpath(".//w:del", namespaces=NS)),
        "move_from": len(root.xpath(".//w:moveFrom", namespaces=NS)),
        "move_to": len(root.xpath(".//w:moveTo", namespaces=NS)),
        "paragraph_marks": len(root.xpath(".//w:pPr/w:rPr/w:del", namespaces=NS)),
        "paragraphs_joined": 0,
    }
    if mode == "accept":
        counts["paragraphs_joined"] = _accept_deleted_paragraph_marks(root)
    else:
        _reject_deleted_paragraph_marks(root)

    # Deepest first so nested revisions are deterministic.
    nodes = [node for node in root.iter() if node.tag in REVISION_TAGS]
    for node in reversed(nodes):
        if node.getparent() is None:
            continue
        if mode == "accept":
            if node.tag in {W + "ins", W + "moveTo"}:
                _unwrap(node)
            else:
                node.getparent().remove(node)
        else:
            if node.tag in {W + "del", W + "moveFrom"}:
                _unwrap(node, restore_deleted_text=True)
            else:
                node.getparent().remove(node)
    return counts


def apply_revision_view(
    input_path: str | Path,
    output_path: str | Path,
    *,
    mode: str,
) -> dict[str, Any]:
    if mode not in {"accept", "reject"}:
        raise ValueError("mode must be accept or reject")
    package = Package(input_path)
    parts = sorted(
        name
        for name in package.names
        if name == "word/document.xml"
        or name.startswith("word/header")
        or name.startswith("word/footer")
        or name in {"word/footnotes.xml", "word/endnotes.xml"}
    )
    reports = {}
    for part in parts:
        root = package.xml(part)
        report = _process_root(root, mode)
        if any(report.values()):
            package.write_xml(part, root)
            reports[part] = report
    package.save(output_path)
    remaining = extract_docx(output_path, revisions="all")["inventory"]
    return {
        "input": str(Path(input_path)),
        "output": str(Path(output_path)),
        "mode": mode,
        "parts": reports,
        "remaining_insertions": remaining.get("insertions", 0),
        "remaining_deletions": remaining.get("deletions", 0),
    }


def verify_tracked_text(original_path: str | Path, modified_path: str | Path) -> dict[str, Any]:
    original = extract_docx(original_path, revisions="accept")
    rejected = extract_docx(modified_path, revisions="reject")
    original_parts = original["parts"]
    rejected_parts = rejected["parts"]
    differences = []
    story_parts = {
        part
        for part in set(original_parts) | set(rejected_parts)
        if part == "word/document.xml"
        or part.startswith("word/header")
        or part.startswith("word/footer")
        or part in {"word/footnotes.xml", "word/endnotes.xml"}
    }
    for part in sorted(story_parts):
        before = original_parts.get(part, {}).get("text", "")
        after = rejected_parts.get(part, {}).get("text", "")
        if before != after:
            differences.append(
                {
                    "part": part,
                    "original": before,
                    "rejected_modified": after,
                }
            )
    return {
        "original": str(Path(original_path)),
        "modified": str(Path(modified_path)),
        "passed": not differences,
        "differences": differences,
        "message": (
            "Rejecting all revisions reproduces the original visible text"
            if not differences
            else "Visible text differs after rejecting revisions; one or more edits may be untracked"
        ),
    }
