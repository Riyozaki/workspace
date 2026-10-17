"""Preplanned hostile baselines and scaling studies, not pooled with primary."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import random
from .benchmark import compare_pair, read_protocol, summarize, write_csv
from .data import make_dataset
from .experiments import ROOT, RESULTS, log_event, run_isolated


def four_way(label="audit_four_way", seeds=range(5), repetitions=3):
    RESULTS.mkdir(parents=True, exist_ok=True)
    protocol = read_protocol()
    methods = ["dense", "dense_fortran", "spectral", "spectral_numpy"]
    rng = random.Random(148410)
    plan = []
    for seed in seeds:
        for rep in range(repetitions):
            order = methods[rep % 4:] + methods[:rep % 4]
            rng.shuffle(order)
            plan.append({"seed": seed, "repeat": rep, "order": order})
    rng.shuffle(plan)
    path = RESULTS / f"{label}_plan.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(plan, indent=2) + "\n")
    rows = []
    comparisons = [("dense", "spectral"), ("dense_fortran", "spectral"),
                   ("dense", "spectral_numpy"), ("dense_fortran", "spectral_numpy")]
    for p in plan:
        pair = {}
        for method in p["order"]:
            pair[method] = run_isolated(method, ROOT / f'artifacts/datasets/seed_{p["seed"]}.npz',
                f'{label}/s{p["seed"]}_r{p["repeat"]}_{method}', case=label,
                seed=p["seed"], repeat=p["repeat"])
        for baseline, method in comparisons:
            row = compare_pair(pair[baseline], pair[method], protocol)
            row["comparison"] = baseline + "__vs__" + method
            rows.append(row)
        write_csv(RESULTS / f"{label}.csv", rows)
    summaries = {b + "__vs__" + m: summarize([r for r in rows if r["comparison"] == b + "__vs__" + m])
                 for b, m in comparisons}
    (RESULTS / f"{label}_summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    print(json.dumps(summaries, indent=2), flush=True)
    log_event({"event": "audit_complete", "label": label, "comparisons": summaries})


def scaling(label="scaling", shapes=((16, 16), (32, 32), (64, 64), (128, 64), (128, 96)),
            seeds=(0, 1, 2), repetitions=2, methods=("dense", "spectral"), test_size=512):
    RESULTS.mkdir(parents=True, exist_ok=True)
    protocol = read_protocol()
    rows = []
    for shape in shapes:
        for seed in seeds:
            data = ROOT / f"artifacts/studies/{label}_{shape[0]}x{shape[1]}_s{seed}.npz"
            make_dataset(data, shape, test_size, seed)
            for rep in range(repetitions):
                order = methods if (rep + seed) % 2 else methods[::-1]
                pair = {}
                for method in order:
                    pair[method] = run_isolated(method, data,
                        f"{label}/{shape[0]}x{shape[1]}_s{seed}_r{rep}_{method}",
                        case=label, seed=seed, repeat=rep)
                row = compare_pair(pair[methods[0]], pair[methods[1]], protocol)
                row["shape"] = f"{shape[0]}x{shape[1]}"
                rows.append(row)
                write_csv(RESULTS / f"{label}.csv", rows)
    summaries = {str(shape): summarize([r for r in rows if r["shape"] == f"{shape[0]}x{shape[1]}"])
                 for shape in shapes}
    (RESULTS / f"{label}_summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    print(json.dumps(summaries, indent=2), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("study", choices=["four-way", "scaling", "scaling-tuned"])
    p.add_argument("--label", default=None)
    a = p.parse_args()
    if a.study == "four-way":
        four_way(a.label or "audit_four_way")
    elif a.study == "scaling":
        scaling(a.label or "scaling")
    else:
        scaling(a.label or "scaling_tuned", methods=("dense_fortran", "spectral_numpy"))
