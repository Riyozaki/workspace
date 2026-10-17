"""All-image Set12 study; bootstrap clusters are images, never repeated runs."""
from __future__ import annotations
import argparse
import json
import random
import time
import numpy as np
from .benchmark import compare_pair, read_protocol, write_csv
from .external_data import download_corpus
from .experiments import ROOT, RESULTS, log_event, run_isolated


def summarize_external(rows, image_names):
    bt = np.array([sum(r["baseline_cold_s"] for r in rows if r["image"] == image) for image in image_names])
    ft = np.array([sum(r["method_cold_s"] for r in rows if r["image"] == image) for image in image_names])
    idx = np.random.default_rng(20261017).integers(0, len(image_names), (10000, len(image_names)))
    distribution = bt[idx].sum(axis=1) / ft[idx].sum(axis=1)
    return {"n_pairs": len(rows), "n_images": len(image_names),
            "cold_speedup_ratio_of_sums": float(bt.sum() / ft.sum()),
            "cold_speedup_image_cluster_bootstrap_95ci": np.quantile(distribution, [.025, .975]).tolist(),
            "baseline_cold_mean_s": sum(r["baseline_cold_s"] for r in rows) / len(rows),
            "method_cold_mean_s": sum(r["method_cold_s"] for r in rows) / len(rows),
            "baseline_rmse_mean": sum(r["baseline_rmse"] for r in rows) / len(rows),
            "method_rmse_mean": sum(r["method_rmse"] for r in rows) / len(rows),
            "all_quality_checks_pass": all(r["quality_pass"] for r in rows),
            "max_abs_mean_diff": max(r["max_abs_mean_diff"] for r in rows),
            "max_abs_variance_diff": max(r["max_abs_variance_diff"] for r in rows),
            "per_image": {name: {"n_pairs": sum(r["image"] == name for r in rows),
                "speedup": sum(r["baseline_cold_s"] for r in rows if r["image"] == name) / sum(r["method_cold_s"] for r in rows if r["image"] == name),
                "baseline_rmse_mean": float(np.mean([r["baseline_rmse"] for r in rows if r["image"] == name])),
                "quality_pass": all(r["quality_pass"] for r in rows if r["image"] == name)} for name in image_names}}


def run(label="external_set12", respect_budget=False):
    RESULTS.mkdir(parents=True, exist_ok=True)
    protocol = read_protocol()
    spec = json.loads((ROOT / "research/external_protocol.json").read_text())
    paths = download_corpus()
    plan = [{"image": str(path), "seed": seed, "repeat": rep,
             "order": ["image_dense", "image_spectral"] if (i + seed + rep) % 2 else ["image_spectral", "image_dense"]}
            for i, path in enumerate(paths) for seed in spec["seeds"] for rep in range(spec["repetitions_per_seed"])]
    random.Random(123456).shuffle(plan)
    plan_file = RESULTS / f"{label}_plan.json"
    if plan_file.exists():
        raise FileExistsError(plan_file)
    plan_file.write_text(json.dumps(plan, indent=2) + "\n")
    start = json.loads((ROOT / "research/start_time.json").read_text())["start_unix"]
    rows, failed = [], []
    for index, p in enumerate(plan):
        if respect_budget and time.time() - start > spec["time_cutoff_research_minute"] * 60:
            (RESULTS / f"{label}_unfinished.json").write_text(json.dumps(plan[index:], indent=2) + "\n")
            log_event({"event": "budget_cutoff", "label": label, "remaining_pairs": len(plan)-index})
            break
        image = ROOT / p["image"]
        pair = {}
        for method in p["order"]:
            pair[method] = run_isolated(method, image,
                f'{label}/image{image.stem}_s{p["seed"]}_r{p["repeat"]}_{method}',
                case=label, seed=p["seed"], repeat=p["repeat"], timeout=180)
        if any(r["status"] != "ok" for r in pair.values()):
            failed.append(p)
            (RESULTS / f"{label}_failed_pairs.json").write_text(json.dumps(failed, indent=2) + "\n")
            continue
        assert pair["image_dense"]["source_sha256"] == pair["image_spectral"]["source_sha256"]
        assert pair["image_dense"]["train_pixel_indices_sha256"] == pair["image_spectral"]["train_pixel_indices_sha256"]
        assert pair["image_dense"]["test_pixel_indices_sha256"] == pair["image_spectral"]["test_pixel_indices_sha256"]
        row = compare_pair(pair["image_dense"], pair["image_spectral"], protocol)
        row["image"] = image.name
        rows.append(row)
        write_csv(RESULTS / f"{label}.csv", rows)
        log_event({"event": "external_pair_validation", "label": label, **row})
    if rows:
        completed_names = sorted({r["image"] for r in rows})
        summary = summarize_external(rows, completed_names)
        summary.update(planned_pairs=len(plan), failed_pairs=len(failed), complete=len(rows)==len(plan))
        (RESULTS / f"{label}_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2), flush=True)
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--label", default="external_set12")
    p.add_argument("--respect-research-budget", action="store_true")
    a = p.parse_args()
    run(a.label, a.respect_research_budget)
