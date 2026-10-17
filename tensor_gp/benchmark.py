"""Execute the frozen paired experiment; every attempt is retained."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random

import numpy as np

from .data import make_dataset
from . import experiments
from .experiments import ROOT, log_event, run_isolated


def read_protocol():
    p = ROOT / "research/preregister.json"
    expected = (ROOT / "research/preregister.sha256").read_text().split()[0]
    if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise ValueError("Preregistration hash changed; refusing benchmark")
    return json.loads(p.read_text())


def compare_pair(base, fast, protocol):
    if base["status"] != "ok" or fast["status"] != "ok":
        raise ValueError("Cannot score a failed run; raw failed attempt remains logged")
    base_path = ROOT / base["prediction_file"]
    fast_path = ROOT / fast["prediction_file"]
    if base_path.resolve() == fast_path.resolve():
        raise ValueError("Baseline and method refer to the same prediction artifact")
    for record, path in ((base, base_path), (fast, fast_path)):
        if "prediction_sha256" in record:
            if hashlib.sha256(path.read_bytes()).hexdigest() != record["prediction_sha256"]:
                raise ValueError(f"Prediction artifact was overwritten: {path}")
    with np.load(base_path, allow_pickle=False) as b, \
         np.load(fast_path, allow_pickle=False) as f:
        mean_error = float(np.max(np.abs(b["mean"] - f["mean"])))
        variance_error = float(np.max(np.abs(b["variance"] - f["variance"])))
    q = protocol["quality"]
    nll_error = abs(base["quality"]["nll"] - fast["quality"]["nll"])
    guards = q["paired_guardrails"]
    passed = (fast["quality"]["rmse"] <= base["quality"]["rmse"] + q["noninferiority_absolute_tolerance"]
              and mean_error <= guards["max_abs_mean_difference"]
              and variance_error <= guards["max_abs_latent_variance_difference"]
              and nll_error <= guards["max_abs_predictive_nll_difference"])
    return {
        "case": base["case"], "seed": base["seed"], "repeat": base["repeat"],
        "n_train": base["n_train"], "n_test": base["n_test"], "threads": base["threads"],
        "baseline_cold_s": base["cold_wall_s"], "method_cold_s": fast["cold_wall_s"],
        "cold_speedup": base["cold_wall_s"] / fast["cold_wall_s"],
        "baseline_pipeline_s": base["pipeline_s"], "method_pipeline_s": fast["pipeline_s"],
        "pipeline_speedup": base["pipeline_s"] / fast["pipeline_s"],
        "baseline_rmse": base["quality"]["rmse"], "method_rmse": fast["quality"]["rmse"],
        "baseline_nll": base["quality"]["nll"], "method_nll": fast["quality"]["nll"],
        "max_abs_mean_diff": mean_error, "max_abs_variance_diff": variance_error,
        "abs_nll_diff": nll_error, "quality_pass": bool(passed),
        "baseline_peak_rss_bytes": base["peak_rss_bytes"],
        "method_peak_rss_bytes": fast["peak_rss_bytes"],
        "baseline_model_state_bytes": base["model_state_bytes"],
        "method_model_state_bytes": fast["model_state_bytes"],
        "baseline_run_id": base["run_id"], "method_run_id": fast["run_id"],
    }


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("No rows to write")
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def summarize(rows, bootstrap_reps=10000):
    seeds = sorted({r["seed"] for r in rows})
    base_by_seed = np.array([sum(r["baseline_cold_s"] for r in rows if r["seed"] == s) for s in seeds])
    fast_by_seed = np.array([sum(r["method_cold_s"] for r in rows if r["seed"] == s) for s in seeds])
    rng = np.random.default_rng(20261017)
    indices = rng.integers(0, len(seeds), size=(bootstrap_reps, len(seeds)))
    ratios = base_by_seed[indices].sum(axis=1) / fast_by_seed[indices].sum(axis=1)
    ci = np.quantile(ratios, [0.025, 0.975]).tolist()
    return {
        "n_pairs": len(rows), "n_dataset_seeds": len(seeds),
        "primary_speedup_ratio_of_sums": float(base_by_seed.sum() / fast_by_seed.sum()),
        "primary_speedup_cluster_bootstrap_95ci": ci,
        "bootstrap_clusters": "dataset seed, keeping repetitions together",
        "bootstrap_replicates": bootstrap_reps,
        "baseline_cold_mean_s": float(np.mean([r["baseline_cold_s"] for r in rows])),
        "method_cold_mean_s": float(np.mean([r["method_cold_s"] for r in rows])),
        "baseline_cold_min_max_s": [min(r["baseline_cold_s"] for r in rows), max(r["baseline_cold_s"] for r in rows)],
        "method_cold_min_max_s": [min(r["method_cold_s"] for r in rows), max(r["method_cold_s"] for r in rows)],
        "paired_speedup_min_max": [min(r["cold_speedup"] for r in rows), max(r["cold_speedup"] for r in rows)],
        "secondary_inprocess_speedup_ratio_of_sums": sum(r["baseline_pipeline_s"] for r in rows) / sum(r["method_pipeline_s"] for r in rows),
        "baseline_rmse_mean": float(np.mean([r["baseline_rmse"] for r in rows])),
        "method_rmse_mean": float(np.mean([r["method_rmse"] for r in rows])),
        "max_abs_mean_diff": max(r["max_abs_mean_diff"] for r in rows),
        "max_abs_variance_diff": max(r["max_abs_variance_diff"] for r in rows),
        "max_abs_nll_diff": max(r["abs_nll_diff"] for r in rows),
        "all_quality_checks_pass": all(r["quality_pass"] for r in rows),
        "baseline_peak_rss_max_bytes": max(r["baseline_peak_rss_bytes"] for r in rows),
        "method_peak_rss_max_bytes": max(r["method_peak_rss_bytes"] for r in rows),
    }


def run_primary(label="preregistered_primary", result_csv=None):
    protocol = read_protocol()
    c = protocol["primary_case"]
    seeds = protocol["data"]["seeds"]
    reps = protocol["timing"]["repetitions_per_seed"]
    fixtures = {}
    for seed in seeds:
        path = ROOT / f"artifacts/datasets/seed_{seed}.npz"
        # Same deterministic fixture as initial baseline. Regeneration does not use results.
        fixtures[seed] = make_dataset(path, c["axis_sizes"], c["test_size"], seed)
    plans = [(s, r) for s in seeds for r in range(reps)]
    rng = random.Random(20261017)
    rng.shuffle(plans)
    orders = [["dense", "spectral"] if i % 2 else ["spectral", "dense"] for i in range(len(plans))]
    rng.shuffle(orders)
    plan = [{"seed": s, "repeat": r, "order": order} for (s, r), order in zip(plans, orders, strict=True)]
    plan_path = experiments.RESULTS / f"{label}_plan.json"
    plan_path.parent.mkdir(exist_ok=True, parents=True)
    if plan_path.exists():
        raise FileExistsError(f"Refusing to overwrite experiment plan: {plan_path}")
    plan_path.write_text(json.dumps({"label": label, "fixtures": fixtures, "plan": plan}, indent=2) + "\n")
    rows = []
    csv_path = Path(result_csv) if result_csv else experiments.RESULTS / f"{label}.csv"
    for item in plan:
        seed, repeat = item["seed"], item["repeat"]
        pair = {}
        for method in item["order"]:
            pair[method] = run_isolated(method, fixtures[seed]["path"],
                f"{label}/seed{seed}_repeat{repeat}_{method}", case="primary", seed=seed,
                repeat=repeat, threads=protocol["baseline"]["threads"])
        row = compare_pair(pair["dense"], pair["spectral"], protocol)
        rows.append(row)
        write_csv(csv_path, rows)
        log_event({"event": "pair_validation", "label": label, **row})
        print(f'PAIR seed={seed} repeat={repeat} cold={row["cold_speedup"]:.3f}x quality={row["quality_pass"]}', flush=True)
    summary = summarize(rows)
    (experiments.RESULTS / f"{label}_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)
    if not summary["all_quality_checks_pass"]:
        raise SystemExit("Primary quality criterion failed; do not claim lossless speedup.")
    return rows, summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--label", default="primary_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"))
    p.add_argument("--csv", default=None)
    p.add_argument("--results-dir", default=None)
    a = p.parse_args()
    if a.results_dir:
        experiments.RESULTS = Path(a.results_dir).resolve()
    run_primary(a.label, a.csv)
