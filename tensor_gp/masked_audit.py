"""Run every predeclared masked case, preserving slowdowns/timeouts and cutoff."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
from .benchmark import compare_pair, read_protocol, write_csv
from .data import make_dataset
from .experiments import ROOT, RESULTS, log_event, run_isolated


def run(label="masked_extension", full=True, respect_budget=False):
    RESULTS.mkdir(parents=True, exist_ok=True)
    primary = read_protocol()
    spec = json.loads((ROOT / "research/extension_protocol.json").read_text())
    cases = []
    pilot = spec["pilot"]
    for missing in pilot["missing_fractions"]:
        cases.append({"phase": "pilot", "shape": pilot["axes"], "q": pilot["query_count"],
                      "seed": pilot["seed"], "missing": missing})
    if full:
        c = spec["full_cases"]
        for missing in c["missing_fractions"]:
            for seed in c["seeds"]:
                cases.append({"phase": "full", "shape": c["axes"], "q": c["query_count"],
                              "seed": seed, "missing": missing})
    path = RESULTS / f"{label}_plan.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(cases, indent=2) + "\n")
    rows = []
    start = json.loads((ROOT / "research/start_time.json").read_text())["start_unix"]
    for index, case in enumerate(cases):
        if respect_budget and time.time() - start + spec["timeout_seconds_per_method"] >= 75 * 60:
            remaining = cases[index:]
            (RESULTS / f"{label}_unfinished.json").write_text(json.dumps(remaining, indent=2) + "\n")
            log_event({"event": "budget_cutoff", "label": label, "remaining_cases": len(remaining)})
            break
        shape, seed, missing = case["shape"], case["seed"], case["missing"]
        fixture = ROOT / f'artifacts/studies/{label}_{shape[0]}x{shape[1]}_q{case["q"]}_s{seed}.npz'
        make_dataset(fixture, shape, case["q"], seed)
        methods = ["masked_dense", "masked_pcg"]
        if index % 2:
            methods.reverse()
        pair = {}
        for method in methods:
            extra = ["--missing-fraction", missing, "--rtol", spec["cg"]["rtol"],
                     "--maxiter", spec["cg"]["maxiter"]]
            pair[method] = run_isolated(method, fixture,
                f'{label}/{case["phase"]}_missing{missing}_s{seed}_{method}',
                case=label, seed=seed, extra_args=extra,
                timeout=spec["timeout_seconds_per_method"])
        base, fast = pair["masked_dense"], pair["masked_pcg"]
        row = {"phase": case["phase"], "shape": str(shape), "missing_fraction": missing,
               "seed": seed, "n_test": case["q"], "baseline_status": base["status"],
               "method_status": fast["status"], "baseline_cold_s": base["cold_wall_s"],
               "method_cold_s": fast["cold_wall_s"], "cold_speedup": None,
               "baseline_rmse": base.get("quality", {}).get("rmse"),
               "method_rmse": fast.get("quality", {}).get("rmse"),
               "quality_pass": False, "max_abs_mean_diff": None,
               "max_abs_variance_diff": None, "abs_nll_diff": None,
               "cg_fit_iterations": None, "cg_variance_iterations_mean": None,
               "cg_max_relative_residual": None, "status": "incomplete"}
        if base["status"] == fast["status"] == "ok":
            check = compare_pair(base, fast, primary)
            for key in ("cold_speedup", "quality_pass", "max_abs_mean_diff", "max_abs_variance_diff", "abs_nll_diff"):
                row[key] = check[key]
            its = fast["cg_iterations"]
            row["cg_fit_iterations"] = its[0]
            row["cg_variance_iterations_mean"] = sum(its[1:]) / len(its[1:])
            row["cg_max_relative_residual"] = max(fast["cg_relative_residuals"])
            row["status"] = "pass" if row["quality_pass"] else "quality_fail"
        rows.append(row)
        write_csv(RESULTS / f"{label}.csv", rows)
        log_event({"event": "masked_pair_result", "label": label, **row})
        print(json.dumps(row), flush=True)
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--label", default="masked_extension")
    p.add_argument("--pilot-only", action="store_true")
    p.add_argument("--respect-research-budget", action="store_true")
    a = p.parse_args()
    run(a.label, not a.pilot_only, a.respect_research_budget)
