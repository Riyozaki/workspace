"""Independent end-to-end hyperparameter-training study; no primary replacement."""
from __future__ import annotations
import argparse
import json
import random
import time
import numpy as np
from .benchmark import compare_pair, read_protocol, summarize, write_csv
from .data import make_dataset
from .experiments import ROOT, RESULTS, log_event, run_isolated


def run(label="hyperparameter_training", full=True, respect_budget=False):
    RESULTS.mkdir(parents=True, exist_ok=True)
    primary = read_protocol()
    spec = json.loads((ROOT / "research/hyperparameter_protocol.json").read_text())
    cases = []
    for phase in (["pilot", "full"] if full else ["pilot"]):
        c = spec[phase]
        phase_cases = [{"phase": phase, "shape": c["axes"], "q": c["test_size"],
                        "seed": seed, "repeat": rep}
                       for seed in c["seeds"] for rep in range(c["repetitions"])]
        random.Random(148433).shuffle(phase_cases)
        cases.extend(phase_cases)
    plan_file = RESULTS / f"{label}_plan.json"
    if plan_file.exists():
        raise FileExistsError(plan_file)
    plan_file.write_text(json.dumps(cases, indent=2) + "\n")
    start = json.loads((ROOT / "research/start_time.json").read_text())["start_unix"]
    rows = []
    for index, c in enumerate(cases):
        if respect_budget and time.time() - start + spec["timeout_seconds_per_method"] > 83 * 60:
            (RESULTS / f"{label}_unfinished.json").write_text(json.dumps(cases[index:], indent=2) + "\n")
            log_event({"event": "budget_cutoff", "label": label, "unstarted_cases": len(cases) - index})
            break
        nx, ny = c["shape"]
        seed, repeat = c["seed"], c["repeat"]
        fixture = ROOT / f"artifacts/studies/{label}_{nx}x{ny}_s{seed}.npz"
        make_dataset(fixture, (nx, ny), c["q"], seed)
        methods = ["hyper_dense", "hyper_spectral"]
        if (seed + repeat) % 2:
            methods.reverse()
        pair = {}
        for method in methods:
            pair[method] = run_isolated(method, fixture,
                f'{label}/{c["phase"]}_s{seed}_r{repeat}_{method}', case=label,
                seed=seed, repeat=repeat, timeout=spec["timeout_seconds_per_method"])
        base, fast = pair["hyper_dense"], pair["hyper_spectral"]
        if base["status"] != "ok" or fast["status"] != "ok":
            log_event({"event": "hyper_pair_incomplete", "label": label, "case": c,
                       "baseline_status": base["status"], "method_status": fast["status"]})
            # Keep raw failed attempts, do not pretend to have a quality or speed score.
            continue
        row = compare_pair(base, fast, primary)
        row.update(phase=c["phase"], baseline_optimizer_success=base["optimizer_success"],
                   method_optimizer_success=fast["optimizer_success"],
                   baseline_nfev=base["optimizer_nfev"], method_nfev=fast["optimizer_nfev"],
                   baseline_nit=base["optimizer_iterations"], method_nit=fast["optimizer_iterations"],
                   max_abs_theta_diff=float(np.max(np.abs(np.array(base["theta"]) - fast["theta"]))),
                   abs_negative_lml_diff=abs(base["final_negative_lml"] - fast["final_negative_lml"]))
        rows.append(row)
        write_csv(RESULTS / f"{label}.csv", rows)
        log_event({"event": "hyper_pair_validation", "label": label, **row})
        print(json.dumps(row), flush=True)
    if rows:
        summaries = {phase: summarize([r for r in rows if r["phase"] == phase])
                     for phase in ("pilot", "full") if any(r["phase"] == phase for r in rows)}
        (RESULTS / f"{label}_summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
        print(json.dumps(summaries, indent=2), flush=True)
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--label", default="hyperparameter_training")
    p.add_argument("--pilot-only", action="store_true")
    p.add_argument("--respect-research-budget", action="store_true")
    a = p.parse_args()
    run(a.label, not a.pilot_only, a.respect_research_budget)
