from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .opc import issue
from .pdf_extract import extract_pdf
from .render import render_document
from .util import write_json

# U+FFFD means text decoding failed. Long contiguous runs of square glyphs are
# the common PDF symptom of using a font without the requested Unicode glyphs.
# A threshold avoids rejecting isolated square symbols used as legitimate UI.
MISSING_GLYPH_PATTERN = re.compile(r"\uFFFD+|[\u25A0\u25A1\u25AF]{3,}")


def validate_pdf(
    path: str | Path,
    *,
    output_report: str | Path | None = None,
    password: str | None = None,
    render: bool = False,
    render_dir: str | Path | None = None,
    strict: bool = False,
    expected_pages: int | None = None,
    require_text: Iterable[str] = (),
    require_forms: bool = False,
    allow_placeholders: bool = False,
    allow_risk_features: bool = False,
) -> dict[str, Any]:
    source = Path(path)
    issues: list[dict[str, str]] = []
    try:
        pdf = extract_pdf(source, password=password, extract_tables=False)
    except Exception as exc:
        pdf = None
        issues.append(issue("error", "pdf-parse-failed", str(exc)))
    if pdf:
        if pdf.get("encrypted") and not pdf.get("unlocked"):
            issues.append(issue("error", "pdf-locked", "PDF is encrypted and could not be opened"))
        else:
            if expected_pages is not None and pdf["page_count"] != expected_pages:
                issues.append(issue("error", "page-count-mismatch", f"Expected {expected_pages} pages, found {pdf['page_count']}"))
            for text in require_text:
                if text not in pdf["text"]:
                    issues.append(issue("error", "required-text-missing", f"Required PDF text not found: {text!r}"))
            if require_forms and not pdf["form_field_count"]:
                issues.append(issue("error", "form-fields-required", "PDF has no AcroForm fields"))
            if pdf["placeholders"] and not allow_placeholders:
                for placeholder in pdf["placeholders"][:25]:
                    issues.append(issue("error", "placeholder-present", f"Page {placeholder['page']} contains {placeholder['value']!r}"))
            for page in pdf["pages"]:
                missing_glyphs = MISSING_GLYPH_PATTERN.search(page["text"])
                if missing_glyphs:
                    sample = missing_glyphs.group(0)
                    issues.append(
                        issue(
                            "error",
                            "missing-glyph-markers",
                            f"Page {page['number']} contains a suspicious missing-glyph sequence ({len(sample)} characters)",
                        )
                    )
            for font in pdf["unembedded_fonts"]:
                issues.append(issue("warning", "font-not-embedded", f"Font is not embedded: {font}"))
            if pdf["risk_features"] and not allow_risk_features:
                for feature in pdf["risk_features"]:
                    issues.append(issue("error", "active-or-embedded-content", f"PDF contains risky feature: {feature}"))
            for page in pdf["pages"]:
                if page["width_pt"] <= 0 or page["height_pt"] <= 0:
                    issues.append(issue("error", "invalid-page-size", f"Page {page['number']} has invalid dimensions"))

    render_report = None
    if render and pdf and pdf.get("unlocked"):
        try:
            render_report = render_document(source, render_dir or source.parent / f"{source.stem}-render")
            if render_report["page_count"] != pdf["page_count"]:
                issues.append(issue("error", "render-page-count-mismatch", f"Rendered {render_report['page_count']} of {pdf['page_count']} pages"))
            for page in render_report["summary"]["blank_pages"]:
                issues.append(issue("warning", "likely-blank-page", f"Rendered page {page} appears blank"))
            for page in render_report["summary"]["possible_edge_clipping_pages"]:
                issues.append(issue("warning", "possible-edge-clipping", f"Rendered page {page} has ink at the edge"))
        except Exception as exc:
            issues.append(issue("error", "render-failed", str(exc)))

    counts = Counter(item["severity"] for item in issues)
    passed = counts["error"] == 0 and (not strict or counts["warning"] == 0)
    report = {
        "path": str(source),
        "format": "pdf",
        "passed": passed,
        "strict": strict,
        "summary": {"errors": counts["error"], "warnings": counts["warning"], "info": counts["info"]},
        "issues": issues,
        "pdf": pdf,
        "render": render_report,
    }
    if output_report:
        write_json(output_report, report)
    return report
