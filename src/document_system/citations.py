from __future__ import annotations

from pathlib import Path
from typing import Any

from .docx_extract import extract_docx
from .errors import UnsupportedDocumentError
from .pdf_extract import extract_pdf
from .pptx_extract import extract_pptx
from .security import detect_format
from .xlsx_extract import extract_xlsx


def build_citation_index(path: str | Path, *, max_entries: int = 200_000) -> dict[str, Any]:
    source = Path(path)
    fmt = detect_format(source)
    entries: list[dict[str, Any]] = []
    if fmt == "docx":
        document = extract_docx(source)
        headings: dict[int, str] = {}
        paragraph_number = 0
        table_number = 0
        for block in document["blocks"]:
            if block["type"] == "paragraph":
                paragraph_number += 1
                text = block.get("text", "")
                style = block.get("style") or ""
                if style.lower().startswith("heading"):
                    suffix = "".join(char for char in style if char.isdigit())
                    level = int(suffix or 1)
                    headings[level] = text
                    headings = {key: value for key, value in headings.items() if key <= level}
                if text:
                    section = " > ".join(headings[key] for key in sorted(headings))
                    entries.append(
                        {
                            "citation": f"[DOCX:p{paragraph_number}]",
                            "kind": "paragraph",
                            "location": {
                                "part": "word/document.xml",
                                "paragraph": paragraph_number,
                                "section": section or None,
                                "style": style or None,
                            },
                            "text": text,
                        }
                    )
            elif block["type"] == "table":
                table_number += 1
                for row_number, row in enumerate(block.get("rows", []), start=1):
                    text = " | ".join(row)
                    entries.append(
                        {
                            "citation": f"[DOCX:table{table_number}:row{row_number}]",
                            "kind": "table-row",
                            "location": {
                                "part": "word/document.xml",
                                "table": table_number,
                                "row": row_number,
                            },
                            "text": text,
                        }
                    )
    elif fmt == "xlsx":
        workbook = extract_xlsx(source, include_cells=True, max_cells_per_sheet=max_entries)
        for sheet in workbook["sheets"]:
            for cell in sheet.get("cells") or []:
                value = cell["value"]
                if value is None:
                    continue
                reference = f"{sheet['name']}!{cell['cell']}"
                entries.append(
                    {
                        "citation": f"[XLSX:{reference}]",
                        "kind": "cell",
                        "location": {
                            "sheet": sheet["name"],
                            "cell": cell["cell"],
                            "formula": value if cell["data_type"] == "f" else None,
                        },
                        "text": str(value),
                    }
                )
    elif fmt == "pptx":
        deck = extract_pptx(source)
        for slide in deck["slides"]:
            for shape in slide["shapes"]:
                if not shape.get("text"):
                    continue
                entries.append(
                    {
                        "citation": f"[PPTX:s{slide['number']}:shape{shape['index']}]",
                        "kind": "shape",
                        "location": {
                            "slide": slide["number"],
                            "shape": shape["index"],
                            "name": shape["name"],
                            "title": slide["title"],
                        },
                        "text": shape["text"],
                    }
                )
            if slide.get("notes"):
                entries.append(
                    {
                        "citation": f"[PPTX:s{slide['number']}:notes]",
                        "kind": "speaker-notes",
                        "location": {"slide": slide["number"], "title": slide["title"]},
                        "text": slide["notes"],
                    }
                )
    elif fmt == "pdf":
        pdf = extract_pdf(source)
        for page in pdf["pages"]:
            for line_number, line in enumerate(page["text"].splitlines(), start=1):
                if line.strip():
                    entries.append(
                        {
                            "citation": f"[PDF:p{page['number']}:l{line_number}]",
                            "kind": "text-line",
                            "location": {"page": page["number"], "line": line_number},
                            "text": line,
                        }
                    )
    else:
        raise UnsupportedDocumentError(f"Citation index is unsupported for {fmt}")
    if len(entries) > max_entries:
        raise ValueError(
            f"Citation index has {len(entries)} entries; safety limit is {max_entries}"
        )
    return {
        "path": str(source),
        "format": fmt,
        "entries": entries,
        "entry_count": len(entries),
    }


def locate_text(
    path: str | Path,
    query: str,
    *,
    case_sensitive: bool = False,
    max_hits: int = 100,
) -> dict[str, Any]:
    if not query:
        raise ValueError("query must not be empty")
    index = build_citation_index(path)
    needle = query if case_sensitive else query.casefold()
    hits = []
    for entry in index["entries"]:
        haystack = entry["text"] if case_sensitive else entry["text"].casefold()
        if needle in haystack:
            hits.append(entry)
            if len(hits) >= max_hits:
                break
    return {
        "path": index["path"],
        "format": index["format"],
        "query": query,
        "hits": hits,
        "hit_count": len(hits),
        "truncated": len(hits) == max_hits,
    }
