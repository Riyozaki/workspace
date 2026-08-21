from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .errors import UnsafeModelError

GLB_MAGIC = b"glTF"
JSON_CHUNK = b"JSON"


def inspect_glb_container(
    path: str | Path,
    *,
    max_bytes: int = 512 * 1024 * 1024,
    max_json_bytes: int = 32 * 1024 * 1024,
    max_nodes: int = 100_000,
    max_meshes: int = 25_000,
    max_accessors: int = 250_000,
) -> dict[str, Any]:
    source = Path(path)
    size = source.stat().st_size
    if size > max_bytes:
        raise UnsafeModelError(f"GLB size {size} exceeds safety limit {max_bytes}")
    with source.open("rb") as handle:
        header = handle.read(12)
        if len(header) != 12:
            raise UnsafeModelError("Truncated GLB header")
        magic, version, declared_length = struct.unpack("<4sII", header)
        if magic != GLB_MAGIC or version != 2:
            raise UnsafeModelError("Only binary glTF 2.0 (GLB) is accepted")
        if declared_length != size:
            raise UnsafeModelError(f"GLB declared length {declared_length} does not match file size {size}")
        chunks: list[dict[str, Any]] = []
        document: dict[str, Any] | None = None
        offset = 12
        while offset < size:
            chunk_header = handle.read(8)
            if len(chunk_header) != 8:
                raise UnsafeModelError("Truncated GLB chunk header")
            chunk_length, chunk_type = struct.unpack("<I4s", chunk_header)
            offset += 8
            if chunk_length % 4:
                raise UnsafeModelError("GLB chunk length is not 4-byte aligned")
            if offset + chunk_length > size:
                raise UnsafeModelError("GLB chunk exceeds declared file bounds")
            if chunk_type == JSON_CHUNK:
                if document is not None:
                    raise UnsafeModelError("GLB contains more than one JSON chunk")
                if chunk_length > max_json_bytes:
                    raise UnsafeModelError("GLB JSON chunk exceeds safety limit")
                raw = handle.read(chunk_length)
                try:
                    value = json.loads(raw.rstrip(b" \t\r\n\x00").decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise UnsafeModelError(f"Invalid GLB JSON chunk: {exc}") from exc
                if not isinstance(value, dict):
                    raise UnsafeModelError("GLB JSON root must be an object")
                document = value
            else:
                handle.seek(chunk_length, 1)
            chunks.append({"type": chunk_type.decode("ascii", errors="replace"), "bytes": chunk_length})
            offset += chunk_length

    if document is None:
        raise UnsafeModelError("GLB has no JSON chunk")
    limits = {
        "nodes": (len(document.get("nodes", [])), max_nodes),
        "meshes": (len(document.get("meshes", [])), max_meshes),
        "accessors": (len(document.get("accessors", [])), max_accessors),
    }
    for label, (actual, limit) in limits.items():
        if actual > limit:
            raise UnsafeModelError(f"GLB has {actual} {label}; safety limit is {limit}")

    external_uris: list[str] = []
    data_uris = 0
    for collection in ("buffers", "images"):
        for item in document.get(collection, []):
            uri = item.get("uri") if isinstance(item, dict) else None
            if not uri:
                continue
            parsed = urlparse(uri)
            if parsed.scheme == "data":
                data_uris += 1
            else:
                external_uris.append(uri)
    if external_uris:
        raise UnsafeModelError(
            "Single-file GLB policy forbids external resources: " + ", ".join(repr(uri) for uri in external_uris[:5])
        )

    return {
        "path": str(source),
        "bytes": size,
        "version": version,
        "chunks": chunks,
        "nodes": limits["nodes"][0],
        "meshes": limits["meshes"][0],
        "accessors": limits["accessors"][0],
        "materials": len(document.get("materials", [])),
        "textures": len(document.get("textures", [])),
        "images": len(document.get("images", [])),
        "animations": len(document.get("animations", [])),
        "skins": len(document.get("skins", [])),
        "extensions_used": document.get("extensionsUsed", []),
        "extensions_required": document.get("extensionsRequired", []),
        "embedded_data_uris": data_uris,
        "asset": document.get("asset", {}),
    }
