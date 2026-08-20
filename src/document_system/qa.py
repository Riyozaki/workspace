from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .docx_extract import extract_docx
from .docx_revisions import verify_tracked_text
from .docx_rules import validate_docx_rules
from .opc import inspect_ooxml, issue
from .openxml_sdk import validate_with_openxml_sdk
from .render import render_document
from .util import write_json

PLACEHOLDER_PATTERNS = [
    re.compile(r"\{\{[^{}\n]{1,120}\}\}"),
    re.compile(r"<<[^<>\n]{1,120}>>"),
    re.compile(r"\[(?:TODO|TBD|PLACEHOLDER|INSERT[^\]]*)\]", re.IGNORECASE),
    re.compile(r"\b(?:TODO|TBD)\b", re.IGNORECASE),
]
FORMULA_ERROR_PATTERN = re.compile(r"#(?:REF!|VALUE!|DIV/0!|NAME\?|N/A|NUM!|NULL!)")


def _find_placeholders(text: str) -> list[str]:
    values: list[str] = []
    for pattern in PLACEHOLDER_PATTERNS:
        values.extend(match.group(0) for match in pattern.finditer(text))
    return sorted(set(values))


def validate_docx(
    path: str | Path,
    *,
    output_report: str | Path | None = None,
    render: bool = False,
    render_dir: str | Path | None = None,
    strict: bool = False,
    expect_text: Iterable[str] = (),
    forbid_text: Iterable[str] = (),
    require_header: bool = False,
    require_footer: bool = False,
    require_page_numbers: bool = False,
    require_images: int = 0,
    require_toc: bool = False,
    allow_placeholders: bool = False,
    tracked_against: str | Path | None = None,
    openxml_sdk: bool = True,
    require_openxml_sdk: bool = False,
    timeout: int = 180,
) -> dict[str, Any]:
    source = Path(path)
    package = inspect_ooxml(source)
    semantic = extract_docx(source, revisions="accept")
    rule_issues = validate_docx_rules(source)
    issues: list[dict[str, str]] = [*package["issues"], *rule_issues]
    text = semantic["text"]
    inventory = semantic["inventory"]

    for expected in expect_text:
        if expected not in text:
            issues.append(issue("error", "expected-text-missing", f"Expected text not found: {expected!r}"))
    for forbidden in forbid_text:
        if forbidden in text:
            issues.append(issue("error", "forbidden-text-present", f"Forbidden text is present: {forbidden!r}"))

    placeholders = _find_placeholders(text)
    if placeholders and not allow_placeholders:
        for value in placeholders[:25]:
            issues.append(issue("error", "placeholder-present", f"Unresolved placeholder: {value!r}"))
        if len(placeholders) > 25:
            issues.append(issue("error", "placeholder-list-truncated", f"{len(placeholders) - 25} more placeholders omitted"))

    if FORMULA_ERROR_PATTERN.search(text):
        issues.append(issue("error", "formula-error-text", "Document text contains a spreadsheet formula error token"))
    if require_header and inventory.get("headers", 0) == 0:
        issues.append(issue("error", "header-required", "At least one header part is required"))
    if require_footer and inventory.get("footers", 0) == 0:
        issues.append(issue("error", "footer-required", "At least one footer part is required"))
    if require_images and inventory.get("media_parts", 0) < require_images:
        issues.append(
            issue(
                "error",
                "images-required",
                f"Expected at least {require_images} media part(s), found {inventory.get('media_parts', 0)}",
            )
        )
    fields = " ".join(semantic.get("fields", [])).upper()
    if require_page_numbers and "PAGE" not in fields:
        # PAGE commonly lives in footer parts; the semantic extractor exposes those in parts.
        footer_fields = " ".join(
            part["text"] for name, part in semantic["parts"].items() if name.startswith("word/footer")
        ).upper()
        if "PAGE" not in footer_fields:
            # Search package inventory does not expose instrText in all stories yet; package XML is checked below.
            import zipfile

            from .docx_extract import NS
            from .security import secure_xml_from_bytes

            found = False
            with zipfile.ZipFile(source) as archive:
                for name in archive.namelist():
                    if name.startswith("word/footer") and name.endswith(".xml"):
                        root = secure_xml_from_bytes(archive.read(name), part=name)
                        if any("PAGE" in (node.text or "").upper() for node in root.xpath(".//w:instrText", namespaces=NS)):
                            found = True
                            break
            if not found:
                issues.append(issue("error", "page-number-required", "No PAGE field found in document footers"))
    if require_toc and "TOC" not in fields:
        issues.append(issue("error", "toc-required", "No TOC field found in main document"))

    if not text.strip():
        issues.append(issue("error", "empty-document", "No visible text extracted from the DOCX"))

    tracked_report = None
    if tracked_against:
        tracked_report = verify_tracked_text(tracked_against, source)
        if not tracked_report["passed"]:
            issues.append(
                issue(
                    "error",
                    "untracked-text-change",
                    tracked_report["message"],
                )
            )

    schema_report = None
    if openxml_sdk:
        schema_report = validate_with_openxml_sdk(source, timeout=timeout)
        if schema_report.get("available") and schema_report.get("valid") is False:
            issues.append(
                issue(
                    "error",
                    "openxml-sdk-invalid",
                    f"Open XML SDK reported {schema_report.get('error_count', 'one or more')} error(s)",
                )
            )
        elif require_openxml_sdk and not schema_report.get("available"):
            issues.append(
                issue(
                    "error",
                    "openxml-sdk-unavailable",
                    f"Open XML SDK validation was required: {schema_report.get('reason')}",
                )
            )

    render_report = None
    if render:
        destination = Path(render_dir or source.parent / f"{source.stem}-render")
        try:
            render_report = render_document(source, destination, timeout=timeout)
            for page in render_report["summary"]["blank_pages"]:
                issues.append(issue("warning", "likely-blank-page", f"Rendered page {page} appears blank"))
            for page in render_report["summary"]["possible_edge_clipping_pages"]:
                issues.append(issue("warning", "possible-edge-clipping", f"Rendered page {page} has ink at the page edge"))
        except Exception as exc:
            issues.append(issue("error", "render-failed", str(exc)))

    counts = Counter(item["severity"] for item in issues)
    passed = counts["error"] == 0 and (not strict or counts["warning"] == 0)
    report = {
        "path": str(source),
        "format": "docx",
        "passed": passed,
        "strict": strict,
        "summary": {
            "errors": counts["error"],
            "warnings": counts["warning"],
            "info": counts["info"],
        },
        "issues": issues,
        "package": package,
        "semantic": {
            "inventory": inventory,
            "styles": semantic["styles"],
            "fields": semantic["fields"],
            "comments": semantic["comments"],
            "settings": semantic["settings"],
            "characters": len(text),
            "words": len(text.split()),
            "placeholders": placeholders,
        },
        "tracked_changes": tracked_report,
        "schema": schema_report,
        "render": render_report,
    }
    if output_report:
        write_json(output_report, report)
    return report
