from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .errors import ToolUnavailableError


def find_soffice() -> Path | None:
    configured = os.environ.get("DOCUMENT_SYSTEM_SOFFICE")
    candidates = [
        configured,
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        str(Path.cwd() / ".cache/libreoffice/current/AppRun"),
        str(Path.cwd() / ".cache/libreoffice/squashfs-root/AppRun"),
        str(Path.home() / ".cache/document-system/libreoffice/AppRun"),
    ]
    for value in candidates:
        if value and Path(value).is_file() and os.access(value, os.X_OK):
            return Path(value).resolve()
    return None


def soffice_version(binary: Path | None = None) -> str | None:
    binary = binary or find_soffice()
    if binary is None:
        return None
    try:
        result = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = (result.stdout or result.stderr).strip()
    return value or None


def _write_locked_profile(profile: Path) -> None:
    user = profile / "user"
    user.mkdir(parents=True, exist_ok=True)
    # MacroSecurityLevel=3 (very high). The profile is disposable and has no trusted locations.
    (user / "registrymodifications.xcu").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
  <item oor:path="/org.openoffice.Office.Common/Security/Scripting">
    <prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>
  </item>
</oor:items>
""",
        encoding="utf-8",
    )


def convert_with_soffice(
    input_path: str | Path,
    output_dir: str | Path,
    target_format: str = "pdf",
    *,
    timeout: int = 180,
    filter_name: str | None = None,
) -> dict[str, Any]:
    source = Path(input_path).resolve()
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    binary = find_soffice()
    if binary is None:
        raise ToolUnavailableError(
            "LibreOffice/soffice not found. Run scripts/bootstrap-documents.sh or set "
            "DOCUMENT_SYSTEM_SOFFICE to a trusted executable."
        )
    if not source.is_file():
        raise FileNotFoundError(source)

    with tempfile.TemporaryDirectory(prefix="documentctl-lo-") as tmp:
        root = Path(tmp)
        profile = root / "profile"
        incoming = root / "input"
        converted = root / "output"
        home = root / "home"
        incoming.mkdir()
        converted.mkdir()
        home.mkdir()
        _write_locked_profile(profile)
        staged = incoming / source.name
        shutil.copy2(source, staged)

        format_argument = target_format if not filter_name else f"{target_format}:{filter_name}"
        command = [
            str(binary),
            "--headless",
            "--nologo",
            "--nodefault",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation={profile.as_uri()}",
            "--convert-to",
            format_argument,
            "--outdir",
            str(converted),
            str(staged),
        ]
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home),
                "TMPDIR": str(root / "tmp"),
                "SAL_USE_VCLPLUGIN": "svp",
                "LANG": env.get("LANG", "C.UTF-8"),
                "LC_ALL": env.get("LC_ALL", "C.UTF-8"),
            }
        )
        Path(env["TMPDIR"]).mkdir()

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise ToolUnavailableError(f"LibreOffice conversion timed out after {timeout}s") from exc

        candidates = [path for path in converted.iterdir() if path.is_file()]
        expected = converted / f"{source.stem}.{target_format.split(':', 1)[0]}"
        produced = expected if expected.exists() else (candidates[0] if len(candidates) == 1 else None)
        if process.returncode != 0 or produced is None:
            raise ToolUnavailableError(
                "LibreOffice conversion failed. "
                f"exit={process.returncode}; stdout={stdout.strip()!r}; "
                f"stderr={stderr.strip()!r}; outputs={[p.name for p in candidates]}"
            )

        final_path = destination / produced.name
        shutil.copy2(produced, final_path)
        return {
            "output": str(final_path),
            "binary": str(binary),
            "version": soffice_version(binary),
            "command": ["<soffice>", *command[1:]],
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
            "returncode": process.returncode,
        }
