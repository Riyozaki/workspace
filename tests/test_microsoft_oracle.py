from __future__ import annotations

import pytest

from document_system.microsoft_oracle import (
    MicrosoftOracleError,
    convert_with_microsoft_graph,
    microsoft_oracle_available,
)
from document_system.pdf_build import build_pdf


def test_microsoft_oracle_is_explicit_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv("MS_GRAPH_ACCESS_TOKEN", raising=False)
    source = build_pdf(
        {"content": [{"type": "paragraph", "text": "Oracle"}]},
        tmp_path / "source.pdf",
    )
    assert microsoft_oracle_available() is False
    with pytest.raises(MicrosoftOracleError, match="MS_GRAPH_ACCESS_TOKEN"):
        convert_with_microsoft_graph(source, tmp_path / "converted.pdf")
