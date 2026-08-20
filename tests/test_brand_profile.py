from __future__ import annotations

import json
from pathlib import Path

from document_system.brand_profile import apply_brand_profile


def _profile():
    path = Path(__file__).resolve().parents[1] / "examples/brand/example-corporate.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_brand_profile_merges_format_defaults_and_user_overrides():
    profile = _profile()
    docx = apply_brand_profile(
        profile,
        {
            "theme": {"accent": "FF0000"},
            "content": [{"type": "paragraph", "text": "Body"}],
        },
        format_name="docx",
    )
    assert docx["theme"]["primary"] == "203F54"
    assert docx["theme"]["accent"] == "FF0000"
    assert docx["footer"]["page_numbers"] is True
    assert docx["metadata"]["comments"] == "Brand profile: Example Corporate"

    xlsx = apply_brand_profile(
        profile,
        {"sheets": [{"name": "Data"}]},
        format_name="xlsx",
    )
    assert xlsx["theme"]["font"] == "Arial"
    assert "background" not in xlsx["theme"]

    pptx = apply_brand_profile(
        profile,
        {"slides": [{"layout": "title", "title": "Deck"}]},
        format_name="pptx",
    )
    assert pptx["footer"].startswith("Example Corporate")

    pdf = apply_brand_profile(
        profile,
        {"content": [{"type": "paragraph", "text": "PDF"}]},
        format_name="pdf",
    )
    assert "font" not in pdf["theme"]
    assert pdf["footer"].startswith("Example Corporate")
