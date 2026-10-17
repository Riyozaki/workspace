"""Isolated timing harness; no simultaneous timed workers and no discarded runs."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
RESULTS = Path(os.environ.get("GP_RESULTS_DIR", ROOT / "results")).resolve()


def log_event(event):
    RESULTS.mkdir(exist_ok=True)
    event = {"utc": datetime.now(timezone.utc).isoformat(), **event}
    with (RESULTS / "experiments.jsonl").open("a") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def run_isolated(method, input_path, run_id, *, case="primary", seed=0, repeat=0,
                 threads=2, extra_args=(), timeout=900):
    output = ROOT / "artifacts/predictions" / run_id
    output.parent.mkdir(parents=True, exist_ok=True)
    raw_path = RESULTS / "runs" / (run_id + ".json")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_path.exists():
        raise FileExistsError(f"Refusing to overwrite an existing measured run: {raw_path}")
    env = os.environ.copy()
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS"):
        env[key] = str(threads)
    env["PYTHONHASHSEED"] = "0"
    if method in ("masked_dense", "masked_pcg"):
        worker = "tensor_gp.run_masked"
    elif method in ("hyper_dense", "hyper_spectral"):
        worker = "tensor_gp.run_hyper"
    elif method in ("image_dense", "image_spectral"):
        worker = "tensor_gp.run_external"
    else:
        worker = "tensor_gp.run_numpy" if method == "spectral_numpy" else "tensor_gp.run_one"
    cmd = [sys.executable, "-m", worker, "--method", method,
           "--input", str(input_path), "--output", str(output), "--threads", str(threads),
           "--seed", str(seed), "--repeat", str(repeat), "--case", case, *map(str, extra_args)]
    log_event({"event": "run_start", "run_id": run_id, "method": method,
               "case": case, "seed": seed, "repeat": repeat, "threads": threads,
               "command": cmd, "input": str(input_path)})
    start = perf_counter()
    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=timeout)
        cold_wall = perf_counter() - start
        if proc.returncode:
            record = {"status": "failed", "run_id": run_id, "method": method,
                      "case": case, "seed": seed, "repeat": repeat, "threads": threads,
                      "cold_wall_s": cold_wall, "returncode": proc.returncode,
                      "stdout": proc.stdout, "stderr": proc.stderr}
        else:
            record = json.loads(Path(str(output) + ".json").read_text())
            record.update(status="ok", run_id=run_id, cold_wall_s=cold_wall,
                          prediction_file=str(Path(str(output) + ".npz").relative_to(ROOT)),
                          prediction_sha256=hashlib.sha256(Path(str(output) + ".npz").read_bytes()).hexdigest())
    except subprocess.TimeoutExpired as exc:
        record = {"status": "timeout", "run_id": run_id, "method": method,
                  "case": case, "seed": seed, "repeat": repeat, "threads": threads,
                  "cold_wall_s": perf_counter() - start,
                  "stdout": str(exc.stdout), "stderr": str(exc.stderr)}
    except Exception as exc:
        record = {"status": "harness_error", "run_id": run_id, "method": method,
                  "case": case, "seed": seed, "repeat": repeat, "threads": threads,
                  "cold_wall_s": perf_counter() - start, "error": repr(exc)}
    record["source_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted((ROOT / "tensor_gp").glob("*.py"))}
    raw_path.write_text(json.dumps(record, indent=2) + "\n")
    log_event({"event": "run_end", "run_id": run_id, "status": record["status"],
               "cold_wall_s": record["cold_wall_s"], "result_file": str(raw_path.relative_to(ROOT)),
               "rmse": record.get("quality", {}).get("rmse")})
    print(json.dumps({k: record.get(k) for k in
                      ("run_id", "status", "cold_wall_s", "pipeline_s", "quality")}), flush=True)
    return record


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--initial-baseline", action="store_true")
    a = p.parse_args()
    if a.initial_baseline:
        records = [run_isolated("dense", ROOT / f"artifacts/datasets/seed_{s}.npz",
                                f"baseline_initial/seed{s}", case="baseline_initial", seed=s)
                   for s in range(5)]
        if any(r["status"] != "ok" for r in records):
            raise SystemExit("At least one baseline run failed; see raw records.")
