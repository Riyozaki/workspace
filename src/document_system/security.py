from __future__ import annotations

import re
import stat
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from lxml import etree

from .errors import UnsafeArchiveError


@dataclass(frozen=True)
class ArchivePolicy:
    max_entries: int = 20_000
    max_entry_size: int = 256 * 1024 * 1024
    max_total_size: int = 1024 * 1024 * 1024
    max_compression_ratio: float = 500.0
    reject_encrypted: bool = True
    reject_symlinks: bool = True


_DRIVE = re.compile(r"^[A-Za-z]:")


def _unsafe_member_reason(info: zipfile.ZipInfo, policy: ArchivePolicy) -> str | None:
    name = info.filename.replace("\\", "/")
    pure = PurePosixPath(name)
    if not name or "\x00" in name:
        return "empty name or NUL byte"
    if name.startswith(("/", "//")) or _DRIVE.match(name):
        return "absolute path"
    if any(part == ".." for part in pure.parts):
        return "parent traversal"
    if policy.reject_encrypted and info.flag_bits & 0x1:
        return "encrypted entry"
    mode = (info.external_attr >> 16) & 0xFFFF
    if policy.reject_symlinks and mode and stat.S_ISLNK(mode):
        return "symbolic link"
    if info.file_size > policy.max_entry_size:
        return f"entry expands beyond {policy.max_entry_size} bytes"
    ratio = info.file_size / max(info.compress_size, 1)
    if info.file_size > 1024 * 1024 and ratio > policy.max_compression_ratio:
        return f"compression ratio {ratio:.1f} exceeds {policy.max_compression_ratio:.1f}"
    return None


def inspect_zip(path: str | Path, policy: ArchivePolicy | None = None, test_crc: bool = True) -> dict[str, Any]:
    policy = policy or ArchivePolicy()
    source = Path(path)
    if not zipfile.is_zipfile(source):
        raise UnsafeArchiveError(f"Not a ZIP/OOXML package: {source}")

    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > policy.max_entries:
            raise UnsafeArchiveError(
                f"Archive has {len(entries)} entries; policy allows {policy.max_entries}"
            )

        names: set[str] = set()
        folded_names: dict[str, str] = {}
        duplicates: list[str] = []
        case_collisions: list[tuple[str, str]] = []
        total_uncompressed = 0
        total_compressed = 0
        suspicious: list[dict[str, str]] = []
        encrypted = 0
        symlinks = 0

        for info in entries:
            normalized = info.filename.replace("\\", "/")
            if normalized in names:
                duplicates.append(normalized)
            names.add(normalized)
            folded = normalized.casefold()
            if folded in folded_names and folded_names[folded] != normalized:
                case_collisions.append((folded_names[folded], normalized))
            else:
                folded_names[folded] = normalized
            total_uncompressed += info.file_size
            total_compressed += info.compress_size
            if info.flag_bits & 0x1:
                encrypted += 1
            mode = (info.external_attr >> 16) & 0xFFFF
            if mode and stat.S_ISLNK(mode):
                symlinks += 1
            reason = _unsafe_member_reason(info, policy)
            if reason:
                suspicious.append({"entry": info.filename, "reason": reason})

        if total_uncompressed > policy.max_total_size:
            suspicious.append(
                {
                    "entry": "<archive>",
                    "reason": (
                        f"total expanded size {total_uncompressed} exceeds "
                        f"{policy.max_total_size} bytes"
                    ),
                }
            )
        if duplicates:
            suspicious.extend({"entry": name, "reason": "duplicate member name"} for name in duplicates)
        if case_collisions:
            suspicious.extend(
                {
                    "entry": second,
                    "reason": f"case-insensitive path collision with {first}",
                }
                for first, second in case_collisions
            )
        if suspicious:
            details = "; ".join(f"{item['entry']}: {item['reason']}" for item in suspicious[:10])
            extra = len(suspicious) - 10
            if extra > 0:
                details += f"; and {extra} more"
            raise UnsafeArchiveError(f"Unsafe archive: {details}")

        bad_crc = archive.testzip() if test_crc else None
        if bad_crc:
            raise UnsafeArchiveError(f"CRC check failed for archive member: {bad_crc}")

    return {
        "entries": len(entries),
        "compressed_bytes": total_compressed,
        "uncompressed_bytes": total_uncompressed,
        "compression_ratio": round(total_uncompressed / max(total_compressed, 1), 3),
        "encrypted_entries": encrypted,
        "symlink_entries": symlinks,
        "policy": asdict(policy),
        "crc_ok": bad_crc is None,
    }


def secure_xml_from_bytes(value: bytes, *, part: str = "<xml>") -> etree._Element:
    prefix = value[:4096].upper()
    if b"<!DOCTYPE" in prefix or b"<!ENTITY" in prefix:
        raise UnsafeArchiveError(f"DTD/entity declarations are forbidden in {part}")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        recover=False,
        remove_blank_text=False,
        strip_cdata=False,
        huge_tree=False,
    )
    try:
        return etree.fromstring(value, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise UnsafeArchiveError(f"Malformed XML in {part}: {exc}") from exc


def detect_format(path: str | Path) -> str:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        with source.open("rb") as handle:
            if handle.read(5) == b"%PDF-":
                return "pdf"
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            names = set(archive.namelist())
        if "word/document.xml" in names:
            return "docx"
        if "xl/workbook.xml" in names:
            return "xlsx"
        if "ppt/presentation.xml" in names:
            return "pptx"
        if "mimetype" in names:
            return "odf"
        return "zip"
    if suffix in {".doc", ".xls", ".ppt", ".rtf"}:
        return suffix[1:]
    return "unknown"
