from __future__ import annotations

import warnings
import zipfile

import pytest

from document_system.errors import UnsafeArchiveError
from document_system.security import ArchivePolicy, inspect_zip, secure_xml_from_bytes


def test_rejects_path_traversal(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../escape.txt", "no")
    with pytest.raises(UnsafeArchiveError, match="parent traversal"):
        inspect_zip(archive)


def test_rejects_duplicate_members(tmp_path):
    archive = tmp_path / "duplicate.zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("same.txt", "one")
            handle.writestr("same.txt", "two")
    with pytest.raises(UnsafeArchiveError, match="duplicate"):
        inspect_zip(archive)


def test_rejects_case_insensitive_path_collision(tmp_path):
    archive = tmp_path / "case.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("word/document.xml", "one")
        handle.writestr("WORD/document.xml", "two")
    with pytest.raises(UnsafeArchiveError, match="case-insensitive"):
        inspect_zip(archive)


def test_rejects_zip_bomb_ratio(tmp_path):
    archive = tmp_path / "ratio.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("large.txt", b"0" * (2 * 1024 * 1024))
    with pytest.raises(UnsafeArchiveError, match="compression ratio"):
        inspect_zip(archive, policy=ArchivePolicy(max_compression_ratio=10))


def test_rejects_xml_entities():
    with pytest.raises(UnsafeArchiveError, match="DTD/entity"):
        secure_xml_from_bytes(b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>')


def test_accepts_small_safe_archive(tmp_path):
    archive = tmp_path / "safe.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("folder/value.txt", "safe")
    report = inspect_zip(archive)
    assert report["entries"] == 1
    assert report["crc_ok"] is True
