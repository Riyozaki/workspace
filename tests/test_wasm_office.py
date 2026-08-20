from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from document_system import wasm_office
from document_system.errors import ToolUnavailableError


class _FakeProcess:
    def __init__(self, *, pid: int, outcome: str, destination: Path):
        self.pid = pid
        self.outcome = outcome
        self.destination = destination
        self.returncode: int | None = None
        self._timed_out = False

    def communicate(self, timeout=None):
        if self.outcome == "timeout" and timeout is not None and not self._timed_out:
            self._timed_out = True
            raise subprocess.TimeoutExpired(["node", "wrapper"], timeout)
        if self.outcome == "success":
            self.destination.write_bytes(b"converted")
            self.returncode = 0
            return (json.dumps({"bytes": 9, "engine": "test"}), "")
        self.returncode = -9 if self.outcome == "timeout" else 2
        return ("", "conversion failed")


def _patch_runtime(monkeypatch, tmp_path: Path) -> None:
    wrapper = tmp_path / "wasm-office.mjs"
    wrapper.write_text("// test", encoding="utf-8")
    monkeypatch.setattr(wasm_office, "find_wasm_office", lambda: wrapper)
    monkeypatch.setattr(wasm_office.shutil, "which", lambda _name: "/usr/bin/node")


def test_wasm_office_retries_one_transient_timeout(monkeypatch, tmp_path):
    _patch_runtime(monkeypatch, tmp_path)
    source = tmp_path / "source.pptx"
    source.write_bytes(b"presentation")
    destination = tmp_path / "output.pdf"
    destination.write_bytes(b"stale")
    outcomes = iter(("timeout", "success"))
    processes = []

    def fake_popen(*_args, **_kwargs):
        process = _FakeProcess(
            pid=1000 + len(processes),
            outcome=next(outcomes),
            destination=destination,
        )
        processes.append(process)
        return process

    killed = []
    monkeypatch.setattr(wasm_office.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(wasm_office.os, "killpg", lambda pid, sig: killed.append((pid, sig)))

    result = wasm_office.convert_with_wasm_office(source, destination, "pdf", timeout=1)

    assert destination.read_bytes() == b"converted"
    assert result["attempts"] == 2
    assert result["timed_out_attempts"] == 1
    assert len(processes) == 2
    assert [pid for pid, _sig in killed] == [1000, 1001]


def test_wasm_office_does_not_retry_deterministic_failure(monkeypatch, tmp_path):
    _patch_runtime(monkeypatch, tmp_path)
    source = tmp_path / "source.docx"
    source.write_bytes(b"document")
    destination = tmp_path / "output.pdf"
    calls = 0

    def fake_popen(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return _FakeProcess(pid=2000, outcome="failure", destination=destination)

    monkeypatch.setattr(wasm_office.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(wasm_office.os, "killpg", lambda _pid, _sig: None)

    with pytest.raises(ToolUnavailableError, match="conversion failed"):
        wasm_office.convert_with_wasm_office(source, destination, "pdf")
    assert calls == 1
    assert not destination.exists()
