from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from .compare import compare_documents
from .errors import DocumentSystemError
from .render import render_document
from .util import sha256_file

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
MAX_UPLOAD_BYTES = 30 * 1024 * 1024


class MicrosoftOracleError(DocumentSystemError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def microsoft_oracle_available() -> bool:
    return bool(os.environ.get("MS_GRAPH_ACCESS_TOKEN"))


def _graph_request(
    url: str,
    *,
    token: str,
    method: str = "GET",
    data: bytes | None = None,
    content_type: str | None = None,
    follow_redirects: bool = True,
    timeout: int = 120,
) -> tuple[int, dict[str, str], bytes]:
    headers = {"Authorization": f"Bearer {token}"}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read()
        if not follow_redirects and exc.code in {301, 302, 303, 307, 308}:
            return exc.code, dict(exc.headers.items()), body
        raise MicrosoftOracleError(
            f"Microsoft Graph {method} failed: HTTP {exc.code}; {body[-2000:]!r}"
        ) from exc
    except urllib.error.URLError as exc:
        raise MicrosoftOracleError(f"Microsoft Graph connection failed: {exc}") from exc


def convert_with_microsoft_graph(
    input_path: str | Path,
    output_pdf: str | Path,
    *,
    timeout: int = 180,
) -> dict[str, Any]:
    token = os.environ.get("MS_GRAPH_ACCESS_TOKEN")
    if not token:
        raise MicrosoftOracleError(
            "MS_GRAPH_ACCESS_TOKEN is not configured. The Microsoft oracle is explicit opt-in "
            "because it uploads the document to the caller's OneDrive."
        )
    source = Path(input_path).resolve()
    if source.stat().st_size > MAX_UPLOAD_BYTES:
        raise MicrosoftOracleError(
            f"Microsoft Graph conversion limit is 30 MB; input is {source.stat().st_size} bytes"
        )
    remote_name = f"documentctl-oracle-{uuid.uuid4().hex}-{source.name}"
    encoded_name = urllib.parse.quote(remote_name, safe="")
    upload_url = f"{GRAPH_ROOT}/me/drive/root:/{encoded_name}:/content"
    status, _headers, body = _graph_request(
        upload_url,
        token=token,
        method="PUT",
        data=source.read_bytes(),
        content_type="application/octet-stream",
        timeout=timeout,
    )
    if status not in {200, 201}:
        raise MicrosoftOracleError(f"Unexpected upload status: {status}")
    item = json.loads(body)
    item_id = item["id"]
    convert_url = f"{GRAPH_ROOT}/me/drive/items/{urllib.parse.quote(item_id, safe='')}/content?format=pdf"
    try:
        status, headers, body = _graph_request(
            convert_url,
            token=token,
            follow_redirects=False,
            timeout=timeout,
        )
        if status in {301, 302, 303, 307, 308}:
            location = headers.get("Location") or headers.get("location")
            if not location:
                raise MicrosoftOracleError("Graph conversion redirect had no Location header")
            # Pre-signed download URLs must not receive the Graph bearer token.
            with urllib.request.urlopen(location, timeout=timeout) as response:
                body = response.read()
        elif status != 200:
            raise MicrosoftOracleError(f"Unexpected conversion status: {status}")
        destination = Path(output_pdf).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
    finally:
        try:
            _graph_request(
                f"{GRAPH_ROOT}/me/drive/items/{urllib.parse.quote(item_id, safe='')}",
                token=token,
                method="DELETE",
                timeout=timeout,
            )
        except Exception:
            pass
    return {
        "input": str(source),
        "input_sha256": sha256_file(source),
        "output": str(destination),
        "output_sha256": sha256_file(destination),
        "provider": "microsoft-graph-driveitem-conversion",
        "remote_item_deleted": True,
    }


def compare_libreoffice_to_microsoft(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    timeout: int = 180,
) -> dict[str, Any]:
    source = Path(input_path).resolve()
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    libreoffice = render_document(source, destination / "libreoffice", timeout=timeout)
    microsoft_pdf = destination / "microsoft.pdf"
    microsoft = convert_with_microsoft_graph(source, microsoft_pdf, timeout=timeout)
    comparison = compare_documents(
        libreoffice["pdf"],
        microsoft_pdf,
        visual=True,
        visual_dir=destination / "visual-diff",
    )
    return {
        "input": str(source),
        "libreoffice": libreoffice,
        "microsoft": microsoft,
        "comparison": comparison,
        "warning": "Microsoft Graph conversion can differ from desktop Microsoft Office.",
    }
