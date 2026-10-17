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
    research_root = config.get("latest_research_study") or config["latest_study"]
    latest = ROOT / research_root
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
    delivery = config.get("latest_delivery")
    if delivery:
        delivery_root = ROOT / delivery["root"]
        for name in delivery["required"]:
            path = delivery_root / name
            if not path.is_file():
                raise RuntimeError(f"Latest delivery missing: {path}")
            expected_files.add(path)
        delivery_seal = ROOT / delivery["seal"]
        expected_files.add(delivery_seal)
        for name, expected in read_json(delivery_seal).items():
            path = delivery_root / name
            if not path.is_file() or sha256(path) != expected:
                raise RuntimeError(f"Latest delivery sealed file mismatch: {name}")
            expected_files.add(path)
            checked += 1
        verification = delivery.get("verification", {})
        browser = read_json(delivery_root / verification.get("browser_checks", "results/browser_checks.json"))
        if not browser["all_required_checks_pass"]:
            raise RuntimeError("Latest prototype browser checks did not pass")
        smoke = read_json(delivery_root / verification.get("model_smoke", "results/model_smoke.json"))
        if not smoke["actual_inference"]:
            raise RuntimeError("Latest prototype lacks executed real-model inference")
        # This is a completeness/integrity gate, NOT a demand to hide negative
        # research findings or manufacture a passing capability benchmark.
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
            "git", "ls-files", "--others", "--exclude-standard", "--", research_root
        ], cwd=ROOT, text=True).strip()
        if untracked:
            raise RuntimeError("Latest study still has untracked files:\n" + untracked)
        if delivery:
            untracked_delivery = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", delivery["root"]], cwd=ROOT, text=True).strip()
            if untracked_delivery:
                raise RuntimeError("Latest prototype still has untracked files:\n" + untracked_delivery)
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-tracked", action="store_true")
    args = parser.parse_args()
    count = verify(args.require_tracked)
    print(f"Publication checks passed: {count} sealed files; historical studies and latest delivery complete;")
    print("frozen protocol/evaluator unchanged; primary CSV and deadline consistent.")
    if args.require_tracked:
        print("All checked delivery files are staged/tracked with identical bytes.")


if __name__ == "__main__":
    main()
