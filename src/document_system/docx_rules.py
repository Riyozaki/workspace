from __future__ import annotations

import re
import zipfile
from collections import Counter
from pathlib import Path

from .docx_extract import NS, W
from .opc import issue
from .security import inspect_zip, secure_xml_from_bytes


def validate_docx_rules(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    inspect_zip(source)
    issues: list[dict[str, str]] = []
    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        document = secure_xml_from_bytes(archive.read("word/document.xml"), part="word/document.xml")
        body = document.find("./w:body", namespaces=NS)
        if body is None:
            issues.append(issue("error", "missing-body", "word/document.xml has no w:body", "word/document.xml"))
        else:
            final_sections = [child for child in body if child.tag == W + "sectPr"]
            if not final_sections:
                issues.append(issue("error", "missing-final-section", "Document body has no final sectPr", "word/document.xml"))
            elif len(final_sections) > 1:
                issues.append(issue("error", "multiple-final-sections", "Document body has multiple direct sectPr elements", "word/document.xml"))
            elif body[-1] is not final_sections[0]:
                issues.append(issue("error", "section-not-last", "Final sectPr is not the last body child", "word/document.xml"))

        story_names = ["word/document.xml"] + sorted(
            name
            for name in names
            if re.match(r"word/(?:header|footer|footnotes|endnotes)\d*\.xml$", name)
        )
        revision_ids: list[str] = []
        for name in story_names:
            root = secure_xml_from_bytes(archive.read(name), part=name)
            for node in root.xpath(".//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo", namespaces=NS):
                revision_id = node.get(W + "id")
                revision_ids.append(revision_id or "")
                for attribute in ("id", "author", "date"):
                    if not node.get(W + attribute):
                        issues.append(
                            issue(
                                "error",
                                "revision-metadata-missing",
                                f"{node.tag.rsplit('}', 1)[-1]} lacks w:{attribute}",
                                name,
                            )
                        )
                if node.tag == W + "del":
                    if node.xpath(".//w:t", namespaces=NS):
                        issues.append(issue("error", "deleted-text-wrong-element", "w:del contains w:t; use w:delText", name))
            # A table cell must finish with a paragraph, even when its visible content is a nested table.
            for cell in root.xpath(".//w:tc", namespaces=NS):
                if len(cell) == 0 or cell[-1].tag != W + "p":
                    issues.append(issue("error", "table-cell-missing-final-paragraph", "Table cell does not end with w:p", name))

            begins = root.xpath(".//w:fldChar[@w:fldCharType='begin']", namespaces=NS)
            ends = root.xpath(".//w:fldChar[@w:fldCharType='end']", namespaces=NS)
            if len(begins) != len(ends):
                issues.append(issue("error", "unbalanced-fields", f"Field begin/end count is {len(begins)}/{len(ends)}", name))

            starts = Counter(node.get(W + "id") for node in root.xpath(".//w:bookmarkStart", namespaces=NS))
            ends_bookmarks = Counter(node.get(W + "id") for node in root.xpath(".//w:bookmarkEnd", namespaces=NS))
            if starts != ends_bookmarks:
                issues.append(issue("error", "unbalanced-bookmarks", "Bookmark start/end IDs do not match", name))

        duplicate_revision_ids = [value for value, count in Counter(revision_ids).items() if value and count > 1]
        for value in duplicate_revision_ids:
            issues.append(issue("warning", "duplicate-revision-id", f"Revision id {value} appears more than once"))

        starts = Counter(node.get(W + "id") for node in document.xpath(".//w:commentRangeStart", namespaces=NS))
        ends = Counter(node.get(W + "id") for node in document.xpath(".//w:commentRangeEnd", namespaces=NS))
        references = Counter(node.get(W + "id") for node in document.xpath(".//w:commentReference", namespaces=NS))
        comments: Counter[str | None] = Counter()
        if "word/comments.xml" in names:
            comments_root = secure_xml_from_bytes(archive.read("word/comments.xml"), part="word/comments.xml")
            comments = Counter(node.get(W + "id") for node in comments_root.findall("./w:comment", namespaces=NS))
            for node in comments_root.findall("./w:comment", namespaces=NS):
                if not node.get(W + "author"):
                    issues.append(issue("error", "comment-author-missing", f"Comment {node.get(W + 'id')} lacks author", "word/comments.xml"))
        all_comment_ids = set(starts) | set(ends) | set(references) | set(comments)
        for comment_id in sorted(value for value in all_comment_ids if value is not None):
            counts = {
                "start": starts[comment_id],
                "end": ends[comment_id],
                "reference": references[comment_id],
                "comment": comments[comment_id],
            }
            if any(value != 1 for value in counts.values()):
                issues.append(
                    issue(
                        "error",
                        "comment-sync-error",
                        f"Comment {comment_id} cross-part counts are {counts}; expected one of each",
                    )
                )
        if "word/comments.xml" in names and not comments:
            issues.append(issue("warning", "empty-comments-part", "comments.xml exists but contains no comments", "word/comments.xml"))
    return issues
