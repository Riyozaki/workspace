#!/usr/bin/env python3
"""Check delivery completeness/immutable evidence, not scientific performance."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path):
    return json.loads(path.read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(require_tracked: bool = False):
    config = read_json(ROOT / "publication.json")
    latest = ROOT / config["latest_study"]
    expected_files = {
        ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "publication.json",
        ROOT / "scripts/verify_publication.py", ROOT / "scripts/publish.sh",
    }
    mandatory = (
        "README.md", "report.md", "results.csv", "work_log.md", "checkpoints.md",
        "protocol.md", "protocol_frozen.json", "eval.py", "method_frozen.json",
        "inference.py", "u8gemm.c", "reproduce.sh", "requirements.txt",
    )
    for name in mandatory:
        path = latest / name
        if not path.is_file():
            raise RuntimeError(f"Latest study missing required file: {path}")
        expected_files.add(path)
    checked = 0
    for study in config["studies"]:
        seal_path = ROOT / study["seal"]
        expected_files.add(seal_path)
        for name, expected in read_json(seal_path).items():
            relative = study.get("path_overrides", {}).get(name, name)
            path = ROOT / study["root"] / relative
            if not path.is_file() or sha256(path) != expected:
                raise RuntimeError(f"Sealed file mismatch ({study['id']}): {path}")
            expected_files.add(path)
            checked += 1
    frozen = read_json(latest / "protocol_frozen.json")
    if frozen["elapsed_seconds"] >= 600:
        raise RuntimeError("Latest protocol was not sealed in first ten minutes")
    for name, expected in frozen["files"].items():
        path = latest / name
        if sha256(path) != expected:
            raise RuntimeError(f"Frozen source/protocol changed: {name}")
        expected_files.add(path)
    summary = read_json(latest / "results/primary_summary.json")
    expected_files.add(latest / "results/primary_summary.json")
    with (latest / "results.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != summary["n_pairs"] or not rows:
        raise RuntimeError("Primary CSV/summary pair counts differ")
    ratio = sum(float(r["baseline_endpoint_seconds"]) for r in rows) / sum(
        float(r["method_endpoint_seconds"]) for r in rows
    )
    if not math.isclose(ratio, summary["speedup_ratio_of_sums"], rel_tol=1e-12):
        raise RuntimeError("Primary speedup differs from all-row ratio of sums")
    if not summary["complete"] or not summary["all_quality_pass"]:
        raise RuntimeError("Published latest primary is incomplete or failed quality")
    proof = read_json(latest / "results/deadline_proof.json")
    expected_files.add(latest / "results/deadline_proof.json")
    if min(proof["elapsed_seconds"], proof["elapsed_monotonic_seconds"]) < 5400:
        raise RuntimeError("Latest final report predates the real deadline")
    if require_tracked:
        tracked = set(subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=ROOT
        ).decode().split("\0"))
        for path in expected_files:
            name = path.relative_to(ROOT).as_posix()
            if name not in tracked:
                raise RuntimeError(f"Delivery file is not staged/tracked: {name}")
            staged = subprocess.check_output(["git", "show", ":" + name], cwd=ROOT)
            if staged != path.read_bytes():
                raise RuntimeError(f"Staged bytes differ from verified working file: {name}")
        untracked = subprocess.check_output([
            "git", "ls-files", "--others", "--exclude-standard", "--", config["latest_study"]
        ], cwd=ROOT, text=True).strip()
        if untracked:
            raise RuntimeError("Latest study still has untracked files:\n" + untracked)
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-tracked", action="store_true")
    args = parser.parse_args()
    count = verify(args.require_tracked)
    print(f"Publication checks passed: {count} sealed files; latest study complete;")
    print("frozen protocol/evaluator unchanged; primary CSV and deadline consistent.")
    if args.require_tracked:
        print("All checked delivery files are staged/tracked with identical bytes.")


if __name__ == "__main__":
    main()
